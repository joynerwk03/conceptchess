"""Coordinate-descent weight tuning against the train split of the eval set.

Optimizes the selected weight groups by trying multiplicative steps on each
key in turn (train loss only — exp2 judges on val, which this never sees).
On improvement, writes the tuned values back into engine/weights.py.

Usage:
  python -m research.tune material.            # tune one group
  python -m research.tune pst. mob. --passes 3
"""

import argparse
import re
import sys
from pathlib import Path

from engine.weights import W
from research.evalloss import loss

WEIGHTS_FILE = Path(__file__).parent.parent / "engine" / "weights.py"

COARSE = (0.7, 0.85, 1.15, 1.3)
FINE = (0.94, 0.98, 1.02, 1.06)


def tune(keys, passes):
    best = loss("train")
    print(f"start train loss {best:.6f}  ({len(keys)} params)")
    for p in range(passes):
        steps = COARSE if p == 0 else FINE
        improved = False
        for key in keys:
            base = W[key]
            if base == 0:
                continue
            for mult in steps:
                W[key] = base * mult
                l = loss("train")
                if l < best - 1e-7:
                    best = l
                    base = W[key]
                    improved = True
            W[key] = base
        print(f"pass {p + 1}: train loss {best:.6f}")
        if not improved and p > 0:
            break
    return best


def write_weights():
    src = WEIGHTS_FILE.read_text()
    for key, val in W.items():
        v = round(float(val), 3)
        v = int(v) if v == int(v) else v
        src, n = re.subn(rf'("{re.escape(key)}":\s*)[-\d.]+', rf"\g<1>{v}", src)
        assert n == 1, key
    WEIGHTS_FILE.write_text(src)
    print(f"wrote tuned values -> {WEIGHTS_FILE}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("groups", nargs="+", help="key prefixes, e.g. material. pst.")
    p.add_argument("--passes", type=int, default=3)
    args = p.parse_args()

    keys = [k for k in W if any(k.startswith(g) for g in args.groups)]
    if not keys:
        sys.exit(f"no keys match {args.groups}")
    start = loss("train")
    end = tune(keys, args.passes)
    if end < start - 1e-7:
        for k in keys:
            print(f"  {k}: {W[k]}")
        write_weights()
    else:
        print("no improvement; weights.py untouched")


if __name__ == "__main__":
    main()

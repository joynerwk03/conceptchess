"""How often does a concept actually fire, and does it fire when it shouldn't?

Run this BEFORE gating any new or modified eval concept. It costs seconds and
has already caught both ways an eval term can waste a gate:

* **Too rare to measure.** The opposite-bishop modifier's condition (one bishop
  each and no other pieces) fires in well under 1% of real positions, so its
  gate could only ever return noise -- which it did, for two sessions, before
  anyone checked. A term that fires in <2% of positions cannot be resolved by
  any number of games this project can afford.
* **Firing on the wrong thing.** A "trapped pieces" concept defined as "zero
  safe squares" turned out to fire EIGHT TIMES ON THE START POSITION -- both
  bishops and both rooks, both colours. It was not measuring trapped pieces at
  all, it was measuring undeveloped ones, which piece-square tables already
  price. It gated -16 and the reason was visible here in one second.

The start-position row is the cheapest sanity check in the file: the start
position is symmetric, so any concept scoring non-zero there is either
side-to-move dependent (tempo legitimately reads +10) or measuring something
other than what its name claims.

Usage:
  python -m research.firing_rate                       # every concept
  python -m research.firing_rate --concept threats     # just one
  python -m research.firing_rate --suite research/suites/blunders_v1.epd
"""

import argparse
from pathlib import Path

import chess

from engine.concepts import ALL_CONCEPTS, ALL_MODIFIERS
from engine.context import EvalContext

ROOT = Path(__file__).parent.parent
DEFAULT_SUITE = ROOT / "research" / "suites" / "blunders_v1.epd"


def load_positions(suite):
    boards = []
    path = Path(suite)
    if not path.exists():
        return boards
    for ln in path.read_text().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            boards.append(chess.Board().from_epd(ln)[0])
        except Exception:
            continue
    return boards


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--suite", default=str(DEFAULT_SUITE))
    p.add_argument("--concept", default=None, help="only this concept/modifier name")
    args = p.parse_args()

    boards = load_positions(args.suite)
    if not boards:
        raise SystemExit(f"no positions in {args.suite}")
    contexts = [EvalContext(b) for b in boards]
    start_ctx = EvalContext(chess.Board())

    print(f"{len(boards)} positions from {Path(args.suite).name}\n")
    print(f"{'concept':<18} {'fires':>8} {'mean |cp|':>10} {'max |cp|':>9}  start")
    print("-" * 62)

    for c in ALL_CONCEPTS:
        if args.concept and c.name != args.concept:
            continue
        vals = [c.score(ctx) for ctx in contexts]
        nz = [abs(v) for v in vals if v]
        start = c.score(start_ctx)
        flag = ""
        if len(nz) / len(vals) < 0.02:
            flag = "  <-- too rare to gate"
        if abs(start) > 1e-9 and c.name != "tempo":
            # The start position is symmetric, so anything but a side-to-move
            # term (tempo) scoring here is measuring the wrong thing.
            flag += "  <-- NON-ZERO ON A SYMMETRIC POSITION"
        print(f"{c.name:<18} {100 * len(nz) / len(vals):7.1f}% "
              f"{(sum(nz) / len(nz) if nz else 0):10.1f} "
              f"{(max(nz) if nz else 0):9.1f}  {start:+7.1f}{flag}")

    for m in ALL_MODIFIERS:
        if args.concept and m.name != args.concept:
            continue
        fires = sum(1 for ctx in contexts if m.factor(ctx) != 1.0)
        flag = "  <-- too rare to gate" if fires / len(contexts) < 0.02 else ""
        print(f"{m.name + ' (mod)':<18} {100 * fires / len(contexts):7.1f}% "
              f"{'-':>10} {'-':>9}  {'-':>7}{flag}")


if __name__ == "__main__":
    main()

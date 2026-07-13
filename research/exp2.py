"""Session-2 experiment runner: measure, judge, log. One call = one experiment.

Runs the eval-invariant guard tests, computes train/val eval loss for the
current working tree, auto-judges KEPT (val loss improved on the running
best) vs DISCARDED, and appends the attempt to research/session2.json.
Every attempt is logged, including failures.

Usage: python -m research.exp2 "tune material values"
"""

import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from research.evalloss import loss

HERE = Path(__file__).parent
LOG = HERE / "session2.json"
EPS = 1e-6


def main():
    desc = sys.argv[1] if len(sys.argv) > 1 else "unnamed"
    t0 = time.perf_counter()

    guard = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_eval.py", "-q", "-x"],
        capture_output=True, text=True, cwd=HERE.parent)
    guard_ok = guard.returncode == 0

    train = loss("train")
    val = loss("val")

    entries = json.loads(LOG.read_text()) if LOG.exists() else []
    # Compare against the currently ADOPTED state (last kept experiment),
    # not the historical minimum — overrides (e.g. strength-gated reverts)
    # can legitimately move the adopted val loss up.
    kept_vals = [e["val_loss"] for e in entries if e["kept"]]
    best = kept_vals[-1] if kept_vals else float("inf")

    kept = guard_ok and val < best - EPS
    entries.append({
        "n": len(entries),
        "date": date.today().isoformat(),
        "desc": desc,
        "train_loss": round(train, 6),
        "val_loss": round(val, 6),
        "guard_ok": guard_ok,
        "kept": kept,
        "seconds": round(time.perf_counter() - t0, 1),
    })
    LOG.write_text(json.dumps(entries, indent=1) + "\n")

    verdict = "KEPT" if kept else ("GUARD-FAIL" if not guard_ok else "DISCARDED")
    delta = val - best if best < float("inf") else 0.0
    print(f"[exp {len(entries) - 1}] {verdict}  val {val:.6f} ({delta:+.6f} vs best)"
          f"  train {train:.6f}  '{desc}'")
    if not guard_ok:
        print(guard.stdout[-600:])
    sys.exit(0 if kept else 1)


if __name__ == "__main__":
    main()

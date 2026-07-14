"""Session-3 experiment runner. One call = one experiment.

Metric: sibling-rank agreement (higher is better) — validated in
research/validate_metrics.py as the best fast predictor of playing strength.
Judges KEPT/DISCARDED on val rank agreement vs the adopted state; logs every
attempt to research/session3.json (evalloss recorded for reference only).

Session-2 rule stays in force: weight-value changes additionally need a match
gate before final adoption; the metric alone only screens.

Usage: python -m research.exp3 "description"
"""

import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from research.metrics3 import rank_agreement
from research.evalloss import loss

HERE = Path(__file__).parent
LOG = HERE / "session3.json"
EPS = 1e-9


def main():
    desc = sys.argv[1] if len(sys.argv) > 1 else "unnamed"
    t0 = time.perf_counter()

    guard = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_eval.py", "-q", "-x"],
        capture_output=True, text=True, cwd=HERE.parent)
    guard_ok = guard.returncode == 0

    train = rank_agreement("train")
    val = rank_agreement("val")
    eloss = loss("val")

    entries = json.loads(LOG.read_text()) if LOG.exists() else []
    kept_vals = [e["val_rank"] for e in entries if e["kept"]]
    best = kept_vals[-1] if kept_vals else -1.0

    kept = guard_ok and val > best + EPS
    entries.append({
        "n": len(entries),
        "date": date.today().isoformat(),
        "desc": desc,
        "train_rank": round(train, 3),
        "val_rank": round(val, 3),
        "evalloss_val": round(eloss, 6),
        "guard_ok": guard_ok,
        "kept": kept,
        "seconds": round(time.perf_counter() - t0, 1),
    })
    LOG.write_text(json.dumps(entries, indent=1) + "\n")

    verdict = "KEPT" if kept else ("GUARD-FAIL" if not guard_ok else "DISCARDED")
    print(f"[exp {len(entries) - 1}] {verdict}  val_rank {val:.3f}% "
          f"({val - best:+.3f} vs adopted)  train {train:.3f}%  "
          f"evalloss {eloss:.6f}  '{desc}'")
    if not guard_ok:
        print(guard.stdout[-600:])
    sys.exit(0 if kept else 1)


if __name__ == "__main__":
    main()

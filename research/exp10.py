"""Session-10+ experiment runner (compiled C engine). One call = one experiment.

Records nodes/time to depth 9 for the C engine plus tactics accuracy.
Speed-only changes (node count unchanged, only time changes) are judged by
time alone. Changes that alter node counts change search *shape* and MUST be
match-gated before being trusted — record them as PENDING-GATE and finalize
manually once the match result is in (see research/sprt.py / match.py --sprt).

Usage:
  python -m research.exp10 "description"                # judged by time
  python -m research.exp10 "description" --shape-change  # PENDING-GATE
"""

import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from research.cttd import measure
from research.tactics import run_suite

HERE = Path(__file__).parent
LOG = HERE / "session10.json"
SUITE = HERE.parent / "tests" / "suites" / "tactics_v1.epd"
DEPTH = 9


def main():
    desc = sys.argv[1] if len(sys.argv) > 1 else "unnamed"
    shape_change = "--shape-change" in sys.argv
    t0 = time.perf_counter()

    guard = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-m", "not slow", "-x"],
        capture_output=True, text=True, cwd=HERE.parent)
    guard_ok = guard.returncode == 0

    nodes, ttime = measure(DEPTH)
    tac = run_suite(SUITE, movetime=0.5, verbose=False)

    entries = json.loads(LOG.read_text()) if LOG.exists() else []
    kept = [e for e in entries if e["kept"]]
    base_time = kept[-1]["time_d9"] if kept else float("inf")
    base_nodes = kept[-1]["nodes_d9"] if kept else None

    nodes_changed = base_nodes is not None and nodes != base_nodes

    if shape_change or nodes_changed:
        verdict = "PENDING-GATE"
        is_kept = False
    else:
        is_kept = guard_ok and tac["pct"] >= 90 and ttime < base_time * 0.97
        verdict = "KEPT" if is_kept else ("GUARD-FAIL" if not guard_ok else "DISCARDED")

    entries.append({
        "n": len(entries),
        "date": date.today().isoformat(),
        "desc": desc,
        "nodes_d9": nodes,
        "time_d9": round(ttime, 3),
        "tactics_pct": tac["pct"],
        "guard_ok": guard_ok,
        "kept": is_kept,
        "shape_change": shape_change or nodes_changed,
        "seconds": round(time.perf_counter() - t0, 1),
    })
    LOG.write_text(json.dumps(entries, indent=1) + "\n")

    speedup = (base_time - ttime) / base_time * 100 if base_time < float("inf") else 0
    print(f"[exp {len(entries) - 1}] {verdict}  time_d9 {ttime:.3f}s ({speedup:+.1f}%)"
          f"  nodes {nodes:,}{' (CHANGED)' if nodes_changed else ''}"
          f"  tactics {tac['pct']:.0f}%  '{desc}'")
    if not guard_ok:
        print(guard.stdout[-600:])
    sys.exit(0 if is_kept or shape_change or nodes_changed else 1)


if __name__ == "__main__":
    main()

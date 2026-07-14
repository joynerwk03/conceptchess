"""Session-5 experiment runner (search sprint). One call = one experiment.

Records nodes/time to depth 6 and tactics accuracy. Judgment:
- speed experiments: KEPT if time-to-depth improves >= 3% with tactics >= 90%
  and tests green (node count may change if the change reshapes the search)
- quality experiments (--gate match): logged as PENDING-GATE; the match
  decides, then the entry is finalized manually with the result

Usage:
  python -m research.exp5 "description"
  python -m research.exp5 "description" --quality   # judged by match, not ttd
"""

import json
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from research.ttd import measure
from research.tactics import run_suite

HERE = Path(__file__).parent
LOG = HERE / "session6.json"
SUITE = HERE.parent / "tests" / "suites" / "tactics_v1.epd"


def main():
    desc = sys.argv[1] if len(sys.argv) > 1 else "unnamed"
    quality = "--quality" in sys.argv
    t0 = time.perf_counter()

    guard = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-m", "not slow", "-x"],
        capture_output=True, text=True, cwd=HERE.parent)
    guard_ok = guard.returncode == 0

    nodes, ttime = measure(6)
    tac = run_suite(SUITE, movetime=1.0, verbose=False)

    entries = json.loads(LOG.read_text()) if LOG.exists() else []
    kept = [e for e in entries if e["kept"]]
    base_time = kept[-1]["time_d6"] if kept else float("inf")

    if quality:
        verdict = "PENDING-GATE"
        is_kept = False
    else:
        is_kept = (guard_ok and tac["pct"] >= 90
                   and ttime < base_time * 0.97)
        verdict = "KEPT" if is_kept else ("GUARD-FAIL" if not guard_ok else "DISCARDED")

    entries.append({
        "n": len(entries),
        "date": date.today().isoformat(),
        "desc": desc,
        "nodes_d6": nodes,
        "time_d6": round(ttime, 2),
        "tactics_pct": tac["pct"],
        "guard_ok": guard_ok,
        "kept": is_kept,
        "quality": quality,
        "seconds": round(time.perf_counter() - t0, 1),
    })
    LOG.write_text(json.dumps(entries, indent=1) + "\n")

    speedup = (base_time - ttime) / base_time * 100 if base_time < float("inf") else 0
    print(f"[exp {len(entries) - 1}] {verdict}  time_d6 {ttime:.2f}s ({speedup:+.1f}%)"
          f"  nodes {nodes:,}  tactics {tac['pct']:.0f}%  '{desc}'")
    if not guard_ok:
        print(guard.stdout[-600:])
    sys.exit(0 if is_kept or quality else 1)


if __name__ == "__main__":
    main()

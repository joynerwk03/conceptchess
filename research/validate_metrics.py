"""Meta-experiment: which candidate metric predicts real playing strength?

Runs every candidate metric against four engine states whose relative
strength is match-measured (session 2):

    state        rev       Elo vs session-1 (measured)
    session1     6b96862      0
    exp13        HEAD        +35   (55% in 10 games)
    bounded      493d006    -127   (32.5% in 20 games)
    unbounded    f0343d9    ~-320  (lost 25% match to bounded)

A useful iteration metric must rank these in strength order. evalloss is
included to document that it ranks them BACKWARDS.

Usage: python -m research.validate_metrics <worktree_dir_with_the_4_states>
(worktrees named session1/ exp13/ bounded/ unbounded/; exp13 may be ".")
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

PROBE = r"""
import sys, json
sys.path.insert(0, sys.argv[1])   # engine version under test
sys.path.insert(1, sys.argv[2])   # current research/ tooling + data
import research.metrics3 as m3
import research.evalloss as el
print(json.dumps({
    "evalloss_val": el.loss("val"),
    "rank_train": m3.rank_agreement("train"),
    "rank_val": m3.rank_agreement("val"),
    "qrank_val": m3.qrank_agreement("val"),
    "move_match_d3": m3.move_match("val"),
}))
"""


def probe(engine_dir):
    out = subprocess.run(
        [sys.executable, "-c", PROBE, str(engine_dir), str(ROOT)],
        capture_output=True, text=True, timeout=1200)
    if out.returncode != 0:
        raise RuntimeError(out.stderr[-800:])
    return json.loads(out.stdout.strip().splitlines()[-1])


def main():
    base = Path(sys.argv[1])
    states = [("session1", 0), ("exp13", 35), ("bounded", -127), ("unbounded", -320)]
    results = {}
    for name, elo in states:
        d = base / name
        print(f"probing {name} ...", flush=True)
        results[name] = probe(d)
        results[name]["elo"] = elo
    print(f"\n{'state':<10} {'elo':>5} {'evalloss':>9} {'rank_t':>7} {'rank_v':>7} "
          f"{'qrank_v':>8} {'mm_d3':>6}")
    for name, _ in states:
        r = results[name]
        print(f"{name:<10} {r['elo']:>5} {r['evalloss_val']:>9.5f} "
              f"{r['rank_train']:>7.2f} {r['rank_val']:>7.2f} "
              f"{r['qrank_val']:>8.2f} {r['move_match_d3']:>6.2f}")
    (ROOT / "research" / "metric_validation.json").write_text(
        json.dumps(results, indent=2) + "\n")
    print("\nsaved to research/metric_validation.json")


if __name__ == "__main__":
    main()

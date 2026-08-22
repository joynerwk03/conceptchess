"""Screen a configuration against the cached referee table.

The expensive half of a fidelity screen -- the referee's opinion -- is a property
of the POSITION, not of the engine under test, so reftable.py computes it once
and it is reused forever. Each candidate then costs one fixed-depth search plus
a dictionary lookup.

**The statistic is the blunder RATE, not the mean.** Mean centipawn loss is
useless here for two reasons, both measured rather than assumed:

  * Mate scores (`mate_score=100000`) dominate it. The first run of this screen
    reported a mean of 194 with a standard error of 89.6 -- the same tail
    contamination `eval_tails.py` hit when a p95 turned out to be a mate score.
    Losses are now clamped to CLAMP cp, which preserves the ordering of real
    mistakes and stops one position from carrying the estimate.

  * Even clean, the mean is far too noisy. Over 200 positions it could not
    separate configurations spanning 33 Elo (14.1 / 13.9 / 14.2).

The share of moves losing more than 50cp does separate them: 16% for the
baseline against 19% for a configuration measured at -33 Elo on two anchors,
which at 1500 positions is about three standard errors. Proportions are far
better behaved than a heavy-tailed mean.

Reported with standard errors so a reading can be checked against its own
resolution rather than over-read -- the failure mode that has cost this session
twice already.

Usage: screen_ref.py <table.jsonl> <depth> <name=tree> [...]   env CLAMP
"""
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

CC = Path("/home/joynerwk03/mission-control/projects/conceptchess")
PY = str(CC / ".venv/bin/python")
CLAMP = int(os.environ.get("CLAMP", "300"))

PROBE = r'''
import sys, json, chess
from engine.engine import Engine
from engine import core
core.set_threads(1)
depth = int(sys.argv[1])
fens = json.loads(open(sys.argv[2]).read())
eng = Engine(use_book=False, use_tablebase=False)
out = []
for f in fens:
    r = eng.best_move(chess.Board(f), movetime=999.0, max_depth=depth)
    out.append([str(r.move), int(r.nodes)])
print(json.dumps(out))
'''


def main():
    table_path = Path(sys.argv[1])
    depth = int(sys.argv[2])
    configs = [("baseline", CC)]
    for arg in sys.argv[3:]:
        name, path = arg.split("=", 1)
        configs.append((name, Path(path)))

    ref = {}
    for ln in table_path.read_text().splitlines():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        ref[r["fen"]] = r
    fens = list(ref)
    tmp = Path("/tmp/screen_fens.json")
    tmp.write_text(json.dumps(fens))

    n = len(fens)
    print(f"{n} positions, our depth {depth}, losses clamped at {CLAMP}cp")
    print(f"{'config':<14}{'nodes':>14}{'vs base':>9}"
          f"{'>20cp':>9}{'>50cp':>9}{'>100cp':>9}{'mean':>8}")

    base_n = None
    for name, tree in configs:
        env = dict(os.environ, PYTHONPATH=".")
        r = subprocess.run([PY, "-c", PROBE, str(depth), str(tmp)],
                           cwd=str(tree), capture_output=True, text=True, env=env)
        if r.returncode != 0:
            sys.stderr.write(r.stderr[-2000:])
            raise SystemExit(f"probe failed in {tree}")
        res = json.loads(r.stdout.strip().splitlines()[-1])
        nodes = sum(x[1] for x in res)
        if base_n is None:
            base_n = nodes
        losses = []
        for fen, (uci, _) in zip(fens, res):
            row = ref[fen]
            tab = row["moves"]
            best = tab[row["best"]]
            got = tab[uci] if uci in tab else min(tab.values())
            losses.append(min(CLAMP, max(0, best - got)))

        def rate(th):
            k = sum(1 for x in losses if x > th)
            p = k / len(losses)
            return 100 * p, 100 * (p * (1 - p) / len(losses)) ** 0.5

        r20, s20 = rate(20)
        r50, s50 = rate(50)
        r100, s100 = rate(100)
        print(f"{name:<14}{nodes:>14,}{nodes / base_n:>8.2f}x"
              f"{r20:>6.1f}±{s20:<3.1f}{r50:>6.1f}±{s50:<3.1f}"
              f"{r100:>6.1f}±{s100:<3.1f}{statistics.mean(losses):>8.1f}")


if __name__ == "__main__":
    main()

"""Iso-NODE referee screen: the instrument this project has been missing.

The existing screen (`screen_paired.py`) is FIXED-DEPTH. For a change that alters
tree size it therefore sees the fidelity cost and is structurally blind to the
depth benefit, which is why it mispriced lmr2+qs (0.65x nodes for +0.925cp, then
-25.0 and -3.0 Elo on two anchors) and why closing thinning cost SEVEN full
game-gates. Every pruning candidate in this project has had to buy its answer in
games because no cheap instrument could price it.

Fixed-TIME would fix the validity problem and break something worse: a
wall-clock-limited search is non-deterministic, so the paired differences that
make this screen sensitive would drown in machine noise. `noise_floor.sh` says
so outright.

Fixed-NODES is both. It is deterministic AND it prices the trade correctly: a
change that prunes better reaches GREATER DEPTH inside the same node budget, so
the screen sees the depth benefit and the move-quality cost in one number.

No engine change is needed. For each position, search the baseline at depth D and
record its node count N, then search the candidate at increasing depths and keep
the deepest one costing <= N nodes. That is an iso-node comparison built out of
the fixed-depth API the engine already has.

Statistic: share of moves losing more than 20/50/100cp against the cached SF11
MultiPV table, never the mean -- mate scores put the mean's standard error at
89.6. Same convention as screen_paired.py so numbers stay comparable.

CALIBRATE BEFORE TRUSTING. This project's rule is that an uncalibrated screen is
an opinion. Three configurations have known Elo and must be run through this
first: baseline, lmr1.75 (-4 Elo) and rfp25 (-33 Elo). Correct ordering plus
separation of the -33 is the minimum bar; failing to separate the -4 is expected
and fine.

Usage: screen_isonode.py <reftable.jsonl> <base_depth> name=<worktree> ...
"""
import json
import os
import subprocess
import sys

PY = "/home/joynerwk03/mission-control/projects/conceptchess/.venv/bin/python"
CLAMP = 300
MAXD = 24

PROBE = r'''
import sys, json, chess
from engine.engine import Engine
from engine import core
core.set_threads(1)
mode = sys.argv[1]                      # "base" or "iso"
depth = int(sys.argv[2])
fens = json.loads(open(sys.argv[3]).read())
budget = json.loads(open(sys.argv[4]).read()) if mode == "iso" else None
eng = Engine(use_book=False, use_tablebase=False)
out = []
for i, f in enumerate(fens):
    b = chess.Board(f)
    if mode == "base":
        r = eng.best_move(b, movetime=999.0, max_depth=depth)
        out.append([str(r.move), int(r.nodes), depth])
    else:
        # deepest search that fits the baseline's node budget for THIS position
        cap = budget[i]
        best = None
        for d in range(1, %d):
            r = eng.best_move(b, movetime=999.0, max_depth=d)
            if best is not None and int(r.nodes) > cap:
                break
            best = [str(r.move), int(r.nodes), d]
        out.append(best)
print(json.dumps(out))
''' % MAXD


def run(tree, mode, depth, fens_path, budget_path=None):
    env = dict(os.environ, PYTHONPATH=".")
    args = [PY, "-c", PROBE, mode, str(depth), fens_path, budget_path or fens_path]
    r = subprocess.run(args, cwd=str(tree), capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        raise SystemExit(f"probe failed in {tree}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def losses(res, fens, ref):
    out = []
    for fen, (uci, _n, _d) in zip(fens, res):
        row = ref[fen]
        tab = row["moves"]
        best = tab[row["best"]]
        got = tab[uci] if uci in tab else min(tab.values())
        out.append(min(CLAMP, max(0, best - got)))
    return out


def main():
    reftable, base_depth = sys.argv[1], int(sys.argv[2])
    configs = [a.split("=", 1) for a in sys.argv[3:]]

    ref = {}
    for ln in open(reftable):
        if ln.strip():
            r = json.loads(ln)
            ref[r["fen"]] = r
    fens = list(ref)
    tmp = "/tmp/iso_fens.json"
    bud = "/tmp/iso_budget.json"
    json.dump(fens, open(tmp, "w"))

    CC = "/home/joynerwk03/mission-control/projects/conceptchess"
    base = run(CC, "base", base_depth, tmp)
    json.dump([n for _m, n, _d in base], open(bud, "w"))
    bl = losses(base, fens, ref)
    n = len(bl)
    print(f"{n} positions, baseline depth {base_depth}, iso-node budget per position")
    print(f"baseline: mean loss {sum(bl)/n:.2f}cp, "
          f">20cp {100*sum(x>20 for x in bl)/n:.1f}%, "
          f"{sum(x[1] for x in base):,} nodes")
    print(f"\n{'config':<16}{'depth':>7}{'nodes':>8}{'>20cp':>9}{'d_mean':>9}{'t':>7}")
    for name, tree in configs:
        res = run(tree, "iso", base_depth, tmp, bud)
        cl = losses(res, fens, ref)
        d = [a - b for a, b in zip(cl, bl)]
        mean = sum(d) / n
        sd = (sum((x - mean) ** 2 for x in d) / (n - 1)) ** 0.5
        se = sd / n ** 0.5
        dep = sum(x[2] for x in res) / n
        nod = sum(x[1] for x in res)
        print(f"{name:<16}{dep:>7.2f}{nod/sum(x[1] for x in base):>7.2f}x"
              f"{100*sum(x>20 for x in cl)/n:>8.1f}%{mean:>9.3f}"
              f"{mean/se if se else 0:>7.2f}")


if __name__ == "__main__":
    main()

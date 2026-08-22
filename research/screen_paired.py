"""Paired screening: the difference, not the rate.

`screen_ref.py` reports each configuration's blunder rate with its own standard
error -- about 0.8% at 3.5k positions, which resolves roughly 15 Elo. That is
enough to triage a pruning change but far too blunt to tune a weight, where a
single coefficient might move the rate by 0.1%.

The fix is the one `abgate` already uses for games: common random numbers. Two
configurations see the SAME positions and agree on most of them, so every
position where they agree contributes exactly zero to the difference. The
standard error of the paired difference is therefore far smaller than the
standard error of either rate -- typically several times smaller, because the
variance comes only from the positions where the two actually diverge.

Reported per configuration, against the baseline on identical positions:

    d_mean    mean of (loss_cand - loss_base), in cp. Negative is better.
    se        standard error of that mean
    t         d_mean / se; |t| > 2 is a real difference
    diff      how many positions the two configurations played differently
              -- if this is near zero the change is inert and the screen is
              correctly saying nothing rather than pretending to

Losses are clamped (CLAMP, default 300cp) because mate scores otherwise
dominate: an unclamped mean once carried a standard error of 89.6.

Usage: screen_paired.py <table.jsonl> <depth> <name=tree> [...]
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


def losses_for(tree, depth, fens, ref, tmp):
    env = dict(os.environ, PYTHONPATH=".")
    r = subprocess.run([PY, "-c", PROBE, str(depth), str(tmp)],
                       cwd=str(tree), capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-2000:])
        raise SystemExit(f"probe failed in {tree}")
    res = json.loads(r.stdout.strip().splitlines()[-1])
    out, moves = [], []
    for fen, (uci, _) in zip(fens, res):
        row = ref[fen]
        tab = row["moves"]
        best = tab[row["best"]]
        got = tab[uci] if uci in tab else min(tab.values())
        out.append(min(CLAMP, max(0, best - got)))
        moves.append(uci)
    return out, moves, sum(x[1] for x in res)


def main():
    table_path = Path(sys.argv[1])
    depth = int(sys.argv[2])
    configs = []
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

    base_l, base_m, base_n = losses_for(CC, depth, fens, ref, tmp)
    print(f"{len(fens)} positions, depth {depth}, clamp {CLAMP}cp")
    print(f"baseline: mean loss {statistics.mean(base_l):.2f}cp, "
          f"{base_n:,} nodes")
    print(f"{'config':<16}{'vs base':>9}{'d_mean':>9}{'se':>7}{'t':>7}{'diff':>7}")
    for name, tree in configs:
        L, M, N = losses_for(tree, depth, fens, ref, tmp)
        d = [a - b for a, b in zip(L, base_l)]
        ndiff = sum(1 for a, b in zip(M, base_m) if a != b)
        se = statistics.stdev(d) / (len(d) ** 0.5) if len(d) > 1 else 0.0
        m = statistics.mean(d)
        t = m / se if se > 0 else 0.0
        print(f"{name:<16}{N / base_n:>8.2f}x{m:>9.3f}{se:>7.3f}{t:>7.2f}{ndiff:>7}")


if __name__ == "__main__":
    main()

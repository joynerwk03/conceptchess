"""Re-tune the drawishness weights against DECISIVE-game loss.

Tuned against all-games loss they went to 0.05 -- a near-total damping, which
minimises forecast error on drawn games and costs Elo, because an evaluation of
exactly zero gives the search no reason to keep pressing a position the opponent
may yet misplay. "Theoretically drawn" and "worth nothing against a fallible
opponent" are different claims, and only the first is what the tuner was asked
about.

Decisive games are the ones where a choice mattered. Optimising the same weights
against those should find damping that reflects PRACTICAL winning chances.
"""
import json
import random
import subprocess

CC = "/home/joynerwk03/mission-control/projects/conceptchess"
WT = CC + "/research/worktrees/dev_scale"

rows = [json.loads(l) for l in open(CC + "/research/data/texel5.jsonl")]
random.Random(11).shuffle(rows)
rows = rows[:30000]
res = [r["res"] for r in rows]
json.dump([r["fen"] for r in rows], open("/tmp/td_fens.json", "w"))
dec = [i for i, r in enumerate(res) if r != 0.5]

KEYS = ["scale.no_pawns", "scale.wrong_rook_pawn",
        "scale.opposite_bishops", "scale.single_pawn"]


def evals(cfg, kpk_on=True):
    sets = "\n".join(f'wm.W[{k!r}] = {v}' for k, v in cfg.items())
    code = f"""
import sys, json
sys.path.insert(0, {WT!r})
import chess
from engine import weights as wm
{sets}
if not {kpk_on}:
    from engine.concepts import draw_scale as dsm
    dsm.kpk.probe = lambda b: (False, False)
from engine.evaluation import evaluate, clear_caches
clear_caches()
fens = json.load(open('/tmp/td_fens.json'))
print(json.dumps([evaluate(chess.Board(f)) for f in fens]))
"""
    out = subprocess.run([CC + "/.venv/bin/python", "-c", code],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(out.stderr[-2000:])
    return json.loads(out.stdout)


def dloss(ev):
    s = 0.0
    for i in dec:
        p = 1.0 / (1.0 + 10.0 ** (-ev[i] / (0.8 * 400.0)))
        s += (p - res[i]) * (p - res[i])
    return s / len(dec)


off = dloss(evals({k: 1.0 for k in KEYS}, kpk_on=False))
print(f"decisive-game loss with everything OFF: {off:.6f}\n")

cur = {k: 1.0 for k in KEYS}
best = off
print("coordinate descent on decisive-game loss (1.0 = no damping at all)")
for p in range(8):
    improved = False
    for k in KEYS:
        for cand in (cur[k] - 0.1, cur[k] + 0.1):
            if not (0.0 <= cand <= 1.0) or abs(cand - cur[k]) < 1e-9:
                continue
            trial = dict(cur)
            trial[k] = round(cand, 3)
            l = dloss(evals(trial))
            if l < best - 1e-9:
                best, cur[k], improved = l, round(cand, 3), True
                print(f"  pass {p+1}: {k} -> {cur[k]:.2f}   decisive loss {l:.6f}")
    if not improved:
        print(f"  converged after {p+1} passes")
        break

gain = 100 * (off - best) / off
print(f"\nfinal decisive-game loss {best:.6f}  ({gain:+.3f}% vs off, "
      f"about {4.7*gain:+.1f} Elo)")
for k in KEYS:
    print(f"  {k:28s} {cur[k]:.2f}")

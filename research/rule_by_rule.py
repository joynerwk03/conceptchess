"""Which drawishness rules help on DECISIVE games, and which only flatter the
forecast on games that were drawn anyway?

The bundle as a whole is -0.615% on decisive games -- slightly harmful. But it
mixes two very different kinds of rule:

  * FACTS: no_pawns, wrong_rook_pawn, KPK. Theoretically drawn; damping them
    cannot cost anything real, because there was nothing to win.
  * HEURISTICS: opposite_bishops, single_pawn. These fire on plenty of positions
    that are perfectly winnable, and scaling those toward zero removes the very
    gradient that makes the engine try.

If the facts are neutral-or-positive and the heuristics are the negative, the
salvage is obvious: keep the knowledge, drop the guesses.
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
json.dump([r["fen"] for r in rows], open("/tmp/rbr_fens.json", "w"))
dec = [i for i, r in enumerate(res) if r != 0.5]

SETTINGS = {
    "everything OFF":       dict(no_pawns=1.0, wrong=1.0, ocb=1.0, single=1.0),
    "facts only (no_pawns + wrong rook pawn + KPK)":
                            dict(no_pawns=0.05, wrong=0.05, ocb=1.0, single=1.0),
    "heuristics only (opposite bishops + single pawn)":
                            dict(no_pawns=1.0, wrong=1.0, ocb=0.65, single=0.65),
    "everything ON (what was gated)":
                            dict(no_pawns=0.05, wrong=0.05, ocb=0.65, single=0.65),
}


def evals(cfg, kpk_on):
    code = f"""
import sys, json
sys.path.insert(0, {WT!r})
import chess
from engine import weights as wm
wm.W["scale.no_pawns"] = {cfg['no_pawns']}
wm.W["scale.wrong_rook_pawn"] = {cfg['wrong']}
wm.W["scale.opposite_bishops"] = {cfg['ocb']}
wm.W["scale.single_pawn"] = {cfg['single']}
if not {kpk_on}:
    from engine.concepts import draw_scale as dsm
    dsm.kpk.probe = lambda b: (False, False)
from engine.evaluation import evaluate, clear_caches
clear_caches()
fens = json.load(open('/tmp/rbr_fens.json'))
print(json.dumps([evaluate(chess.Board(f)) for f in fens]))
"""
    out = subprocess.run([CC + "/.venv/bin/python", "-c", code],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(out.stderr[-2000:])
    return json.loads(out.stdout)


def loss(ev, idx):
    s = 0.0
    for i in idx:
        p = 1.0 / (1.0 + 10.0 ** (-ev[i] / (0.8 * 400.0)))
        s += (p - res[i]) * (p - res[i])
    return s / len(idx)


allidx = list(range(len(res)))
base = evals(SETTINGS["everything OFF"], kpk_on=False)
b_all, b_dec = loss(base, allidx), loss(base, dec)

print(f"{'setting':50s} {'all %':>9s} {'DECISIVE %':>12s} {'~Elo':>8s}")
print("-" * 82)
for name, cfg in SETTINGS.items():
    kpk_on = "facts" in name or "everything ON" in name
    ev = evals(cfg, kpk_on=kpk_on)
    ga = 100 * (b_all - loss(ev, allidx)) / b_all
    gd = 100 * (b_dec - loss(ev, dec)) / b_dec
    print(f"{name:50s} {ga:+9.3f} {gd:+12.3f} {4.7*gd:+8.1f}")

print()
print("Elo estimated at 4.7 per 1% of DECISIVE-game loss -- the rate that")
print("predicted the phase3 stack to +0.1 Elo and phase4 to within noise.")

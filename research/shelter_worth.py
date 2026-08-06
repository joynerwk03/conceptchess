"""What is the castling-aware king shelter worth, on DECISIVE-game loss?

Not a weight change, so the tuning screen does not apply -- this is a structural
change to how the shelter is computed. Straight before/after on the metric that
predicts Elo (4.7 per 1%, which called the phase3 stack to within 0.1).
"""
import json
import random
import subprocess

import chess

CC = "/home/joynerwk03/mission-control/projects/conceptchess"
WT = CC + "/research/worktrees/dev_shelter"

rows = [json.loads(l) for l in open(CC + "/research/data/texel5.jsonl")]
random.Random(11).shuffle(rows)
rows = rows[:30000]
res = [r["res"] for r in rows]
json.dump([r["fen"] for r in rows], open("/tmp/sh_fens.json", "w"))
dec = [i for i, r in enumerate(res) if r != 0.5]
allidx = list(range(len(res)))


def evals(root):
    code = ("import sys, json\n"
            "sys.path.insert(0, %r)\n"
            "import chess\n"
            "from engine.evaluation import evaluate, clear_caches\n"
            "clear_caches()\n"
            "fens = json.load(open('/tmp/sh_fens.json'))\n"
            "print(json.dumps([evaluate(chess.Board(f)) for f in fens]))\n" % root)
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


a, b = evals(CC), evals(WT)
# How many positions does this even touch? A castling-rights-aware shelter can
# only differ where somebody still has rights.
touched = sum(1 for x, y in zip(a, b) if abs(x - y) > 1e-9)

ga = 100 * (loss(a, allidx) - loss(b, allidx)) / loss(a, allidx)
gd = 100 * (loss(a, dec) - loss(b, dec)) / loss(a, dec)
print(f"positions where the eval changes: {touched} of {len(a)} "
      f"({100*touched/len(a):.1f}%)")
print(f"all-games loss      {ga:+.3f}%")
print(f"DECISIVE-game loss  {gd:+.3f}%   ~{4.7*gd:+.1f} Elo")

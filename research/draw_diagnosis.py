"""Why did 2.264% of outcome loss buy +1.1 Elo instead of +15?

Hypothesis: the Texel loss rewards being RIGHT, and Elo rewards CHOOSING WELL,
and those come apart exactly where the drawishness modifier does its work.
Telling a drawn rook-versus-bishop from +170 to 0.00 is a huge improvement in
forecast and no improvement at all in result -- the game was drawn either way.

Test: split the same positions by the outcome of the game they came from, and
see where the loss gain lives. If it is concentrated in DRAWN games, the term
improved prediction without improving decisions and the loss-to-Elo rate
calibrated on bundle A simply does not apply to it.
"""
import json
import random
import subprocess

import chess

CC = "/home/joynerwk03/mission-control/projects/conceptchess"
WT = CC + "/research/worktrees/dev_scale"

rows = [json.loads(l) for l in open(CC + "/research/data/texel5.jsonl")]
random.Random(11).shuffle(rows)
rows = rows[:30000]
fens = [r["fen"] for r in rows]
res = [r["res"] for r in rows]
json.dump(fens, open("/tmp/dd_fens.json", "w"))


def evals(root):
    code = ("import sys, json\n"
            "sys.path.insert(0, %r)\n"
            "import chess\n"
            "from engine.evaluation import evaluate, clear_caches\n"
            "clear_caches()\n"
            "fens = json.load(open('/tmp/dd_fens.json'))\n"
            "print(json.dumps([evaluate(chess.Board(f)) for f in fens]))\n" % root)
    out = subprocess.run([CC + "/.venv/bin/python", "-c", code],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(out.stderr[-2000:])
    return json.loads(out.stdout)


def loss(ev, rs, k):
    s = 0.0
    for e, r in zip(ev, rs):
        p = 1.0 / (1.0 + 10.0 ** (-e / (k * 400.0)))
        s += (p - r) * (p - r)
    return s / len(ev)


base = evals(CC)
new = evals(WT)
K = 0.8

print(f"{'positions from games that were':38s} {'n':>7s} {'before':>10s} "
      f"{'after':>10s} {'gain':>9s}   share of total gain")
print("-" * 96)

total_gain = None
buckets = [("ALL", lambda r: True),
           ("DRAWN  (result 0.5)", lambda r: r == 0.5),
           ("DECISIVE (result 0 or 1)", lambda r: r != 0.5)]
gains = {}
for label, keep in buckets:
    idx = [i for i, r in enumerate(res) if keep(r)]
    b = loss([base[i] for i in idx], [res[i] for i in idx], K)
    v = loss([new[i] for i in idx], [res[i] for i in idx], K)
    # absolute contribution to the overall mean loss, so shares are comparable
    contrib = (b - v) * len(idx) / len(res)
    gains[label] = contrib
    if total_gain is None:
        total_gain = contrib
    share = 100 * contrib / total_gain if total_gain else 0
    print(f"{label:38s} {len(idx):7d} {b:10.6f} {v:10.6f} {100*(b-v)/b:+8.3f}%"
          f"   {share:6.1f}%")

print()
print("If nearly all of the gain sits in DRAWN games, the modifier improved the")
print("engine's forecast without improving its choices -- which is exactly what")
print("+2.264% loss buying +1.1 Elo looks like.")

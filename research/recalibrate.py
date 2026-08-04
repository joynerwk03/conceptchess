"""Recalibrate loss -> Elo on DECISIVE games only.

The rate this session has been planning with -- ~8.5 Elo per 1% of outcome loss
-- was calibrated on one point (bundle A) and has now been falsified by a second
(phase4: 2.264% bought +1.1). The diagnosis is that the Texel loss is a
FORECASTING metric while Elo is a DECISION metric, and the two come apart on
positions whose result was never in doubt.

So compute both rates, over the two changes with real external measurements:

    phase3 stack  = converged taper + bundle A + bundle D   ->  +12.8 Elo
    phase4        = drawishness + history-scaled LMR        ->   +1.1 Elo

If the decisive-games rate is consistent across both where the all-games rate is
not, then decisive-games loss is the screen this project should have been using.
"""
import json
import random
import subprocess

CC = "/home/joynerwk03/mission-control/projects/conceptchess"
PRE_PHASE3 = CC + "/research/worktrees/base_stack2"   # main before the merge
POST_PHASE3 = CC + "/research/worktrees/base_p4"      # main after the merge
PHASE4 = CC + "/research/worktrees/phase4"

rows = [json.loads(l) for l in open(CC + "/research/data/texel5.jsonl")]
random.Random(11).shuffle(rows)
rows = rows[:30000]
res = [r["res"] for r in rows]
json.dump([r["fen"] for r in rows], open("/tmp/rc_fens.json", "w"))


def evals(root):
    code = ("import sys, json\n"
            "sys.path.insert(0, %r)\n"
            "import chess\n"
            "from engine.evaluation import evaluate, clear_caches\n"
            "clear_caches()\n"
            "fens = json.load(open('/tmp/rc_fens.json'))\n"
            "print(json.dumps([evaluate(chess.Board(f)) for f in fens]))\n" % root)
    out = subprocess.run([CC + "/.venv/bin/python", "-c", code],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(out.stderr[-2000:])
    return json.loads(out.stdout)


def loss(ev, rs, k=0.8):
    s = 0.0
    for e, r in zip(ev, rs):
        p = 1.0 / (1.0 + 10.0 ** (-e / (k * 400.0)))
        s += (p - r) * (p - r)
    return s / len(ev)


dec = [i for i, r in enumerate(res) if r != 0.5]


def gains(a, b):
    """(all-games %, decisive-games %) improvement of b over a."""
    la, lb = loss(a, res), loss(b, res)
    da = loss([a[i] for i in dec], [res[i] for i in dec])
    db = loss([b[i] for i in dec], [res[i] for i in dec])
    return 100 * (la - lb) / la, 100 * (da - db) / da


print("evaluating three trees over 30000 positions...", flush=True)
pre = evals(PRE_PHASE3)
post = evals(POST_PHASE3)
p4 = evals(PHASE4)

print(f"\n{len(dec)} of {len(res)} positions come from decisive games\n")
print(f"{'change':16s} {'all-games %':>12s} {'decisive %':>12s} "
      f"{'measured Elo':>13s} {'Elo per 1% all':>15s} {'Elo per 1% dec':>15s}")
print("-" * 92)
for name, a, b, elo in (("phase3 stack", pre, post, 12.8),
                        ("phase4", post, p4, 1.1)):
    ga, gd = gains(a, b)
    ra = elo / ga if abs(ga) > 1e-9 else float("nan")
    rd = elo / gd if abs(gd) > 1e-9 else float("nan")
    print(f"{name:16s} {ga:+12.3f} {gd:+12.3f} {elo:+13.1f} {ra:15.1f} {rd:15.1f}")

print()
print("A rate that is consistent in the last column and wildly inconsistent in")
print("the second-to-last says the screen should be measured on decisive games.")

"""What is the assembled phase3 stack worth, against the untouched baseline?

Individually the three parts measured 1.072% (taper), 0.82% (bundle A) and
~0.95% (bundle D). They are all fitted against the same outcomes, so they
overlap and cannot be added. This measures the stack as it stands, on the same
20k sample and with K fitted on the BASELINE so both sides sit on one scale.
"""
import json
import random
import sys

import chess

CC = "/home/joynerwk03/mission-control/projects/conceptchess"
STACK = CC + "/research/worktrees/dev_stack"

rows = [json.loads(l) for l in open(CC + "/research/data/texel5.jsonl")]
random.Random(11).shuffle(rows)
rows = rows[:20000]
results = [r["res"] for r in rows]
fens = [r["fen"] for r in rows]


def measure(root, k=None):
    """Evaluate the sample with the engine living at `root`, in a subprocess so
    the two module trees cannot contaminate each other."""
    import subprocess
    code = (
        "import sys, json\n"
        "sys.path.insert(0, %r)\n"
        "import chess\n"
        "from engine.evaluation import evaluate, clear_caches\n"
        "clear_caches()\n"
        "fens = json.load(open('/tmp/stack_fens.json'))\n"
        "print(json.dumps([evaluate(chess.Board(f)) for f in fens]))\n" % root
    )
    out = subprocess.run([CC + "/.venv/bin/python", "-c", code],
                         capture_output=True, text=True)
    if out.returncode:
        raise SystemExit(out.stderr[-2000:])
    return json.loads(out.stdout)


def loss(evs, k):
    s = 0.0
    for e, r in zip(evs, results):
        p = 1.0 / (1.0 + 10.0 ** (-e / (k * 400.0)))
        s += (p - r) * (p - r)
    return s / len(evs)


json.dump(fens, open("/tmp/stack_fens.json", "w"))

base_evs = measure(CC)
best_k, base = None, 1e9
for k in (0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
    l = loss(base_evs, k)
    if l < base:
        best_k, base = k, l

stack_evs = measure(STACK)
st = loss(stack_evs, best_k)

print(f"{len(rows)} samples, K={best_k} (fitted on the baseline, held for both)\n")
print(f"baseline (main)      {base:.6f}")
print(f"phase3 stack         {st:.6f}   ({100*(base-st)/base:+.3f}%)")
print()
gain = 100 * (base - st) / base
print("parts measured separately: taper 1.072%, bundle A 0.820%, bundle D ~0.950%")
print(f"                    sum if independent: 2.842%")
print(f"                    actually together:  {gain:.3f}%")
print()
print(f"At ~8-9 Elo per 1%, about {8.5*gain:+.1f} Elo. An 800-game gate resolves")
print("+-19 Elo, so this stack is "
      + ("worth gating externally NOW." if gain >= 2.2 else
         "still under what games can resolve."))

"""Can lazy evaluation be made PROVABLY safe here?

Lazy eval skips the positional terms when a cheap partial score is already far
outside the window. It is standard, and it attacks the right thing: evaluation
is 28.3% of runtime and qsearch stand-pat calls it constantly.

But this project's hard constraint is that the search optimises exactly the
number the breakdown shows. A lazy cutoff that is *usually* safe would break
that -- the search could pick a different move than the displayed evaluation
justifies. It is only admissible with a margin large enough that the skipped
terms provably cannot flip the comparison.

So the question is not "does lazy eval help" but "how big is the positional
contribution, worst case". If the tail is huge, a safe margin never fires and
the idea is dead on arrival; if the tail is tight, there is a real speedup that
costs nothing in faithfulness.

Measures |full eval - (material + PST)| over real positions.
"""
import json
import random
import statistics
import sys

import chess

CC = "/home/joynerwk03/mission-control/projects/conceptchess"
sys.path.insert(0, CC)

from engine.context import EvalContext  # noqa: E402
from engine.concepts import ALL_CONCEPTS  # noqa: E402
from engine.evaluation import evaluate  # noqa: E402

CHEAP = {"material", "placement"}
rest = [c for c in ALL_CONCEPTS if c.name not in CHEAP]

rows = [json.loads(l) for l in open(CC + "/research/data/texel5.jsonl")]
random.Random(19).shuffle(rows)
fens = [r["fen"] for r in rows[:20000]]

diffs = []
for f in fens:
    ctx = EvalContext(chess.Board(f))
    diffs.append(abs(sum(c.score(ctx) for c in rest)))

diffs.sort()
n = len(diffs)
print(f"|positional contribution| over {n} real positions, cp")
for q, lbl in ((0.50, "median"), (0.90, "p90"), (0.99, "p99"),
               (0.999, "p99.9"), (1.0, "MAX")):
    i = min(n - 1, int(q * n))
    print(f"  {lbl:7s} {diffs[i]:8.0f}")
print(f"  mean    {statistics.mean(diffs):8.0f}")
print()
mx = diffs[-1]
print(f"A provably safe lazy margin must be at least the MAX: {mx:.0f}cp.")
print(f"For scale, a queen is 900. A margin of {mx:.0f} fires only when the cheap")
print("score is already more than that outside the window -- which in a normal")
print("search window essentially never happens.")
print()
print("Positions where a 300cp margin would be UNSAFE: "
      f"{100*sum(1 for d in diffs if d > 300)/n:.1f}%")
print("Positions where a 500cp margin would be UNSAFE: "
      f"{100*sum(1 for d in diffs if d > 500)/n:.1f}%")

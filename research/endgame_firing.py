"""Firing rates for endgame terms, on positions that are actually endgames.

`research.firing_rate` reads one middlegame-heavy blunder suite and reports the
new drawishness modifier at 0.0% -- the same reading it gives the dead `ocb`
modifier, and for a completely different reason. An endgame term cannot fire on
middlegame positions, so that number says nothing about it. Killing a term on
that basis would be the measurement mistake this session has been about.

Real game positions from the Texel data, bucketed by how much material is left.
"""
import json
import random
import sys

import chess

WT = sys.argv[1] if len(sys.argv) > 1 else (
    "/home/joynerwk03/mission-control/projects/conceptchess"
    "/research/worktrees/dev_scale")
sys.path.insert(0, WT)

from engine.context import EvalContext  # noqa: E402
from engine.concepts import ALL_MODIFIERS  # noqa: E402

DATA = ("/home/joynerwk03/mission-control/projects/conceptchess"
        "/research/data/texel5.jsonl")

rows = [json.loads(l) for l in open(DATA)]
random.Random(3).shuffle(rows)
rows = rows[:40000]

buckets = {"all positions": lambda n: True,
           "<=12 pieces": lambda n: n <= 12,
           "<=8 pieces (real endgames)": lambda n: n <= 8,
           "<=6 pieces": lambda n: n <= 6}

for mod in ALL_MODIFIERS:
    print(f"modifier: {mod.name}")
    for label, keep in buckets.items():
        n = fired = 0
        reasons = {}
        for r in rows:
            b = chess.Board(r["fen"])
            if not keep(chess.popcount(b.occupied)):
                continue
            n += 1
            ctx = EvalContext(b)
            f = mod.factor(ctx)
            if f != 1.0:
                fired += 1
                why = mod.item_label(ctx)
                reasons[why] = reasons.get(why, 0) + 1
        if n:
            print(f"  {label:30s} {n:6d} positions   fires {100*fired/n:5.2f}%")
            for why, c in sorted(reasons.items(), key=lambda kv: -kv[1]):
                print(f"      {c:5d}  {why}")
        else:
            print(f"  {label:30s} none in sample")
    print()

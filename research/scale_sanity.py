"""Does the drawishness modifier agree with endgame theory?

+2.18% loss over all positions and +29% over real endgames is a large claim from
four hand-written rules. A rule that fires on a WON ending is not a small error:
it would teach the search to throw away wins. Check every classic case by name
before believing the number.
"""
import sys

import chess

sys.path.insert(0, "/home/joynerwk03/mission-control/projects/conceptchess"
                   "/research/worktrees/dev_scale")

from engine.context import EvalContext  # noqa: E402
from engine.concepts.draw_scale import DrawScale  # noqa: E402

ds = DrawScale()

CASES = [
    # fen,                                          should_damp, what it is
    ("8/8/4k3/8/8/4K3/8/6R1 w - - 0 1",             False,  "KR vs K   WON"),
    ("8/8/4k3/8/8/4K3/8/6B1 w - - 0 1",             True,  "KB vs K   DRAW"),
    ("8/8/4k3/8/8/4K3/8/6N1 w - - 0 1",             True,  "KN vs K   DRAW"),
    ("8/8/4k3/8/8/4K3/8/5NN1 w - - 0 1",            True,  "KNN vs K  DRAW (cannot force)"),
    ("8/8/4k3/8/8/4K3/8/5BN1 w - - 0 1",            False, "KBN vs K  WON"),
    ("8/8/4k3/8/8/4K3/8/5BB1 w - - 0 1",            False, "KBB vs K  WON"),
    ("8/8/4k3/8/8/4K3/8/6Q1 w - - 0 1",             False, "KQ vs K   WON"),
    ("8/8/4k3/8/6r1/4K3/8/6Q1 w - - 0 1",           False, "KQ vs KR  WON"),
    ("8/8/4k3/8/6b1/4K3/8/6R1 w - - 0 1",           True,  "KR vs KB  DRAW"),
    ("8/8/4k3/8/6n1/4K3/8/6R1 w - - 0 1",           True,  "KR vs KN  usually DRAW"),
    ("8/8/4k3/8/8/4K3/6rr/6RR w - - 0 1",           False, "KRR vs KRR equal, nobody stronger"),
    ("7k/8/8/8/8/8/P7/K1B5 w - - 0 1",              True,  "KBP vs K, a-pawn, dark bishop: DRAW"),
    ("7k/8/8/8/8/8/P7/K6B w - - 0 1",               False, "KBP vs K, a-pawn, LIGHT bishop h1: WON"),
    ("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1",             True,  "KP vs K   single pawn, hard"),
    ("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", False, "start position"),
]

print(f"{'case':46s} {'factor':>7s}  {'verdict':>8s}  reason")
print("-" * 100)
bad = 0
for fen, should, what in CASES:
    ctx = EvalContext(chess.Board(fen))
    f = ds.factor(ctx)
    damped = f != 1.0
    ok = (damped == should)
    if not ok:
        bad += 1
    print(f"{what:46s} {f:7.2f}  {'ok' if ok else 'WRONG':>8s}  "
          f"{ds.item_label(ctx) if damped else '-'}")
print()
print(f"{bad} disagreements with theory")
print()

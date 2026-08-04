"""Does the eval's *volatile* part predict how much the eval moves under search?

The concept-aware search idea rests on one empirical claim: that the named
decomposition tells us something a single number cannot -- specifically that
threats + king attack are the parts of the score a few plies can erase, while
pawn structure and placement are the parts that stay put.

If that claim is false, the whole direction is dead and costs one script instead
of an 800-game gate. Measured here as: how well does

    vol = |threats| + |king_attack|

predict |search_score(depth d) - static_eval| ?

Compared against the obvious null hypothesis -- that |static_eval| itself, or
the total absolute eval, predicts the swing just as well. The idea only earns an
implementation if vol beats those.
"""
import os
import statistics
import sys

os.environ["CC_THREADS"] = "1"

import chess  # noqa: E402

sys.path.insert(0, "/home/joynerwk03/mission-control/projects/conceptchess")

from engine.context import EvalContext  # noqa: E402
from engine.concepts import ALL_CONCEPTS  # noqa: E402
from engine.evaluation import evaluate  # noqa: E402
from engine.engine import Engine  # noqa: E402

SUITE = ("/home/joynerwk03/mission-control/projects/conceptchess"
         "/research/suites/blunders_v1.epd")
DEPTH = 6

by_name = {c.name: c for c in ALL_CONCEPTS}
VOLATILE = ("threats", "king_attack")
STABLE = ("pawn_structure", "placement", "mobility")

fens = []
for line in open(SUITE):
    line = line.strip()
    if line:
        p = line.split()
        fens.append(" ".join(p[:4]) + " 0 1")

CACHE = "/home/joynerwk03/ccruns/volatility_rows.json"
if os.path.exists(CACHE):
    import json
    rows = [tuple(r) for r in json.load(open(CACHE))]
    fens = []

eng = Engine(use_book=False, use_tablebase=False)
if not fens:
    pass
else:
    rows = []
for fen in fens:
    b = chess.Board(fen)
    if b.is_game_over():
        continue
    ctx = EvalContext(b)
    vol = sum(abs(by_name[n].score(ctx)) for n in VOLATILE)
    stab = sum(abs(by_name[n].score(ctx)) for n in STABLE)
    static = evaluate(b)
    r = eng.best_move(b, movetime=600.0, max_depth=DEPTH)
    # search score is from the side to move; put it in White's frame
    searched = r.score if b.turn == chess.WHITE else -r.score
    if abs(searched) > 5000:      # mate scores are not "eval movement"
        continue
    rows.append((vol, stab, abs(static), abs(searched - static)))

if fens:
    import json
    json.dump(rows, open(CACHE, "w"))

print(f"{len(rows)} positions, search depth {DEPTH}\n")


def corr(xs, ys):
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


swing = [r[3] for r in rows]
print("predictor of |search(d) - static|        correlation")
print("-" * 52)
for label, idx in (("volatile (threats + king attack)", 0),
                   ("stable  (pawns + placement + mob)", 1),
                   ("|static eval|  (the null)", 2)):
    print(f"{label:38s}   {corr([r[idx] for r in rows], swing):+.3f}")

# The decision-relevant view: does the swing actually differ between quiet and
# sharp positions? A correlation can be real and still too small to act on.
rows.sort(key=lambda r: r[0])
third = len(rows) // 3
lo, hi = rows[:third], rows[-third:]
print(f"\nlowest-volatility third:  vol {statistics.mean(r[0] for r in lo):6.1f}"
      f"   median swing {statistics.median(r[3] for r in lo):6.1f}cp")
print(f"highest-volatility third: vol {statistics.mean(r[0] for r in hi):6.1f}"
      f"   median swing {statistics.median(r[3] for r in hi):6.1f}cp")

# The control that decides it. Sharp positions also have bigger evals, and
# |static| is already free to the search -- so the question is not "does vol
# correlate with the swing" but "does vol tell us anything |static| doesn't".
# Partial correlation of vol with swing, holding |static| fixed.
def partial(xs, ys, zs):
    rxy, rxz, ryz = corr(xs, ys), corr(xs, zs), corr(ys, zs)
    den = ((1 - rxz ** 2) * (1 - ryz ** 2)) ** 0.5
    return (rxy - rxz * ryz) / den if den else 0.0


vols = [r[0] for r in rows]
stat = [r[2] for r in rows]
print(f"\npartial corr(volatile, swing | |static eval|) = "
      f"{partial(vols, swing, stat):+.3f}")

# And within a narrow |static| band, so the control is not just linear.
band = [r for r in rows if 50 <= r[2] <= 300]
if len(band) >= 30:
    band.sort(key=lambda r: r[0])
    t = len(band) // 3
    print(f"within |static| in [50,300] ({len(band)} positions):")
    print(f"  low-vol third  median swing {statistics.median(r[3] for r in band[:t]):6.1f}cp")
    print(f"  high-vol third median swing {statistics.median(r[3] for r in band[-t:]):6.1f}cp")

# Pearson is the wrong instrument on a heavy-tailed swing distribution: the two
# controls above disagree precisely because a handful of huge swings dominate
# the means. Rank statistics are what this data supports.
def rank(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    for pos, i in enumerate(order):
        r[i] = float(pos)
    return r


def spearman(xs, ys):
    return corr(rank(xs), rank(ys))


def partial_spearman(xs, ys, zs):
    rx, ry, rz = rank(xs), rank(ys), rank(zs)
    rxy, rxz, ryz = corr(rx, ry), corr(rx, rz), corr(ry, rz)
    den = ((1 - rxz ** 2) * (1 - ryz ** 2)) ** 0.5
    return (rxy - rxz * ryz) / den if den else 0.0


print("\n--- rank statistics (what this distribution actually supports) ---")
print(f"spearman(volatile, swing)                  {spearman(vols, swing):+.3f}")
print(f"spearman(|static|,  swing)                 {spearman(stat, swing):+.3f}")
print(f"spearman(volatile, swing | |static|)       "
      f"{partial_spearman(vols, swing, stat):+.3f}   <-- the decisive number")

# Bootstrap the median-swing gap inside the matched band, so "38 vs 85" comes
# with an interval instead of being one draw from a 36-position sample.
if len(band) >= 30:
    import random
    rng = random.Random(7)
    lo_b, hi_b = band[:t], band[-t:]
    diffs = []
    for _ in range(4000):
        a = statistics.median(rng.choice(lo_b)[3] for _ in lo_b)
        c = statistics.median(rng.choice(hi_b)[3] for _ in hi_b)
        diffs.append(c - a)
    diffs.sort()
    print(f"\nmedian-swing gap (high-vol minus low-vol) inside the band: "
          f"{statistics.median(r[3] for r in hi_b) - statistics.median(r[3] for r in lo_b):+.1f}cp"
          f"   95% [{diffs[100]:+.1f}, {diffs[3899]:+.1f}]")

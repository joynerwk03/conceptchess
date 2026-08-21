"""Gate a change against an EXTERNAL opponent, paired on openings.

Why this exists
---------------
s24 measured the thing that governs all eval work now: two eval concepts gated
at +55 and +29 in SELF-PLAY and transferred ~ZERO against Stockfish. Self-play
rewards fixing our own lineage's blind spots, which an outside opponent never
had. So eval changes have to be judged against an outside opponent -- but a
naive "play A vs Stockfish, then B vs Stockfish, compare" throws away so much
precision that it was never practical.

The fix is common random numbers. Both builds play the SAME openings in the SAME
colours against the SAME strength-limited Stockfish. Opening difficulty then
cancels in the per-opening difference, and since our engine is deterministic at
CC_THREADS=1, what is left is mostly Stockfish's own randomness. The paired
difference is far tighter than differencing two independent score estimates.

  delta_score = mean over game slots i of ( score_B(i) - score_A(i) )

reported as an Elo difference via the logistic derivative at the observed score.
That is the number to judge an eval change by.

Usage:
  git worktree add research/worktrees/base <rev>
  (cd research/worktrees/base && sh core/build.sh)
  python -m research.abgate --games 400 --opponent stockfish:2700 \\
      --baseline-cwd research/worktrees/base --movetime 0.3 --concurrency 8
"""

import argparse
import math
import os
import sys
from pathlib import Path

from research.match import (ROOT, load_book, run_match, trinomial_elo, _elo)

DEFAULT_BOOK = ROOT / "research" / "books" / "uho_1000.epd"


def _elo_slope(p):
    """dElo/dp of the logistic at score fraction p."""
    p = min(max(p, 1e-4), 1 - 1e-4)
    return 400.0 / (math.log(10) * p * (1 - p))


def paired_delta(scores_a, scores_b):
    """(delta_elo, ci, mean_d, n, p_a, p_b) from two runs over the same slots."""
    slots = sorted(set(scores_a) & set(scores_b))
    if len(slots) < 2:
        return None
    diffs = [scores_b[i] - scores_a[i] for i in slots]
    n = len(diffs)
    mean_d = sum(diffs) / n
    var = sum((d - mean_d) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    p_a = sum(scores_a[i] for i in slots) / n
    p_b = sum(scores_b[i] for i in slots) / n
    slope = _elo_slope((p_a + p_b) / 2)
    delta = _elo(p_b) - _elo(p_a)
    return delta, (delta - 1.96 * se * slope, delta + 1.96 * se * slope), mean_d, n, p_a, p_b


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=400,
                   help="games per side (each build plays this many)")
    p.add_argument("--opponent", default="stockfish:2700",
                   help="the EXTERNAL opponent both builds face. Pick an anchor "
                        "near our own strength: information per game is highest "
                        "where the score is near 50%%.")
    p.add_argument("--baseline-cwd", required=True,
                   help="worktree holding the baseline build (must be built)")
    p.add_argument("--movetime", type=float, default=0.3)
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--book", default=str(DEFAULT_BOOK))
    p.add_argument("--opening-offset", type=int, default=0)
    p.add_argument("--threads", default="1")
    args = p.parse_args()

    os.environ["CC_THREADS"] = args.threads
    openings = None if args.book == "none" else load_book(args.book)
    base_cmd = f"cmd:{sys.executable} -m engine.uci"

    common = dict(movetime=args.movetime,
                  concurrency=args.concurrency, openings=openings,
                  progress=False)

    # COUNTERBALANCED ORDER: A1 B1 B2 A2.
    #
    # Both arms use identical openings, colours and slot indices, which removes
    # opening difficulty from the per-slot difference. What that does NOT remove
    # is machine drift, because the arms play at different TIMES. This engine is
    # wall-clock limited at a fixed movetime, so anything else running on the box
    # changes how deep it gets -- an earlier version of this file claimed the
    # engine "is deterministic at CC_THREADS=1", which is true only at a fixed
    # DEPTH. research/noise_floor.sh states the opposite and is the correct one.
    #
    # Running A entirely and then B entirely puts every drift that happens
    # between the phases straight into the reported delta. Splitting each arm in
    # half and playing A B B A gives both arms the same mean position in time, so
    # drift that is linear over the run cancels. The halves use different
    # openings, so no material is repeated.
    half = args.games // 2
    off1 = args.opening_offset
    off2 = args.opening_offset + (half // 2)   # openings are indexed by g//2

    def block(label, cwd, games, offset):
        kw = dict(common, games=games, opening_offset=offset)
        if cwd is not None:
            kw["ours_cwd"] = cwd
        r = run_match(opponent=args.opponent, **kw)
        print(f"  {label}: +{r.wins} ={r.draws} -{r.losses}  "
              f"({100 * r.score / max(r.n, 1):.1f}%)", flush=True)
        return r

    BASE = args.baseline_cwd
    print(f"=== counterbalanced A B B A vs {args.opponent} "
          f"({half} games per block) ===", flush=True)
    a1 = block("A1 baseline", BASE, half, off1)
    b1 = block("B1 current ", None, half, off1)
    b2 = block("B2 current ", None, half, off2)
    a2 = block("A2 baseline", BASE, half, off2)

    def merge(first, second):
        """Second block's slot indices are shifted so they do not collide."""
        out = dict(first.scores)
        out.update({k + half: v for k, v in second.scores.items()})
        return out

    scores_a, scores_b = merge(a1, a2), merge(b1, b2)
    n_a = max(len(scores_a), 1)
    n_b = max(len(scores_b), 1)
    p_a_all = sum(scores_a.values()) / n_a
    p_b_all = sum(scores_b.values()) / n_b

    print("\n" + "=" * 70)
    print(f"A baseline  vs {args.opponent}: {100 * p_a_all:5.1f}%  "
          f"({a1.wins + a2.wins}W {a1.draws + a2.draws}D {a1.losses + a2.losses}L)")
    print(f"B current   vs {args.opponent}: {100 * p_b_all:5.1f}%  "
          f"({b1.wins + b2.wins}W {b1.draws + b2.draws}D {b1.losses + b2.losses}L)")
    print(f"  per-block A {100 * a1.score / max(a1.n, 1):.1f}% / "
          f"{100 * a2.score / max(a2.n, 1):.1f}%   "
          f"B {100 * b1.score / max(b1.n, 1):.1f}% / "
          f"{100 * b2.score / max(b2.n, 1):.1f}%"
          "   (a large A1-A2 or B1-B2 split is machine drift, not the change)")
    pd = paired_delta(scores_a, scores_b)
    if not pd:
        print("not enough paired slots")
        return
    delta, ci, mean_d, n, p_a, p_b = pd
    print("-" * 70)
    print(f"PAIRED external delta over {n} shared slots: {delta:+.1f} Elo  "
          f"95% [{ci[0]:+.1f}, {ci[1]:+.1f}]")
    print(f"  (score {100 * p_a:.1f}% -> {100 * p_b:.1f}%, mean per-slot "
          f"difference {mean_d:+.4f})")
    print("=" * 70)
    if ci[0] > 0:
        print("VERDICT: externally positive (CI clears zero).")
    elif ci[1] < 0:
        print("VERDICT: externally NEGATIVE.")
    else:
        print("VERDICT: not distinguishable from zero externally.")


if __name__ == "__main__":
    main()

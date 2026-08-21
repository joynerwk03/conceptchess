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

    # INTERLEAVED. Both arms go through ONE concurrency pool, so every
    # disturbance hits them at the same moment:
    #
    #     g:      0     1     2     3     4    ...
    #     arm:    A     A     B     B     A         (g//2) % 2
    #     colour: w     b     w     b     w         g % 2
    #     opening o     o     o     o     o+1       g // 4
    #
    # The blocked design this replaces (A1 B1 B2 A2) cancels LINEAR drift only;
    # B held both middle slots, so a mid-run dip landed entirely on it and read
    # as -28.3 Elo on an anchor where the stable reading was -3.3.
    #
    # --games N still means games per side: 2N games over N/2 openings, and both
    # arms are scored on the same N (opening, colour) slots.
    BASE = args.baseline_cwd
    total = 2 * args.games

    def arm_cwd(g):
        return BASE if (g // 2) % 2 == 0 else None      # None = this tree (B)

    def opening_of(g):
        return args.opening_offset + g // 4

    def slot_of(g):
        return 2 * (g // 4) + (g % 2)                   # (opening, colour)

    print(f"=== interleaved A/B vs {args.opponent}: {total} games, "
          f"{args.games} per arm, {args.games // 2} openings ===", flush=True)
    res = run_match(opponent=args.opponent, games=total, movetime=args.movetime,
                    concurrency=args.concurrency, openings=openings,
                    ours_cwd_fn=arm_cwd, opening_fn=opening_of, progress=False)

    scores_a, scores_b = {}, {}
    for g, sc in res.scores.items():
        (scores_a if (g // 2) % 2 == 0 else scores_b)[slot_of(g)] = sc

    n_a, n_b = max(len(scores_a), 1), max(len(scores_b), 1)
    p_a_all = sum(scores_a.values()) / n_a
    p_b_all = sum(scores_b.values()) / n_b

    def half(d, first):
        cut = args.games // 2
        v = [x for k, x in d.items() if (k < cut) == first]
        return 100 * sum(v) / max(len(v), 1)

    print("\n" + "=" * 70)
    print(f"A baseline  vs {args.opponent}: {100 * p_a_all:5.1f}%  ({n_a} slots)")
    print(f"B current   vs {args.opponent}: {100 * p_b_all:5.1f}%  ({n_b} slots)")
    print(f"  first/second half   A {half(scores_a, True):.1f}% / "
          f"{half(scores_a, False):.1f}%   B {half(scores_b, True):.1f}% / "
          f"{half(scores_b, False):.1f}%")
    print("   (both arms should move TOGETHER; that is drift, and interleaving "
          "means it no longer favours either)")
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

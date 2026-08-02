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

    common = dict(games=args.games, movetime=args.movetime,
                  concurrency=args.concurrency, openings=openings,
                  opening_offset=args.opening_offset, progress=False)

    # Both runs use identical openings, colours and slot indices; only the build
    # on our side changes. That is what makes the per-slot difference meaningful.
    print(f"=== A: baseline ({args.baseline_cwd}) vs {args.opponent} ===", flush=True)
    res_a = run_match(opponent=args.opponent, ours_cwd=args.baseline_cwd, **common)
    print(f"  A: +{res_a.wins} ={res_a.draws} -{res_a.losses}  "
          f"({100 * res_a.score / max(res_a.n, 1):.1f}%)", flush=True)

    print(f"\n=== B: current tree vs {args.opponent} ===", flush=True)
    res_b = run_match(opponent=args.opponent, **common)
    print(f"  B: +{res_b.wins} ={res_b.draws} -{res_b.losses}  "
          f"({100 * res_b.score / max(res_b.n, 1):.1f}%)", flush=True)

    print("\n" + "=" * 70)
    for name, res in (("A baseline", res_a), ("B current ", res_b)):
        elo, ci = res.elo()
        print(f"{name}  vs {args.opponent}: {100 * res.score / max(res.n, 1):5.1f}%  "
              f"(elo vs anchor {elo:+.0f} [{ci[0]:+.0f},{ci[1]:+.0f}])")
    pd = paired_delta(res_a.scores, res_b.scores)
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

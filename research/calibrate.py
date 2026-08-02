"""External Elo calibration against Stockfish anchors, tracked over time.

The LOG's standing lesson is that self-play gates measure "did we fix our own
lineage's blind spots" -- the +84 Elo of eval concepts in session 24 transferred
~ZERO against Stockfish, while the search work transferred. So the only
trustworthy strength number is against an OUTSIDE opponent, and it needs to be
repeatable rather than eyeballed once a session.

Method
------
Play the engine against several strength-limited Stockfish anchors, then fit OUR
rating by maximum likelihood over all anchors at once, instead of reading off
where the score curve crosses 50% (which throws away every anchor but the two
nearest and has no error bar at all). Draws are modelled explicitly with the
BayesElo draw model and a single nuisance "draw Elo" fitted jointly:

    P(win)  = 1 / (1 + 10^((-delta + draw_elo)/400))
    P(loss) = 1 / (1 + 10^(( delta + draw_elo)/400))
    P(draw) = 1 - P(win) - P(loss)         delta = our_rating - anchor_rating

Two intervals are reported, and they are meant to be compared:

* **profile likelihood** -- the model-based 95% interval on our rating, with
  draw_elo maximised out at each candidate rating (the right way to handle a
  nuisance parameter). Tight, but only as good as the logistic model.
* **paired bootstrap** -- resample the colour-swapped game PAIRS with
  replacement and refit. Assumption-light: it accounts both for the correlation
  inside a pair (the same opening played twice) and for model misfit. If the two
  intervals disagree materially, trust the bootstrap and distrust the model.

Sizing: 40 games/anchor gave ~+-100 Elo, far too loose for the +20-30 effects the
gates now chase. `--target-ci` just reports whether the run met the width you
asked for; ~150 games/anchor over 4 anchors is the ballpark for +-25.

Relation to research/ladder_anchor.py
-------------------------------------
ladder_anchor.py fits a rating from results typed in BY HAND, and models the
score as a binomial -- i.e. it treats a 0/0.5/1 chess score as a count of coin
flips, the same draw-blind approximation that was already fixed for match gates
(see `trinomial_elo` in research/match.py). It stays as the reproducible record
of the historical anchors in research/data/ladder_anchors.json. This module is
the successor for new measurements: it RUNS the ladder (the piece the ROADMAP
listed as missing), models draws properly, and appends every run to
research/data/elo_history.json so external strength is tracked over time rather
than re-derived from scratch each session.

Usage
-----
  python -m research.calibrate --games 160 --movetime 0.3 --concurrency 8 \
      --label "post-search-stack"
  python -m research.calibrate --show          # print the tracked history
"""

import argparse
import json
import math
import os
import platform
import random
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from research.match import load_book, run_match

ROOT = Path(__file__).parent.parent
HISTORY = ROOT / "research" / "data" / "elo_history.json"
DEFAULT_BOOK = ROOT / "research" / "books" / "uho_1000.epd"

# Bracket the engine (~2725 as of session 25). Two reasons this set is tight and
# fixed rather than wide:
#   * information: a game against an anchor we score 20% or 80% against says far
#     less about our rating than one near 50%, so distant anchors mostly burn CPU;
#   * misfit: the s25 pilot measured residuals of +4.8% at SF-2500 and -8.7% at
#     SF-2900 -- our score curve is STEEPER than the logistic, so a wide ladder
#     drags the single fitted number around depending on which anchors are in it.
# Keeping the same three anchors every run makes whatever misfit remains a
# constant offset that cancels when comparing one run to the next, which is what
# a tracking instrument needs.
DEFAULT_ANCHORS = [2600, 2700, 2800]

EPS = 1e-12
CHI2_95 = 3.841          # 1 df


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------

def _probs(delta, draw_elo):
    """(P(win), P(draw), P(loss)) for a rating advantage of `delta`."""
    pw = 1.0 / (1.0 + 10 ** ((-delta + draw_elo) / 400.0))
    pl = 1.0 / (1.0 + 10 ** ((delta + draw_elo) / 400.0))
    return max(pw, EPS), max(1.0 - pw - pl, EPS), max(pl, EPS)


def loglik(rating, draw_elo, results):
    """Trinomial log-likelihood. results: [(anchor_elo, w, d, l), ...]"""
    total = 0.0
    for anchor, w, d, l in results:
        pw, pd, pl = _probs(rating - anchor, draw_elo)
        total += w * math.log(pw) + d * math.log(pd) + l * math.log(pl)
    return total


def _scan_max(f, lo, hi, steps=80, rounds=4):
    """Maximise a smooth 1-D function by coarse-to-fine scanning.

    Scanning rather than golden-section on purpose: with saturated anchors the
    likelihood can be very flat, and a bracketing method can walk off the plateau
    in the wrong direction.
    """
    best_x, best_y = lo, f(lo)
    for _ in range(rounds):
        step = (hi - lo) / steps
        for i in range(steps + 1):
            x = lo + i * step
            y = f(x)
            if y > best_y:
                best_x, best_y = x, y
        lo, hi = best_x - 2 * step, best_x + 2 * step
    return best_x, best_y


def profile(rating, results, de_lo=1.0, de_hi=1200.0):
    """max over draw_elo of loglik(rating, draw_elo) -- the profile likelihood."""
    _, ll = _scan_max(lambda de: loglik(rating, de, results), de_lo, de_hi)
    return ll


def fit(results, r_lo=1000.0, r_hi=4000.0):
    """Maximum-likelihood (rating, draw_elo, logL)."""
    rating, ll = _scan_max(lambda r: profile(r, results), r_lo, r_hi)
    draw_elo, _ = _scan_max(lambda de: loglik(rating, de, results), 1.0, 1200.0)
    return rating, draw_elo, ll


def profile_ci(results, rating_hat, ll_max, span=800.0):
    """95% profile-likelihood interval: where 2*(llmax - ll) crosses chi2(1)."""
    target = ll_max - CHI2_95 / 2.0

    def edge(direction):
        lo, hi = 0.0, span                       # offset from rating_hat
        if profile(rating_hat + direction * hi, results) > target:
            return rating_hat + direction * hi   # never crosses: unbounded-ish
        for _ in range(50):
            mid = (lo + hi) / 2
            if profile(rating_hat + direction * mid, results) > target:
                lo = mid
            else:
                hi = mid
        return rating_hat + direction * (lo + hi) / 2

    return edge(-1), edge(+1)


def bootstrap_ci(pair_counts, draw_elo, iters=600, seed=12345):
    """95% CI by resampling colour-swapped PAIRS with replacement.

    pair_counts: {anchor_elo: [(w, d, l), ...]} -- one triple per pair, the two
    games of that pair summed. Resampling pairs (not games) keeps the two halves
    of an opening together, which is the correlation the per-game interval misses.

    draw_elo is held at the full-sample estimate rather than re-profiled per
    replicate: it is a nuisance parameter that barely moves under resampling, and
    profiling it 600 times over costs ~300x more for no measurable change in the
    interval.
    """
    rng = random.Random(seed)
    fits = []
    for _ in range(iters):
        results = []
        for anchor, pairs in pair_counts.items():
            if not pairs:
                continue
            w = d = l = 0
            for _ in range(len(pairs)):
                pw, pd, pl = pairs[rng.randrange(len(pairs))]
                w += pw
                d += pd
                l += pl
            results.append((anchor, w, d, l))
        if len(results) < 2:
            return None
        r, _ = _scan_max(lambda x: loglik(x, draw_elo, results), 1000.0, 4000.0)
        fits.append(r)
    fits.sort()
    lo = fits[int(0.025 * len(fits))]
    hi = fits[min(len(fits) - 1, int(0.975 * len(fits)))]
    return lo, hi


# --------------------------------------------------------------------------
# running the anchors
# --------------------------------------------------------------------------

def _pair_counts(res):
    """MatchResult -> [(w, d, l)] per colour-swapped pair."""
    out = []
    for k in range(res.games // 2):
        a, b = res.scores.get(2 * k), res.scores.get(2 * k + 1)
        if a is None or b is None:
            continue                       # incomplete pair: unusable for pairing
        w = sum(1 for s in (a, b) if s == 1)
        l = sum(1 for s in (a, b) if s == 0)
        out.append((w, 2 - w - l, l))
    return out


def stockfish_id():
    path = shutil.which("stockfish")
    if not path:
        sys.exit("stockfish not found on PATH")
    import chess.engine
    eng = chess.engine.SimpleEngine.popen_uci(path)
    try:
        return eng.id.get("name", "stockfish"), path
    finally:
        eng.quit()


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


def load_history():
    if HISTORY.exists():
        return json.loads(HISTORY.read_text())
    return []


def show_history():
    hist = load_history()
    if not hist:
        print(f"no history yet at {HISTORY}")
        return
    print(f"{'date':<12} {'commit':<9} {'tc':>7} {'games':>6} {'elo':>6}  "
          f"{'95% CI':>13}  label")
    for h in hist:
        ci = h.get("ci") or [0, 0]
        print(f"{h.get('date', ''):<12} {str(h.get('commit')):<9} "
              f"{h.get('movetime', 0):>6}s {h.get('games', 0):>6} "
              f"{h.get('elo', 0):>6.0f}  {ci[0]:>6.0f}..{ci[1]:<6.0f} "
              f"{h.get('label', '')}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--anchors", default=",".join(str(a) for a in DEFAULT_ANCHORS),
                   help="comma-separated Stockfish UCI_Elo anchors")
    p.add_argument("--games", type=int, default=160,
                   help="games per anchor (must be even: games are colour-swapped pairs)")
    p.add_argument("--movetime", type=float, default=0.3)
    p.add_argument("--concurrency", type=int, default=1,
                   help="parallel games; validate the value with the A-vs-identical-A "
                        "check in research.match before trusting it")
    p.add_argument("--book", default=str(DEFAULT_BOOK),
                   help="opening book (default UHO). 'none' uses the built-in "
                        "balanced list, but those 10 lines get replayed many times "
                        "at these game counts, which correlates the sample.")
    p.add_argument("--opening-offset", type=int, default=0)
    p.add_argument("--label", default="", help="note stored with the history entry")
    p.add_argument("--target-ci", type=float, default=25.0,
                   help="report whether the achieved half-width met this")
    p.add_argument("--no-record", action="store_true", help="do not append to history")
    p.add_argument("--bootstrap", type=int, default=600, help="bootstrap replicates (0 to skip)")
    p.add_argument("--show", action="store_true", help="print tracked history and exit")
    p.add_argument("--quiet", action="store_true", help="suppress per-game lines")
    args = p.parse_args()

    if args.show:
        show_history()
        return

    if args.games % 2:
        sys.exit("--games must be even (games are played as colour-swapped pairs)")

    anchors = [int(a) for a in args.anchors.split(",") if a.strip()]
    openings = None if args.book == "none" else load_book(args.book)
    sf_name, sf_path = stockfish_id()

    print(f"calibrating vs {sf_name}  ({len(anchors)} anchors x {args.games} games "
          f"@ {args.movetime}s, CC_THREADS={os.environ.get('CC_THREADS')}, "
          f"concurrency {args.concurrency})")
    if openings:
        print(f"book: {len(openings)} openings from {args.book}")

    results, pair_counts, per_anchor = [], {}, []
    for anchor in anchors:
        print(f"\n--- vs Stockfish {anchor} ---", flush=True)
        res = run_match(games=args.games, opponent=f"stockfish:{anchor}",
                        movetime=args.movetime, concurrency=args.concurrency,
                        openings=openings, opening_offset=args.opening_offset,
                        progress=not args.quiet)
        if res.n == 0:
            print(f"  no games completed vs {anchor}; skipping")
            continue
        results.append((anchor, res.wins, res.draws, res.losses))
        pair_counts[anchor] = _pair_counts(res)
        per_anchor.append({"elo": anchor, "w": res.wins, "d": res.draws,
                           "l": res.losses, "score_pct": 100 * res.score / res.n})
        print(f"  vs {anchor}: +{res.wins} ={res.draws} -{res.losses}  "
              f"({100 * res.score / res.n:.1f}%)", flush=True)

    if len(results) < 2:
        sys.exit("need at least two anchors with completed games to fit a rating")

    rating, draw_elo, ll = fit(results)
    ci = profile_ci(results, rating, ll)
    boot = bootstrap_ci(pair_counts, draw_elo, iters=args.bootstrap) if args.bootstrap else None

    print("\n" + "=" * 66)
    print(f"{'anchor':>7} {'W':>4} {'D':>4} {'L':>4} {'score':>8} {'expected':>9} {'resid':>7}")
    total_games = 0
    for anchor, w, d, l in results:
        n = w + d + l
        total_games += n
        obs = (w + 0.5 * d) / n
        pw, pd, pl = _probs(rating - anchor, draw_elo)
        exp = pw + 0.5 * pd
        print(f"{anchor:>7} {w:>4} {d:>4} {l:>4} {100 * obs:>7.1f}% "
              f"{100 * exp:>8.1f}% {100 * (obs - exp):>+6.1f}%")
    print("=" * 66)
    half = (ci[1] - ci[0]) / 2
    print(f"external Elo: {rating:.0f}   95% profile CI [{ci[0]:.0f}, {ci[1]:.0f}] "
          f"(+-{half:.0f})")
    if boot:
        bhalf = (boot[1] - boot[0]) / 2
        print(f"              paired bootstrap 95% CI [{boot[0]:.0f}, {boot[1]:.0f}] "
              f"(+-{bhalf:.0f})")
    print(f"draw Elo: {draw_elo:.0f}   games: {total_games}   logL: {ll:.1f}")
    report_half = max(half, (boot[1] - boot[0]) / 2) if boot else half
    if report_half > args.target_ci:
        need = total_games * (report_half / args.target_ci) ** 2
        print(f"NOTE: +-{report_half:.0f} is wider than the +-{args.target_ci:.0f} target; "
              f"~{need:.0f} games total ({need / max(len(results), 1):.0f}/anchor) "
              f"would be needed at this spread.")

    if args.no_record:
        return
    entry = {
        "date": date.today().isoformat(),
        "commit": git_commit(),
        "label": args.label,
        "elo": round(rating, 1),
        "ci": [round(ci[0], 1), round(ci[1], 1)],
        "ci_bootstrap": [round(boot[0], 1), round(boot[1], 1)] if boot else None,
        "draw_elo": round(draw_elo, 1),
        "games": total_games,
        "movetime": args.movetime,
        "threads": int(os.environ.get("CC_THREADS", "1")),
        "concurrency": args.concurrency,
        "book": None if args.book == "none" else str(Path(args.book).name),
        "opponent": sf_name,
        "anchors": per_anchor,
        "machine": f"{platform.system()} {platform.machine()} / {os.cpu_count()} cpus",
    }
    hist = load_history()
    hist.append(entry)
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(hist, indent=2) + "\n")
    print(f"\nappended to {HISTORY.relative_to(ROOT)} ({len(hist)} entries)")


if __name__ == "__main__":
    main()

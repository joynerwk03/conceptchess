"""Maximum-likelihood Elo anchor from a multi-level Stockfish ladder.

Prior sessions anchored the engine's absolute Elo by playing strength-limited
Stockfish at several UCI_Elo levels and fitting one engine rating E to all
levels at once (research/data/ladder_anchors.json stores the raw results + the
fitted mle). This is the script that does the fit, so re-anchoring is
reproducible instead of hand-computed.

Model: against a Stockfish level rated e_i, the engine of rating E scores
p_i = 1 / (1 + 10**((e_i - E)/400)) per game (logistic / Elo). With w/d/l at
that level, the score is s_i = w_i + 0.5 d_i out of n_i games. We treat the
score fraction as a binomial observation and maximize the total log-likelihood
over E. The ~95% interval is the profile-likelihood set where 2*(LL_max - LL)
<= 3.84 (chi-square, 1 dof).

Usage:
  # fit from a results dict on the command line (json) ...
  python -m research.ladder_anchor --results '{"2200":[3,6,1],"2400":[6,2,2]}'
  # ... or fit + store a named anchor into ladder_anchors.json
  python -m research.ladder_anchor --results '{...}' --save-as session11
"""

import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
ANCHORS_PATH = HERE / "data" / "ladder_anchors.json"


def _expected(e_level, E):
    return 1.0 / (1.0 + 10.0 ** ((e_level - E) / 400.0))


def loglik(results, E):
    """Total binomial-on-score log-likelihood of engine rating E."""
    ll = 0.0
    for level, (w, d, l) in results.items():
        n = w + d + l
        if n == 0:
            continue
        s = w + 0.5 * d
        p = min(max(_expected(float(level), E), 1e-9), 1 - 1e-9)
        # binomial kernel on the (fractional) score count
        ll += s * math.log(p) + (n - s) * math.log(1 - p)
    return ll


def fit(results, lo=800.0, hi=3200.0, step=1.0):
    """Grid MLE + profile-likelihood 95% interval. Returns (mle, lo95, hi95)."""
    xs = []
    x = lo
    while x <= hi:
        xs.append(x)
        x += step
    lls = [loglik(results, E) for E in xs]
    best_i = max(range(len(xs)), key=lambda i: lls[i])
    mle = xs[best_i]
    ll_max = lls[best_i]
    # profile interval: 2*(ll_max - ll) <= 3.84  ->  ll >= ll_max - 1.92
    thresh = ll_max - 1.92
    lo95 = mle
    for i in range(best_i, -1, -1):
        if lls[i] >= thresh:
            lo95 = xs[i]
        else:
            break
    hi95 = mle
    for i in range(best_i, len(xs)):
        if lls[i] >= thresh:
            hi95 = xs[i]
        else:
            break
    return mle, lo95, hi95


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results", required=True,
                   help='JSON dict {sf_elo: [wins, draws, losses]}')
    p.add_argument("--save-as", default=None,
                   help="store this anchor under the given name in ladder_anchors.json")
    args = p.parse_args()

    raw = json.loads(args.results)
    results = {str(k): [int(x) for x in v] for k, v in raw.items()}
    mle, lo95, hi95 = fit(results)

    ng = sum(sum(v) for v in results.values())
    score = sum(w + 0.5 * d for (w, d, l) in results.values())
    print(f"ladder: {ng} games, overall score {score:.1f}/{ng} "
          f"({100*score/ng:.0f}%)")
    for level in sorted(results, key=lambda k: int(k)):
        w, d, l = results[level]
        n = w + d + l
        print(f"  vs SF {level}: +{w} ={d} -{l}  "
              f"({100*(w+0.5*d)/n:.0f}%, model expects "
              f"{100*_expected(float(level), mle):.0f}%)")
    print(f"\nMLE Elo: {mle:.0f}  (95% profile {lo95:.0f}..{hi95:.0f})")

    if args.save_as:
        anchors = json.loads(ANCHORS_PATH.read_text()) if ANCHORS_PATH.exists() else {}
        anchors[args.save_as] = {
            "results": {k: list(v) for k, v in results.items()},
            "mle": [round(mle), round(lo95), round(hi95)],
        }
        ANCHORS_PATH.write_text(json.dumps(anchors, indent=1))
        print(f"saved anchor '{args.save_as}' to {ANCHORS_PATH}")


if __name__ == "__main__":
    main()

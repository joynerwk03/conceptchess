"""Fit the evaluation towards the engine's own search scores, not game results.

The standing objective regresses on the result of the game a position came from
-- one bit summarising forty subsequent moves. That label is so noisy per
position that ~100k positions are needed to resolve anything, and where it
carries no information at all the weights drift into nonsense: session 32 caught
three such drifts, all in terms that fire only where the result is already
determined.

A search score is a far lower-variance target for the same position, and a
stronger evaluator than the static evaluation being fitted -- which is why depth
wins games. Fitting the static eval towards it moves what the search discovers
into the shallow nodes where pruning and ordering decisions are actually made.

Fitted in WIN-PROBABILITY space rather than centipawns:

    minimise  sum ( sigma(eval) - sigma(search) )^2

because a hundred centipawns of error matters enormously at level material and
almost not at all at +800, and squared centipawn error would spend its effort in
exactly the wrong place.

TWO checks decide whether this is worth anything, and the second is the honest
one:

  * does it reduce the distance to the search scores on HELD-OUT positions?
    (it should -- that is what is being optimised);
  * does it ALSO reduce the ordinary decisive-game OUTCOME loss on those same
    positions? If matching the search improves outcome prediction too, the
    change is likely real. If outcome loss gets worse while search distance
    improves, the fit is chasing the search's quirks and should be discarded.

What this does NOT do is escape self-reference: the labels still come from this
engine. Only an outside evaluator would do that. What it does is remove the
label noise.

    PYTHONPATH=. .venv/bin/python research/fit_to_search.py --workers 15
"""
import argparse
import json
import multiprocessing as mp
import random

import chess
import numpy as np

from research.texel import ROOT
from research.tune_pst_linear import BLOCKS, collect, param_map

KGRID = [0.30, 0.34, 0.38, 0.42, 0.46, 0.50, 0.54, 0.60]


def sig(e, k):
    return 1.0 / (1.0 + np.exp(-(np.log(10.0) / (k * 400.0)) * e))


def outcome_loss(e, res):
    """Ordinary decisive-game loss, at the best K -- the honesty check."""
    return min(float(np.mean((sig(e, k) - res) ** 2)) for k in KGRID)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/labelled.jsonl"))
    ap.add_argument("--holdout", type=float, default=0.35)
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--lr", type=float, default=0.4)
    ap.add_argument("--k", type=float, default=0.46, help="win-prob scale")
    ap.add_argument("--blend", type=float, default=1.0,
                    help="weight on the SEARCH target; the remainder goes on the "
                         "game OUTCOME. 1.0 is pure distillation, 0.0 is ordinary "
                         "Texel tuning, and in between the search score acts as a "
                         "variance reducer while the outcome keeps it honest.")
    ap.add_argument("--out", default=str(ROOT / "research/data/pst_search.json"))
    a = ap.parse_args()

    from engine.concepts import piece_placement as pp

    rows = [json.loads(l) for l in open(a.data)]
    random.Random(31415).shuffle(rows)
    cut = int(len(rows) * (1 - a.holdout))
    fit_rows, hold_rows = rows[:cut], rows[cut:]
    print(f"{len(fit_rows)} fitting positions, {len(hold_rows)} held out "
          f"(search-score labels)")

    fmap, npar = param_map()
    T0 = np.concatenate([np.asarray(getattr(pp, b), dtype=float) for b in BLOCKS])

    print("collecting fit features...")
    fb = [chess.Board(r["fen"]) for r in fit_rows]
    frows, fcols, fvals, fbase = collect(fb, None)
    print("collecting held-out features...")
    hb = [chess.Board(r["fen"]) for r in hold_rows]
    hrows, hcols, hvals, hbase = collect(hb, None)

    fpar, hpar = fmap[fcols], fmap[hcols]
    ftgt = np.asarray([r["sv"] for r in fit_rows], dtype=float)
    htgt = np.asarray([r["sv"] for r in hold_rows], dtype=float)
    fres = np.asarray([r["res"] for r in fit_rows], dtype=float)
    hres = np.asarray([r["res"] for r in hold_rows], dtype=float)
    fdec = fres != 0.5
    hdec = hres != 0.5

    def evals(delta, rows_, par, vals, base):
        return base + np.bincount(rows_, weights=vals * delta[par],
                                  minlength=len(base))

    def sdist(e, tgt):
        return float(np.mean((sig(e, a.k) - sig(tgt, a.k)) ** 2))

    d = np.zeros(npar)
    e0f, e0h = evals(d, frows, fpar, fvals, fbase), evals(d, hrows, hpar, hvals, hbase)
    s0 = sdist(e0h, htgt)
    o0 = outcome_loss(e0h[hdec], hres[hdec])
    print(f"before:  search distance {s0:.6f}   outcome loss {o0:.6f}")

    lim = np.zeros(npar)
    np.maximum.at(lim, fmap, np.abs(T0) * 0.25 + 10.0)

    c = np.log(10.0) / (a.k * 400.0)
    m = np.zeros(npar)
    v = np.zeros(npar)
    b1, b2, eps = 0.9, 0.999, 1e-8
    # Blended target in win-probability space. The search score is precise but
    # only reflects what this engine already believes; the game result is
    # unbiased but carries one bit of information per position. A convex
    # combination keeps the outcome as the thing being predicted while letting
    # the search score damp its variance.
    tgt_p = a.blend * sig(ftgt, a.k) + (1.0 - a.blend) * fres
    n = len(fb)
    for t in range(1, a.steps + 1):
        e = evals(d, frows, fpar, fvals, fbase)
        p = sig(e, a.k)
        g_e = (2.0 * (p - tgt_p) * p * (1.0 - p) * c) / n
        g = np.bincount(fpar, weights=fvals * g_e[frows], minlength=npar)
        m = b1 * m + (1 - b1) * g
        v = b2 * v + (1 - b2) * g * g
        d -= a.lr * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)
        np.clip(d, -lim, lim, out=d)

    dint = np.round(d)
    eh = evals(dint, hrows, hpar, hvals, hbase)
    s1 = sdist(eh, htgt)
    o1 = outcome_loss(eh[hdec], hres[hdec])

    print(f"after:   search distance {s1:.6f}   outcome loss {o1:.6f}")
    print(f"\nsearch distance  {100*(s0-s1)/s0:+.3f}%   <- what was optimised")
    print(f"OUTCOME loss     {100*(o0-o1)/o0:+.3f}%   <- the honest check"
          f"   ~{4.7*100*(o0-o1)/o0:+.1f} Elo")
    if o1 >= o0:
        print("\nOutcome loss did NOT improve: this is chasing the search's own\n"
              "quirks rather than learning chess. Not shipping it.")

    tuned = T0 + dint[fmap]
    json.dump({"tables": {n_: list(tuned[i * 64:(i + 1) * 64])
                          for i, n_ in enumerate(BLOCKS)}},
              open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

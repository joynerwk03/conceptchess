"""Joint fit of EVERY evaluation weight, by iterated local linearisation.

`linfit.py` showed the idea works but only reached 27 of 84 weights: it demanded
exact global linearity, and 57 weights fail that because they sit behind a
threshold, multiply another weighted quantity, or feed the drawishness modifier.

They are still locally linear, though -- almost everything here is piecewise
linear in its own weight. So instead of demanding linearity over the whole
range, take it only where it holds:

    1. measure every weight's coefficient by perturbing it and running the
       REAL evaluate(), exactly as before;
    2. fit all of them jointly by gradient descent, but confined to a TRUST
       REGION -- no weight may move more than a set fraction of itself, which
       is the range the linearisation was measured over;
    3. re-score with the real evaluator. If the held-out loss actually fell,
       accept and widen the region; if it did not, revert and shrink it;
    4. re-measure at the new point and repeat.

Step 3 is what makes this safe. The model is an approximation now, not an
identity, so it is never trusted -- every round is judged by the real evaluator
on held-out data, and a round that fails to deliver is thrown away. The fit can
mislead itself for one round; it cannot ship a regression.

The payoff over coordinate descent is that weights move TOGETHER. Coordinate
descent walks the axes, so two terms that must both move to help -- an isolated
pawn penalty and a passed pawn bonus arguing about the same pawn -- look flat
along each axis alone and never move at all.

    PYTHONPATH=. .venv/bin/python research/linfit_tr.py --rounds 8 --workers 15
"""
import argparse
import json
import multiprocessing as mp
import random

import chess
import numpy as np

from research.texel import ROOT

_B = None
_BASE = None


def _init(fens, wmg, weg):
    global _B, _BASE
    from engine.weights import W, W_EG
    W.update(wmg)
    W_EG.update(weg)
    _B = [chess.Board(f) for f in fens]
    _BASE = _eval_all()


def _eval_all():
    from engine.evaluation import evaluate, clear_caches
    clear_caches()
    return np.asarray([evaluate(b) for b in _B])


def _col(job):
    from engine.weights import W, W_EG
    key, side, step = job
    tgt = W if side == "mg" else W_EG
    orig = tgt[key]
    tgt[key] = orig + step
    e1 = _eval_all()
    tgt[key] = orig
    return (e1 - _BASE) / step


def measure(fens, jobs, workers, wmg, weg):
    """Base evals + one coefficient column per weight, at the current point."""
    with mp.Pool(workers, initializer=_init,
                 initargs=(fens, wmg, weg)) as pool:
        cols = pool.map(_col, jobs, chunksize=1)
    _init(fens, wmg, weg)
    return _BASE.copy(), np.asarray(cols).T


def sigmoid_loss(e, r, k):
    s = 1.0 / (1.0 + np.exp(-(np.log(10.0) / (k * 400.0)) * e))
    return float(np.mean((s - r) ** 2))


# K sets how many centipawns count as decisive. Holding it FIXED makes the
# objective reward inflating the evaluation: at K=0.6, multiplying every score
# by 1.2 "improves" the loss by 0.751% while changing no move the search would
# ever make -- and it silently de-tunes the search's centipawn margins
# (futility, probcut, delta pruning), which are calibrated to the current scale.
# Re-fitting K for every candidate makes a pure rescale worth exactly zero, so
# what the fit can still earn is the part that actually reorders positions.
KGRID = [0.30, 0.34, 0.38, 0.42, 0.44, 0.46, 0.48, 0.50, 0.52,
         0.54, 0.58, 0.62, 0.70, 0.80]


def best_loss(e, r):
    """Loss at the best K for THIS evaluation -- scale-invariant by construction."""
    best = (1e9, KGRID[0])
    for k in KGRID:
        l = sigmoid_loss(e, r, k)
        if l < best[0]:
            best = (l, k)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--positions", type=int, default=50000)
    ap.add_argument("--holdout", type=float, default=0.35)
    ap.add_argument("--rounds", type=int, default=8)
    ap.add_argument("--trust", type=float, default=0.10)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=15)
    ap.add_argument("--min-men", type=int, default=0,
                    help="drop positions with fewer men than this. Positions the "
                         "tablebase already solves at the root are ~17% of the "
                         "data and the eval's accuracy in them cannot affect "
                         "play, so fitting them spends capacity on nothing.")
    ap.add_argument("--target", default="outcome",
                    choices=("outcome", "teacher"),
                    help="'teacher' fits towards an outside evaluator's "
                         "static score (the 'sv' field)")
    ap.add_argument("--test-data", default="",
                    help="independent file for the held-out check; a "
                         "position split of self-play data is not "
                         "independent and inflates the result")
    ap.add_argument("--out", default=str(ROOT / "research/data/linfit_tr.json"))
    a = ap.parse_args()

    from engine.weights import W, W_EG
    from research.texel import TUNABLE

    rows = [json.loads(l) for l in open(a.data)]
    # Decisive games only when the OUTCOME is the target -- a draw carries no
    # gradient there. The teacher labels every position, so draws are usable
    # for fitting even though the held-out check still grades on decisive ones.
    if a.target == "outcome":
        rows = [r for r in rows if r["res"] != 0.5]
    if a.min_men:
        n0 = len(rows)
        rows = [r for r in rows
                if bin(chess.Board(r["fen"]).occupied).count("1") >= a.min_men]
        print(f"dropped {n0-len(rows)} of {n0} positions with <{a.min_men} men "
              f"(the tablebase decides those at the root)")
    random.Random(4242).shuffle(rows)
    rows = rows[:a.positions]
    if a.test_data:
        hold = [json.loads(l) for l in open(a.test_data)]
        hold = [r for r in hold if r["res"] != 0.5]      # graded on outcomes
        random.Random(4242).shuffle(hold)
        hold = hold[:a.positions]
        cut = len(rows)
        fens = [r["fen"] for r in rows] + [r["fen"] for r in hold]
        # The fitting half is pulled towards whichever target was asked for;
        # the held-out half is ALWAYS graded on the game result, because that is
        # the quantity calibrated to Elo. Grading on the teacher would only show
        # that the optimiser works.
        if a.target == "teacher":
            k_ref = 0.46
            fit_lab = 1.0 / (1.0 + np.exp(
                -(np.log(10.0) / (k_ref * 400.0))
                * np.asarray([r["sv"] for r in rows], dtype=float)))
        else:
            fit_lab = np.asarray([r["res"] for r in rows], dtype=float)
        rf = fit_lab
        rh = np.asarray([r["res"] for r in hold], dtype=float)
        print(f"{cut} fitting positions ({a.target} labels), "
              f"{len(hold)} held out from {a.test_data} (independent games)")
    else:
        fens = [r["fen"] for r in rows]
        res = np.asarray([r["res"] for r in rows], dtype=float)
        cut = int(len(rows) * (1 - a.holdout))
        rf, rh = res[:cut], res[cut:]
        print(f"{cut} decisive fitting positions, {len(rows)-cut} held out "
              f"(position split -- NOT independent)")

    names = [(k, "mg") for k in W] + [(k, "eg") for k in W_EG]
    w0 = np.asarray([(W if s == "mg" else W_EG)[k] for k, s in names], float)

    lo = np.empty(len(names))
    hi = np.empty(len(names))
    for i, (k, _s) in enumerate(names):
        v = w0[i]
        if k.startswith("material."):
            lo[i], hi[i] = v * 0.88, v * 1.12
        elif k in TUNABLE:
            f0, f1 = TUNABLE[k]
            lo[i], hi[i] = min(v * f0, v * f1), max(v * f0, v * f1)
        else:
            lo[i], hi[i] = v - abs(v) * 0.5 - 2, v + abs(v) * 0.5 + 2
    print(f"{len(names)} weights (all of them, not just the exactly-linear ones)")

    cur = w0.copy()

    def as_dicts(vec):
        mg, eg = {}, {}
        for (k, s), val in zip(names, vec):
            (mg if s == "mg" else eg)[k] = float(val)
        return mg, eg

    mg, eg = as_dicts(cur)
    _init(fens, mg, eg)
    ev = _BASE
    fit0, best_k = best_loss(ev[:cut], rf)
    hold0, hk0 = best_loss(ev[cut:], rh)
    scale0 = float(np.mean(np.abs(ev)))
    print(f"fit {fit0:.6f} (K={best_k})  held-out {hold0:.6f} (K={hk0})"
          f"  mean|eval| {scale0:.1f}")

    trust = a.trust
    hold_cur, fit_cur = hold0, fit0

    for rnd in range(1, a.rounds + 1):
        mg, eg = as_dicts(cur)
        step = np.maximum(np.abs(cur) * trust * 0.25, 1e-3)
        jobs = [(k, s, float(step[i])) for i, (k, s) in enumerate(names)]
        base, X = measure(fens, jobs, a.workers, mg, eg)
        Xf, Xh = X[:cut], X[cut:]
        bf, bh = base[:cut], base[cut:]
        # Re-fit K at this point and descend with it held there. By the envelope
        # theorem the gradient at the optimal K is the partial derivative with K
        # fixed, so this is the right descent direction -- and the accept test
        # below re-optimises K again, so a step that only inflates the eval buys
        # nothing and gets rejected.
        _, k_round = best_loss(bf, rf)
        c = np.log(10.0) / (k_round * 400.0)

        room = np.maximum(np.abs(cur) * trust, 1e-3)
        dlo = np.maximum(lo - cur, -room)
        dhi = np.minimum(hi - cur, room)

        d = np.zeros(len(names))
        m = np.zeros_like(d)
        v = np.zeros_like(d)
        b1, b2, eps = 0.9, 0.999, 1e-8
        n = Xf.shape[0]
        for t in range(1, a.steps + 1):
            e = bf + Xf @ d
            s = 1.0 / (1.0 + np.exp(-c * e))
            g = Xf.T @ ((2.0 * (s - rf) * s * (1.0 - s) * c) / n)
            m = b1 * m + (1 - b1) * g
            v = b2 * v + (1 - b2) * g * g
            d -= (0.02 * room) * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)
            np.clip(d, dlo, dhi, out=d)

        pred_hold, _ = best_loss(bh + Xh @ d, rh)

        # the model is an approximation now, so the real evaluator decides
        trial = cur + d
        mg, eg = as_dicts(trial)
        _init(fens, mg, eg)
        real = _BASE
        real_fit, _ = best_loss(real[:cut], rf)
        real_hold, hk = best_loss(real[cut:], rh)
        scale = float(np.mean(np.abs(real)))

        ok = real_hold < hold_cur - 1e-9
        print(f"round {rnd}  trust {trust:.3f}  K={k_round}  predicts "
              f"{pred_hold:.6f}, real {real_hold:.6f} (K={hk})  "
              f"scale {100*(scale-scale0)/scale0:+.1f}%  "
              f"{'ACCEPT' if ok else 'REJECT'}", flush=True)
        if ok:
            cur, fit_cur, hold_cur = trial, real_fit, real_hold
            trust = min(trust * 1.4, 0.35)
        else:
            trust *= 0.5
            if trust < 0.005:
                print("trust region collapsed -- at a local optimum")
                break

    mg, eg = as_dicts(cur)
    json.dump({"k": best_k, "weights": {"mg": mg, "eg": eg}},
              open(a.out, "w"), indent=1)
    gh = 100 * (hold0 - hold_cur) / hold0
    print(f"\nfit      {fit0:.6f} -> {fit_cur:.6f}")
    print(f"HELD-OUT {hold0:.6f} -> {hold_cur:.6f}   {gh:+.3f}%"
          f"   ~{4.7*gh:+.1f} Elo   (real evaluator, scale-invariant)")
    moved = [(k, s, float(w0[i]), float(cur[i]))
             for i, (k, s) in enumerate(names)
             if abs(cur[i] - w0[i]) > 1e-9]
    print(f"{len(moved)} of {len(names)} weights moved")
    for k, s, o, nv in sorted(moved, key=lambda t: -abs(t[3] - t[2]))[:15]:
        print(f"  {k:34s} {s}  {o:10.3f} -> {nv:10.3f}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

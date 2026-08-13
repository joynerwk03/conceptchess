"""Fit every LINEAR evaluation weight jointly, by measuring the eval itself.

Every weight in this engine has been tuned by coordinate descent: move one
number, re-score the whole dataset, keep it if the loss fell. That has two
costs. It is slow -- a pass per parameter per direction -- which is why runs
sample 24k of 98k rows and stop after a few passes. And it is *wrong* whenever
parameters are correlated: coordinate descent walks down the axes, so a pair of
terms that must move together to help (an isolated-pawn penalty and a
passed-pawn bonus disagreeing about the same pawn) looks flat along both axes
and is left where it started.

Both problems dissolve if the loss is a function the fit can differentiate.
And for most of these weights it is: they enter the evaluation as plain
multipliers, so for a fixed position

    eval(w) = eval(w0) + sum_j c_j * (w_j - w0_j)

Once the c_j are known, scoring any candidate weight vector is a matrix
multiply, and all of them can be fitted jointly by gradient descent.

The coefficients are MEASURED, not derived: perturb the weight, run the real
`evaluate()`, take the difference. Deriving them by reading the concept source
is how the first version of the piece-square fit went wrong -- it missed that
`evaluate` multiplies the concept sum by the opposite-bishop modifier, and the
error was invisible because a uniform perturbation cancels between colours.
Measuring through the real evaluator cannot make that class of mistake.

Linearity is measured too, not assumed. A weight is admitted only if a
double-size step moves the eval exactly twice as far, at every sampled
position. That rejects the genuinely non-linear ones -- `kattack` terms behind
an `attackers >= 2` threshold, anything inside the drawishness modifier -- which
stay with the coordinate tuner where they belong.

Finally the fitted weights are checked by RE-SCORING THE HELD-OUT SET WITH THE
REAL EVALUATOR. The model is exact by construction, but "by construction" is
what the last broken harness also had.

    PYTHONPATH=. .venv/bin/python research/linfit.py --workers 18
"""
import argparse
import json
import multiprocessing as mp
import random

import chess
import numpy as np

from research.texel import ROOT

_BOARDS = None
_STATE = {}


def _init(fens):
    global _BOARDS
    _BOARDS = [chess.Board(f) for f in fens]


def _eval_all():
    from engine.evaluation import evaluate, clear_caches
    clear_caches()
    return np.asarray([evaluate(b) for b in _BOARDS])


def _column(job):
    """(key, side, step) -> the eval response to perturbing that weight."""
    from engine.weights import W, W_EG
    key, side, step = job
    tgt = W if side == "mg" else W_EG
    orig = tgt.get(key)
    base = _STATE["base"]

    tgt[key] = orig + step
    e1 = _eval_all()
    tgt[key] = orig + 2.0 * step
    e2 = _eval_all()
    tgt[key] = orig
    _eval_all()                      # restore caches to the baseline weights

    d1 = e1 - base
    d2 = e2 - base
    # linear iff the second step moves exactly twice as far as the first
    scale = np.maximum(np.abs(d1), 1e-9)
    linear = bool(np.max(np.abs(d2 - 2.0 * d1) / scale) < 1e-6)
    return key, side, linear, d1 / step, float(np.abs(d1).max())


def _worker(job):
    return _column(job)


def _boot(fens):
    _init(fens)
    _STATE["base"] = _eval_all()


def build_columns(fens, jobs, workers):
    with mp.Pool(workers, initializer=_boot, initargs=(fens,)) as pool:
        return pool.map(_worker, jobs, chunksize=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--positions", type=int, default=40000)
    ap.add_argument("--holdout", type=float, default=0.35)
    ap.add_argument("--steps", type=int, default=6000)
    ap.add_argument("--lr", type=float, default=0.004)
    ap.add_argument("--l2", type=float, default=1e-4)
    ap.add_argument("--step", type=float, default=0.05,
                    help="relative probe step for measuring a coefficient")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default=str(ROOT / "research/data/linfit.json"))
    a = ap.parse_args()

    from engine.weights import W, W_EG
    from research.texel import TUNABLE

    rows = [json.loads(l) for l in open(a.data)]
    rows = [r for r in rows if r["res"] != 0.5]          # decisive only
    random.Random(4242).shuffle(rows)
    rows = rows[:a.positions]
    fens = [r["fen"] for r in rows]
    res = np.asarray([r["res"] for r in rows], dtype=float)
    cut = int(len(rows) * (1 - a.holdout))
    print(f"{cut} decisive fitting positions, {len(rows)-cut} held out")

    jobs = []
    for key in W:
        base = abs(W[key]) or 1.0
        jobs.append((key, "mg", a.step * base))
    for key in W_EG:
        base = abs(W_EG[key]) or 1.0
        jobs.append((key, "eg", a.step * base))
    print(f"measuring {len(jobs)} candidate parameters on {len(rows)} positions "
          f"with {a.workers} workers...")

    _boot(fens)
    base_eval = _STATE["base"].copy()
    cols = build_columns(fens, jobs, a.workers)

    keep, names = [], []
    dead = nonlin = 0
    for key, side, linear, col, span in cols:
        if span <= 1e-12:
            dead += 1
            continue
        if not linear:
            nonlin += 1
            continue
        keep.append(col)
        names.append((key, side))
    X = np.asarray(keep).T if keep else np.zeros((len(rows), 0))
    print(f"{X.shape[1]} linear parameters kept "
          f"({nonlin} non-linear, {dead} with no effect on this data)")

    w0 = np.asarray([(W if s == "mg" else W_EG)[k] for k, s in names], dtype=float)
    lo = np.empty(len(names))
    hi = np.empty(len(names))
    for i, (k, _s) in enumerate(names):
        b = TUNABLE.get(k)
        if b is None:
            lo[i], hi[i] = w0[i] - abs(w0[i]) * 0.5 - 2, w0[i] + abs(w0[i]) * 0.5 + 2
        else:
            f0, f1 = b
            v = w0[i]
            lo[i], hi[i] = min(v * f0, v * f1), max(v * f0, v * f1)

    Xf, Xh = X[:cut], X[cut:]
    bf, bh = base_eval[:cut], base_eval[cut:]
    rf, rh = res[:cut], res[cut:]

    def loss_of(Xm, bm, rm, d, k):
        e = bm + Xm @ d
        s = 1.0 / (1.0 + np.exp(-(np.log(10.0) / (k * 400.0)) * e))
        return float(np.mean((s - rm) ** 2))

    zero = np.zeros(X.shape[1])
    best_k, base_l = None, 1e9
    for k in (0.6, 0.8, 1.0, 1.2):
        l = loss_of(Xf, bf, rf, zero, k)
        if l < base_l:
            best_k, base_l = k, l
    hold_base = loss_of(Xh, bh, rh, zero, best_k)
    print(f"K={best_k}  fit {base_l:.6f}  held-out {hold_base:.6f}")

    c = np.log(10.0) / (best_k * 400.0)
    n = Xf.shape[0]
    d = np.zeros(X.shape[1])
    m = np.zeros_like(d)
    v = np.zeros_like(d)
    b1, b2, eps = 0.9, 0.999, 1e-8
    span = np.maximum(np.abs(w0), 1.0)
    for t in range(1, a.steps + 1):
        e = bf + Xf @ d
        s = 1.0 / (1.0 + np.exp(-c * e))
        g_e = (2.0 * (s - rf) * s * (1.0 - s) * c) / n
        g = Xf.T @ g_e + 2.0 * a.l2 * d / (span * span)
        m = b1 * m + (1 - b1) * g
        v = b2 * v + (1 - b2) * g * g
        d -= a.lr * span * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)
        np.clip(d, lo - w0, hi - w0, out=d)
        if t % 1000 == 0:
            print(f"  step {t:5d}  fit {loss_of(Xf, bf, rf, d, best_k):.6f}"
                  f"  held-out {loss_of(Xh, bh, rh, d, best_k):.6f}", flush=True)

    fit_end = loss_of(Xf, bf, rf, d, best_k)
    hold_end = loss_of(Xh, bh, rh, d, best_k)

    tuned = {}
    for (k, s), val in zip(names, w0 + d):
        tuned.setdefault(s, {})[k] = float(val)
    json.dump({"k": best_k, "weights": tuned}, open(a.out, "w"), indent=1)

    # --- the honest check: score the held-out set with the REAL evaluator ---
    for s, kv in tuned.items():
        tgt = W if s == "mg" else W_EG
        for k, val in kv.items():
            tgt[k] = val
    _init(fens[cut:])
    real = _eval_all()
    sr = 1.0 / (1.0 + np.exp(-c * real))
    hold_real = float(np.mean((sr - rh) ** 2))

    gf = 100 * (base_l - fit_end) / base_l
    gh = 100 * (hold_base - hold_end) / hold_base
    gr = 100 * (hold_base - hold_real) / hold_base
    print(f"\nfit           {base_l:.6f} -> {fit_end:.6f}   {gf:+.3f}%")
    print(f"held-out      {hold_base:.6f} -> {hold_end:.6f}   {gh:+.3f}%  (model)")
    print(f"HELD-OUT REAL {hold_base:.6f} -> {hold_real:.6f}   {gr:+.3f}%"
          f"   ~{4.7*gr:+.1f} Elo")
    print(f"model vs real disagreement: {abs(gh-gr):.4f} percentage points"
          f"   {'OK' if abs(gh-gr) < 1e-6 else '<-- MODEL IS NOT EXACT, DO NOT SHIP'}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

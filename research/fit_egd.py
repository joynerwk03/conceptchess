"""Fit the endgame deltas for knight, bishop, rook and queen.

Pawns and kings have had a middlegame and an endgame table since v0; the four
piece types have had one table each, so the evaluation could not say that a
knight on the rim is a different mistake in an opening than in a pawn ending, or
that a rook's file matters more once the queens come off. The delta tables were
added as an exact no-op (all zero, node counts identical); this is what gives
them values.

Method is the one that has worked here twice:

  * coefficients MEASURED by perturbing each parameter and running the REAL
    evaluate(), never derived. Deriving them is what made the first piece-square
    model wrong by 7.9cp -- it missed that evaluate() multiplies the concept sum
    by the opposite-bishop modifier;
  * mirror squares tied, so the tables stay left-right symmetric and readable
    and the fit has 128 parameters rather than 256;
  * the loss is scale-invariant, K refitted per candidate, because at a fixed K
    inflating the evaluation lowers the loss while changing no move;
  * held out, and the held-out set re-scored with the REAL evaluator after
    rounding to integers, since integers are what ship.

    PYTHONPATH=. .venv/bin/python research/fit_egd.py --workers 15
"""
import argparse
import json
import multiprocessing as mp
import random

import chess
import numpy as np

from research.texel import ROOT

BLOCKS = ["KNIGHT_EGD", "BISHOP_EGD", "ROOK_EGD", "QUEEN_EGD"]
_B = None
_BASE = None

KGRID = [0.30, 0.34, 0.38, 0.42, 0.44, 0.46, 0.48, 0.50, 0.54, 0.60]


def best_loss(e, r):
    best = (1e9, None)
    for k in KGRID:
        s = 1.0 / (1.0 + np.exp(-(np.log(10.0) / (k * 400.0)) * e))
        l = float(np.mean((s - r) ** 2))
        if l < best[0]:
            best = (l, k)
    return best


def param_map():
    """feature (block, square) -> parameter, tying left-right mirror squares."""
    fmap = np.zeros(len(BLOCKS) * 64, dtype=np.int32)
    seen, nxt = {}, 0
    for bi in range(len(BLOCKS)):
        for sq in range(64):
            r, f = divmod(sq, 8)
            key = (bi, r, min(f, 7 - f))
            if key not in seen:
                seen[key] = nxt
                nxt += 1
            fmap[bi * 64 + sq] = seen[key]
    return fmap, nxt


def _apply(vec, fmap):
    from engine.concepts import piece_placement as pp
    full = np.asarray(vec)[fmap]
    for bi, name in enumerate(BLOCKS):
        t = getattr(pp, name)
        for sq in range(64):
            t[sq] = float(full[bi * 64 + sq])


def _eval_all():
    from engine.evaluation import evaluate, clear_caches
    clear_caches()
    return np.asarray([evaluate(b) for b in _B])


def _init(fens, vec, fmap):
    global _B, _BASE
    _apply(vec, fmap)
    _B = [chess.Board(f) for f in fens]
    _BASE = _eval_all()


_SPEC = {}


def _col(job):
    i, step, vec = job
    v = np.asarray(vec, dtype=float)
    v[i] += step
    _apply(v, _SPEC["fmap"])
    e1 = _eval_all()
    _apply(np.asarray(vec, dtype=float), _SPEC["fmap"])
    return (e1 - _BASE) / step


def _boot(fens, vec, fmap):
    _SPEC["fmap"] = fmap
    _init(fens, vec, fmap)


def measure(fens, vec, step, workers, fmap):
    jobs = [(i, step, list(vec)) for i in range(len(vec))]
    with mp.Pool(workers, initializer=_boot,
                 initargs=(fens, list(vec), fmap)) as pool:
        cols = pool.map(_col, jobs, chunksize=1)
    _boot(fens, list(vec), fmap)
    return _BASE.copy(), np.asarray(cols).T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--positions", type=int, default=40000)
    ap.add_argument("--holdout", type=float, default=0.35)
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--trust", type=float, default=8.0, help="cp per round")
    ap.add_argument("--workers", type=int, default=15)
    ap.add_argument("--out", default=str(ROOT / "research/data/egd_fit.json"))
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.data)]
    rows = [r for r in rows if r["res"] != 0.5]
    random.Random(8675309).shuffle(rows)
    rows = rows[:a.positions]
    fens = [r["fen"] for r in rows]
    res = np.asarray([r["res"] for r in rows], dtype=float)
    cut = int(len(rows) * (1 - a.holdout))
    rf, rh = res[:cut], res[cut:]

    fmap, npar = param_map()
    cur = np.zeros(npar)
    print(f"{cut} fitting positions, {len(rows)-cut} held out")
    print(f"{len(BLOCKS)*64} table entries -> {npar} parameters (mirror squares tied)")

    _boot(fens, cur, fmap)
    fit0, k0 = best_loss(_BASE[:cut], rf)
    hold0, _ = best_loss(_BASE[cut:], rh)
    print(f"fit {fit0:.6f} (K={k0})  held-out {hold0:.6f}")

    trust = a.trust
    fit_cur, hold_cur = fit0, hold0
    for rnd in range(1, a.rounds + 1):
        base, X = measure(fens, cur, max(trust * 0.25, 0.5), a.workers, fmap)
        Xf, Xh = X[:cut], X[cut:]
        bf, bh = base[:cut], base[cut:]
        _, kr = best_loss(bf, rf)
        c = np.log(10.0) / (kr * 400.0)

        d = np.zeros(npar)
        m = np.zeros(npar)
        v = np.zeros(npar)
        b1, b2, eps = 0.9, 0.999, 1e-8
        n = Xf.shape[0]
        for t in range(1, a.steps + 1):
            e = bf + Xf @ d
            sg = 1.0 / (1.0 + np.exp(-c * e))
            g = Xf.T @ ((2.0 * (sg - rf) * sg * (1.0 - sg) * c) / n)
            m = b1 * m + (1 - b1) * g
            v = b2 * v + (1 - b2) * g * g
            d -= (0.02 * trust) * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)
            np.clip(d, -trust, trust, out=d)

        trial = np.round(cur + d)          # integers are what ship
        _boot(fens, trial, fmap)
        real_fit, _ = best_loss(_BASE[:cut], rf)
        real_hold, _ = best_loss(_BASE[cut:], rh)
        ok = real_hold < hold_cur - 1e-9
        print(f"round {rnd}  trust {trust:.1f}cp  real held-out {real_hold:.6f}"
              f"  {'ACCEPT' if ok else 'REJECT'}", flush=True)
        if ok:
            cur, fit_cur, hold_cur = trial, real_fit, real_hold
            trust = min(trust * 1.4, 40.0)
        else:
            trust *= 0.5
            if trust < 0.5:
                print("trust region collapsed -- at a local optimum")
                break

    full = np.asarray(cur)[fmap]
    out = {n: [int(x) for x in full[i * 64:(i + 1) * 64]]
           for i, n in enumerate(BLOCKS)}
    json.dump(out, open(a.out, "w"), indent=1)
    gh = 100 * (hold0 - hold_cur) / hold0
    print(f"\nHELD-OUT {hold0:.6f} -> {hold_cur:.6f}   {gh:+.3f}%"
          f"   ~{4.7*gh:+.1f} Elo   (real evaluator, scale-invariant)")
    print(f"largest delta: {int(np.abs(full).max())}cp")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

"""Fit weights, piece-square tables and the passed-pawn curve TOGETHER.

Everything so far has been fitted in sequence: the tables at the old weights,
then the weights at the new tables. That leaves the cross-terms on the floor.
A knight table and `pst.knight` and `material.knight` all argue about the same
knight, so the optimum for any one of them depends on the other two, and fitting
them in turn stops at the first point where each is individually flat.

This fits all of it at once -- ~420 parameters -- which is only possible because
the same trick keeps working: perturb a parameter, run the REAL evaluate(),
difference. The evaluation is locally linear in every one of these, so one pass
per parameter buys a model that can be descended jointly, and a trust region
keeps the step inside the range the linearisation was measured over.

Three parameter groups, all free in speed terms -- they are constants, so none
of this costs a single node per second:

  * every weight in W and W_EG;
  * the piece-square tables, mirror-tied for pawns and pieces so they stay
    left-right symmetric and readable, free for the two king tables;
  * PASSED_BONUS, the value of a passed pawn by rank -- eight hand-picked round
    numbers ([0,10,15,20,35,60,100,0]) that have never been tuned, on one of the
    most important curves in the evaluation.

Judged the only way that means anything: held-out positions, re-scored with the
real evaluator, at the best K for each candidate so that inflating the eval --
worth a spurious +0.751% at a fixed K -- earns exactly nothing.

    PYTHONPATH=. .venv/bin/python research/fit_all.py --rounds 7 --workers 15
"""
import argparse
import json
import multiprocessing as mp
import random

import chess
import numpy as np

from research.texel import ROOT
from research.tune_pst_linear import BLOCKS, param_map

_B = None
_BASE = None
_SPEC = {}

KGRID = [0.30, 0.34, 0.38, 0.42, 0.44, 0.46, 0.48, 0.50, 0.52, 0.56, 0.62]


def best_loss(e, r):
    best = (1e9, None)
    for k in KGRID:
        s = 1.0 / (1.0 + np.exp(-(np.log(10.0) / (k * 400.0)) * e))
        l = float(np.mean((s - r) ** 2))
        if l < best[0]:
            best = (l, k)
    return best


def _apply(vec):
    """Push a full parameter vector into the live evaluation modules."""
    from engine.weights import W, W_EG
    from engine.concepts import piece_placement as pp
    from engine.concepts import pawn_structure as ps
    names, fmap, npst, nw = _SPEC["names"], _SPEC["fmap"], _SPEC["npst"], _SPEC["nw"]
    for (k, side), v in zip(names, vec[:nw]):
        (W if side == "mg" else W_EG)[k] = float(v)
    pst = np.asarray(vec[nw:nw + npst])[fmap]
    for i, blk in enumerate(BLOCKS):
        t = getattr(pp, blk)
        for sq in range(64):
            t[sq] = float(pst[i * 64 + sq])
    for j, idx in enumerate(_SPEC["pb_idx"]):
        ps.PASSED_BONUS[idx] = float(vec[nw + npst + j])


def _eval_all():
    from engine.evaluation import evaluate, clear_caches
    clear_caches()
    return np.asarray([evaluate(b) for b in _B])


def _init(fens, vec, spec):
    global _B, _BASE
    _SPEC.update(spec)
    _apply(np.asarray(vec))
    _B = [chess.Board(f) for f in fens]
    _BASE = _eval_all()


def _col(job):
    i, step, vec = job
    v = np.asarray(vec, dtype=float)
    v[i] += step
    _apply(v)
    e1 = _eval_all()
    _apply(np.asarray(vec, dtype=float))
    return (e1 - _BASE) / step


def measure(fens, vec, steps, workers, spec):
    jobs = [(i, float(steps[i]), list(vec)) for i in range(len(vec))]
    with mp.Pool(workers, initializer=_init,
                 initargs=(fens, list(vec), spec)) as pool:
        cols = pool.map(_col, jobs, chunksize=1)
    _init(fens, list(vec), spec)
    return _BASE.copy(), np.asarray(cols).T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--positions", type=int, default=36000)
    ap.add_argument("--holdout", type=float, default=0.35)
    ap.add_argument("--rounds", type=int, default=7)
    ap.add_argument("--trust", type=float, default=0.08)
    ap.add_argument("--steps", type=int, default=2500)
    ap.add_argument("--workers", type=int, default=15)
    ap.add_argument("--out", default=str(ROOT / "research/data/fit_all.json"))
    a = ap.parse_args()

    from engine.weights import W, W_EG
    from engine.concepts import piece_placement as pp
    from engine.concepts import pawn_structure as ps
    from research.texel import TUNABLE

    rows = [json.loads(l) for l in open(a.data)]
    rows = [r for r in rows if r["res"] != 0.5]
    random.Random(90210).shuffle(rows)
    rows = rows[:a.positions]
    fens = [r["fen"] for r in rows]
    res = np.asarray([r["res"] for r in rows], dtype=float)
    cut = int(len(rows) * (1 - a.holdout))
    rf, rh = res[:cut], res[cut:]

    names = [(k, "mg") for k in W] + [(k, "eg") for k in W_EG]
    nw = len(names)
    fmap, npst = param_map()
    # the end ranks of PASSED_BONUS are structurally zero (no pawn lives there)
    pb_idx = [i for i in range(1, 7)]
    spec = {"names": names, "fmap": fmap, "npst": npst, "nw": nw,
            "pb_idx": pb_idx}

    w0 = np.asarray([(W if s == "mg" else W_EG)[k] for k, s in names], float)
    T0 = np.concatenate([np.asarray(getattr(pp, b), dtype=float) for b in BLOCKS])
    pst0 = np.zeros(npst)
    pst0[fmap] = T0            # tied entries agree, so this is exact
    pb0 = np.asarray([ps.PASSED_BONUS[i] for i in pb_idx], float)
    cur = np.concatenate([w0, pst0, pb0])
    print(f"{cut} fitting positions, {len(rows)-cut} held out")
    print(f"{nw} weights + {npst} table params + {len(pb_idx)} passed-pawn ranks "
          f"= {len(cur)} parameters, jointly")

    lo = np.empty(len(cur))
    hi = np.empty(len(cur))
    for i, (k, _s) in enumerate(names):
        v = w0[i]
        if k.startswith("material."):
            lo[i], hi[i] = v * 0.90, v * 1.10
        elif k in TUNABLE:
            f0, f1 = TUNABLE[k]
            lo[i], hi[i] = min(v * f0, v * f1), max(v * f0, v * f1)
        else:
            lo[i], hi[i] = v - abs(v) * 0.5 - 2, v + abs(v) * 0.5 + 2
    lo[nw:nw + npst] = pst0 - (np.abs(pst0) * 0.25 + 10.0)
    hi[nw:nw + npst] = pst0 + (np.abs(pst0) * 0.25 + 10.0)
    lo[nw + npst:] = pb0 * 0.4
    hi[nw + npst:] = pb0 * 2.0

    _init(fens, cur, spec)
    fit0, k0 = best_loss(_BASE[:cut], rf)
    hold0, _ = best_loss(_BASE[cut:], rh)
    print(f"fit {fit0:.6f} (K={k0})  held-out {hold0:.6f}")

    trust = a.trust
    fit_cur, hold_cur = fit0, hold0
    for rnd in range(1, a.rounds + 1):
        step = np.maximum(np.abs(cur) * trust * 0.25, 0.5)
        base, X = measure(fens, cur, step, a.workers, spec)
        Xf, Xh = X[:cut], X[cut:]
        bf, bh = base[:cut], base[cut:]
        _, kr = best_loss(bf, rf)
        c = np.log(10.0) / (kr * 400.0)

        room = np.maximum(np.abs(cur) * trust, 1.0)
        dlo = np.maximum(lo - cur, -room)
        dhi = np.minimum(hi - cur, room)
        d = np.zeros(len(cur))
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

        trial = cur + d
        # piece-square tables and the passed-pawn curve ship as integers
        trial[nw:] = np.round(trial[nw:])
        _init(fens, trial, spec)
        real_fit, _ = best_loss(_BASE[:cut], rf)
        real_hold, _ = best_loss(_BASE[cut:], rh)
        ok = real_hold < hold_cur - 1e-9
        print(f"round {rnd}  trust {trust:.3f}  real held-out {real_hold:.6f}"
              f"  {'ACCEPT' if ok else 'REJECT'}", flush=True)
        if ok:
            cur, fit_cur, hold_cur = trial, real_fit, real_hold
            trust = min(trust * 1.4, 0.30)
        else:
            trust *= 0.5
            if trust < 0.004:
                print("trust region collapsed -- at a local optimum")
                break

    pstv = np.asarray(cur[nw:nw + npst])[fmap]
    out = {
        "weights": {"mg": {}, "eg": {}},
        "tables": {b: [float(x) for x in pstv[i * 64:(i + 1) * 64]]
                   for i, b in enumerate(BLOCKS)},
        "passed_bonus": {str(i): float(v)
                         for i, v in zip(pb_idx, cur[nw + npst:])},
    }
    for (k, s), v in zip(names, cur[:nw]):
        out["weights"][s][k] = float(v)
    json.dump(out, open(a.out, "w"), indent=1)

    gh = 100 * (hold0 - hold_cur) / hold0
    print(f"\nHELD-OUT {hold0:.6f} -> {hold_cur:.6f}   {gh:+.3f}%"
          f"   ~{4.7*gh:+.1f} Elo   (real evaluator, scale-invariant)")
    print("passed-pawn curve by rank: "
          f"{[ps.PASSED_BONUS[0]] + [int(round(v)) for v in cur[nw+npst:]] + [0]}"
          f"   was [0, 10, 15, 20, 35, 60, 100, 0]")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

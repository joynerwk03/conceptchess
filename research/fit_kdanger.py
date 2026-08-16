"""Fit the king-danger curve, monotonically, instead of forcing it quadratic.

King danger was `scale * units^2 / 10`: one free parameter, and a shape assumed
rather than measured. The table that replaced it (an exact no-op, node counts
identical, -0.15% NPS) can hold any curve, and this fits it.

Danger is projected onto NON-DECREASING sequences after every step. More
pressure on a king cannot be worth less, and saying so is both real chess and
the regularisation that matters here -- high unit counts are rare, so without it
the tail would be fitted from a handful of positions each. Projection is by
pool-adjacent violators, the actual least-squares projection onto the monotone
cone.

Everything else is the machinery that has worked repeatedly: coefficients
MEASURED through the real evaluate() rather than derived, a trust region, a
scale-invariant loss with K refitted per candidate, and every round judged by
re-scoring held-out positions with the real evaluator.

    PYTHONPATH=. .venv/bin/python research/fit_kdanger.py --workers 15
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
_SPEC = {}
KGRID = [0.30, 0.34, 0.38, 0.42, 0.44, 0.46, 0.48, 0.50, 0.54, 0.60]


def best_loss(e, r):
    best = (1e9, None)
    for k in KGRID:
        s = 1.0 / (1.0 + np.exp(-(np.log(10.0) / (k * 400.0)) * e))
        l = float(np.mean((s - r) ** 2))
        if l < best[0]:
            best = (l, k)
    return best


def pava(y):
    """Least-squares projection onto non-decreasing sequences."""
    v, w = [], []
    for val in map(float, y):
        v.append(val)
        w.append(1.0)
        while len(v) > 1 and v[-2] > v[-1]:
            nv = (v[-2] * w[-2] + v[-1] * w[-1]) / (w[-2] + w[-1])
            nw = w[-2] + w[-1]
            v[-2:] = [nv]
            w[-2:] = [nw]
    out = []
    for val, cnt in zip(v, w):
        out.extend([val] * int(cnt))
    return np.asarray(out)


def _apply(vec):
    from engine.concepts import king_attack as ka
    n = _SPEC["n"]
    for u in range(n):
        ka.KD_MG[u] = float(vec[u])
        ka.KD_EG[u] = float(vec[n + u])


def _eval_all():
    from engine.evaluation import evaluate, clear_caches
    clear_caches()
    return np.asarray([evaluate(b) for b in _B])


def _boot(fens, vec, n):
    global _B, _BASE
    _SPEC["n"] = n
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


def measure(fens, vec, step, workers, n):
    jobs = [(i, step, list(vec)) for i in range(len(vec))]
    with mp.Pool(workers, initializer=_boot, initargs=(fens, list(vec), n)) as pool:
        cols = pool.map(_col, jobs, chunksize=1)
    _boot(fens, list(vec), n)
    return _BASE.copy(), np.asarray(cols).T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--positions", type=int, default=40000)
    ap.add_argument("--holdout", type=float, default=0.35)
    ap.add_argument("--rounds", type=int, default=7)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--trust", type=float, default=10.0)
    ap.add_argument("--workers", type=int, default=15)
    ap.add_argument("--out", default=str(ROOT / "research/data/kdanger_fit.json"))
    a = ap.parse_args()

    from engine.concepts.king_attack import KD_MG, KD_EG, KD_MAX
    # copied BEFORE fitting: _apply mutates the module lists in place, so
    # holding a reference and printing it later just shows the fitted curve
    # against itself.
    ORIG_MG = list(KD_MG)

    rows = [json.loads(l) for l in open(a.data)]
    rows = [r for r in rows if r["res"] != 0.5]
    random.Random(24601).shuffle(rows)
    rows = rows[:a.positions]
    fens = [r["fen"] for r in rows]
    res = np.asarray([r["res"] for r in rows], dtype=float)
    cut = int(len(rows) * (1 - a.holdout))
    rf, rh = res[:cut], res[cut:]

    n = KD_MAX
    cur = np.concatenate([np.asarray(KD_MG, float), np.asarray(KD_EG, float)])
    print(f"{cut} fitting positions, {len(rows)-cut} held out")
    print(f"{2*n} parameters (danger by attack units, middlegame and endgame)")

    _boot(fens, cur, n)
    fit0, k0 = best_loss(_BASE[:cut], rf)
    hold0, _ = best_loss(_BASE[cut:], rh)
    print(f"fit {fit0:.6f} (K={k0})  held-out {hold0:.6f}")

    probe, X0 = measure(fens, cur, 4.0, a.workers, n)
    live = np.abs(X0).max(axis=0) > 1e-12
    occ = [u for u in range(n) if live[u]]
    print(f"unit counts that occur in the data: {min(occ) if occ else '-'}"
          f"..{max(occ) if occ else '-'}  ({int(live.sum())} live of {2*n})")

    trust = a.trust
    fit_cur, hold_cur = fit0, hold0
    for rnd in range(1, a.rounds + 1):
        base, X = measure(fens, cur, max(trust * 0.25, 0.5), a.workers, n)
        Xf, Xh = X[:cut], X[cut:]
        bf, bh = base[:cut], base[cut:]
        _, kr = best_loss(bf, rf)
        c = np.log(10.0) / (kr * 400.0)

        d = np.zeros(2 * n)
        m = np.zeros(2 * n)
        v = np.zeros(2 * n)
        b1, b2, eps = 0.9, 0.999, 1e-8
        nn = Xf.shape[0]
        for t in range(1, a.steps + 1):
            e = bf + Xf @ d
            sg = 1.0 / (1.0 + np.exp(-c * e))
            g = Xf.T @ ((2.0 * (sg - rf) * sg * (1.0 - sg) * c) / nn)
            m = b1 * m + (1 - b1) * g
            v = b2 * v + (1 - b2) * g * g
            d -= (0.02 * trust) * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + eps)
            np.clip(d, -trust, trust, out=d)

        trial = cur + d
        trial[:n] = pava(trial[:n])          # danger cannot fall as pressure rises
        trial[n:] = pava(trial[n:])
        _boot(fens, trial, n)
        real_fit, _ = best_loss(_BASE[:cut], rf)
        real_hold, _ = best_loss(_BASE[cut:], rh)
        ok = real_hold < hold_cur - 1e-9
        print(f"round {rnd}  trust {trust:.1f}  real held-out {real_hold:.6f}"
              f"  {'ACCEPT' if ok else 'REJECT'}", flush=True)
        if ok:
            cur, fit_cur, hold_cur = trial, real_fit, real_hold
            trust = min(trust * 1.4, 60.0)
        else:
            trust *= 0.5
            if trust < 0.5:
                print("trust region collapsed -- at a local optimum")
                break

    json.dump({"KD_MG": [float(x) for x in cur[:n]],
               "KD_EG": [float(x) for x in cur[n:]]}, open(a.out, "w"), indent=1)
    gh = 100 * (hold0 - hold_cur) / hold0
    print(f"\nHELD-OUT {hold0:.6f} -> {hold_cur:.6f}   {gh:+.3f}%"
          f"   ~{4.7*gh:+.1f} Elo   (real evaluator, scale-invariant)")
    if occ:
        lo, hi = min(occ), min(max(occ), n - 1)
        print("\nfitted danger curve (middlegame), by units:")
        print("  " + " ".join(f"{u}:{cur[u]:.0f}" for u in range(lo, hi + 1, 4)))
        print("was quadratic:")
        print("  " + " ".join(f"{u}:{ORIG_MG[u]:.0f}" for u in range(lo, hi + 1, 4)))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

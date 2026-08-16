"""Fit threat value by (kind, victim), instead of assuming it tracks material.

A threat was priced `weight * VALUE[victim]`, so a threat against a queen was
worth exactly nine times one against a pawn -- an assumption, and a strong one.
The table that replaced it ships as a no-op; this gives it values.

Forty parameters (four kinds x five victims x two phases) where there were four.
Same machinery as the king-danger curve: coefficients MEASURED through the real
evaluate(), a trust region, a scale-invariant loss with K refitted per candidate,
and every round judged by re-scoring held-out positions with the real evaluator.

No monotonicity is imposed here. For king danger "more pressure cannot be worth
less" is real chess; for threats there is no comparable ordering across victims
that is safe to assume -- assuming one is precisely the mistake being corrected.

    PYTHONPATH=. .venv/bin/python research/fit_threats.py --workers 15
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


def _keys():
    from engine.concepts import threats as th
    return [(ph, kind, pt) for ph in ("mg", "eg")
            for kind in th._KINDS for pt in th._VICTIMS]


def _apply(vec):
    from engine.concepts import threats as th
    for (ph, kind, pt), v in zip(_SPEC["keys"], vec):
        (th.THREAT_MG if ph == "mg" else th.THREAT_EG)[kind][pt] = float(v)


def _eval_all():
    from engine.evaluation import evaluate, clear_caches
    clear_caches()
    return np.asarray([evaluate(b) for b in _B])


def _boot(fens, vec):
    global _B, _BASE
    _SPEC["keys"] = _keys()
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


def measure(fens, vec, step, workers):
    jobs = [(i, step, list(vec)) for i in range(len(vec))]
    with mp.Pool(workers, initializer=_boot, initargs=(fens, list(vec))) as pool:
        cols = pool.map(_col, jobs, chunksize=1)
    _boot(fens, list(vec))
    return _BASE.copy(), np.asarray(cols).T


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--positions", type=int, default=45000)
    ap.add_argument("--holdout", type=float, default=0.35)
    ap.add_argument("--rounds", type=int, default=12)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--trust", type=float, default=6.0)
    ap.add_argument("--workers", type=int, default=15)
    ap.add_argument("--out", default=str(ROOT / "research/data/threat_fit.json"))
    a = ap.parse_args()

    from engine.concepts import threats as th

    rows = [json.loads(l) for l in open(a.data)]
    rows = [r for r in rows if r["res"] != 0.5]
    random.Random(1123581321).shuffle(rows)
    rows = rows[:a.positions]
    fens = [r["fen"] for r in rows]
    res = np.asarray([r["res"] for r in rows], dtype=float)
    cut = int(len(rows) * (1 - a.holdout))
    rf, rh = res[:cut], res[cut:]

    keys = _keys()
    cur = np.asarray([(th.THREAT_MG if ph == "mg" else th.THREAT_EG)[k][pt]
                      for ph, k, pt in keys], dtype=float)
    orig = cur.copy()
    print(f"{cut} fitting positions, {len(rows)-cut} held out")
    print(f"{len(cur)} parameters (4 kinds x 5 victims x 2 phases)")

    _boot(fens, cur)
    fit0, k0 = best_loss(_BASE[:cut], rf)
    hold0, _ = best_loss(_BASE[cut:], rh)
    print(f"fit {fit0:.6f} (K={k0})  held-out {hold0:.6f}")

    trust = a.trust
    fit_cur, hold_cur = fit0, hold0
    for rnd in range(1, a.rounds + 1):
        base, X = measure(fens, cur, max(trust * 0.25, 0.4), a.workers)
        Xf, Xh = X[:cut], X[cut:]
        bf, bh = base[:cut], base[cut:]
        _, kr = best_loss(bf, rf)
        c = np.log(10.0) / (kr * 400.0)

        d = np.zeros(len(cur))
        m = np.zeros(len(cur))
        v = np.zeros(len(cur))
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
        _boot(fens, trial)
        real_fit, _ = best_loss(_BASE[:cut], rf)
        real_hold, _ = best_loss(_BASE[cut:], rh)
        ok = real_hold < hold_cur - 1e-9
        print(f"round {rnd}  trust {trust:.1f}  real held-out {real_hold:.6f}"
              f"  {'ACCEPT' if ok else 'REJECT'}", flush=True)
        if ok:
            cur, fit_cur, hold_cur = trial, real_fit, real_hold
            trust = min(trust * 1.4, 40.0)
        else:
            trust *= 0.5
            if trust < 0.3:
                print("trust region collapsed -- at a local optimum")
                break

    out = {"mg": {}, "eg": {}}
    for (ph, kind, pt), v in zip(keys, cur):
        out[ph].setdefault(kind, {})[str(pt)] = float(v)
    json.dump(out, open(a.out, "w"), indent=1)

    gh = 100 * (hold0 - hold_cur) / hold0
    print(f"\nHELD-OUT {hold0:.6f} -> {hold_cur:.6f}   {gh:+.3f}%"
          f"   ~{4.7*gh:+.1f} Elo   (real evaluator, scale-invariant)")
    names = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
             chess.ROOK: "rook", chess.QUEEN: "queen"}
    print("\nmiddlegame threat value, fitted vs the old weight x victim value:")
    for i, (ph, kind, pt) in enumerate(keys):
        if ph == "mg":
            print(f"  {kind:8s} on {names[pt]:7s}  {orig[i]:7.1f} -> {cur[i]:7.1f}")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

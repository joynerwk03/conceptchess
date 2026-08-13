"""Re-tune every weight against DECISIVE-game loss.

Every weight this engine carries was fitted against loss over *all* games,
including drawn ones -- and 2026-08-05 established that this is the wrong
objective. Positions from drawn games carry no information about whether a
change helps you win: scoring a dead-drawn ending as 0.00 instead of +170 is a
huge improvement in forecast and none at all in result. The all-games rate
predicted +11 Elo for a change worth +1; the decisive-games rate predicted the
phase3 stack to within 0.1 Elo.

So the entire weight vector is currently optimised for the wrong thing. This
re-fits it against the metric that actually tracks strength.

Guardrails carried over from the existing tuner, each of which was learned the
hard way:
  * bounds relative to the FROZEN original priors, not to current values, or
    +-25%-of-current compounds geometrically across successive spins and the
    weights escape chess sense (the s2 failure);
  * enough passes to converge, and a loud warning when weights are still moving
    at the last pass -- a coordinate descent that stops early has reported its
    step size, not an optimum (Phase 2 and bundle A both did exactly that);
  * material stays fixed: those values feed SEE, so moving them changes what
    "winning a trade" means inside the search.

    PYTHONPATH=. .venv/bin/python research/texel_decisive.py --passes 40
"""
import argparse
import json
import random

from research.texel import (TUNABLE, ORIGINAL_PRIORS, PRIOR_ENVELOPE,
                            EG_ENVELOPE, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--sample", type=int, default=30000)
    ap.add_argument("--passes", type=int, default=40)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", default=str(ROOT / "research/data/texel_decisive.json"))
    a = ap.parse_args()

    import chess
    from engine import weights as wmod
    from engine.evaluation import evaluate, clear_caches
    W = wmod.W

    rows = [json.loads(l) for l in open(a.data)]
    random.Random(a.seed).shuffle(rows)
    rows = rows[:a.sample]
    n_all = len(rows)
    # THE change: decisive games only.
    rows = [r for r in rows if r["res"] != 0.5]
    print(f"{len(rows)} of {n_all} sampled positions are from DECISIVE games")
    boards = [chess.Board(r["fen"]) for r in rows]
    results = [r["res"] for r in rows]

    def loss(k):
        clear_caches()
        s = 0.0
        for b, r in zip(boards, results):
            p = 1.0 / (1.0 + 10.0 ** (-evaluate(b) / (k * 400.0)))
            s += (p - r) * (p - r)
        return s / len(boards)

    best_k, base = None, 1e9
    for k in (0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
        l = loss(k)
        if l < base:
            best_k, base = k, l
    print(f"K={best_k}  baseline decisive loss {base:.6f}")

    keys = [k for k in TUNABLE if k in W]
    cur = {k: W[k] for k in keys}
    eg_cur = {k: wmod.W_EG.get(k, cur[k]) for k in keys}
    params = [("mg", k) for k in keys] + [("eg", k) for k in keys]
    print(f"tuning {len(params)} parameters against decisive-game loss")

    def apply(kind, key, v):
        if kind == "mg":
            W[key] = v
        else:
            wmod.W_EG[key] = v

    best = base
    moved_last = {}
    for p in range(a.passes):
        improved = False
        for kind, key in params:
            c = cur[key] if kind == "mg" else eg_cur[key]
            if kind == "mg":
                lo, hi = cur[key] * TUNABLE[key][0], cur[key] * TUNABLE[key][1]
                if key in ORIGINAL_PRIORS:
                    lo = max(lo, ORIGINAL_PRIORS[key] * PRIOR_ENVELOPE[0])
                    hi = min(hi, ORIGINAL_PRIORS[key] * PRIOR_ENVELOPE[1])
            else:
                lo, hi = cur[key] * EG_ENVELOPE[0], cur[key] * EG_ENVELOPE[1]
            if lo > hi:
                lo, hi = hi, lo
            step = max(abs(cur[key]) * 0.05, 0.05)
            for cand in (c + step, c - step):
                cand = min(max(cand, lo), hi)
                if cand == c:
                    continue
                apply(kind, key, cand)
                l = loss(best_k)
                if l < best - 1e-9:
                    best, improved = l, True
                    if kind == "mg":
                        cur[key] = cand
                    else:
                        eg_cur[key] = cand
                    c = cand
                    moved_last[(kind, key)] = p
                    print(f"  pass {p+1}: {key}[{kind}] -> {cand:.3f}  "
                          f"decisive loss {l:.6f}", flush=True)
                else:
                    apply(kind, key, c)
        if not improved:
            print(f"converged after {p+1} passes")
            break
    else:
        still = [k for k, v in moved_last.items() if v >= a.passes - 2]
        if still:
            print(f"!! NOT CONVERGED -- still moving: {still[:6]}")

    eg_out = {k: v for k, v in eg_cur.items() if v != cur[k]}
    json.dump({"k": best_k, "baseline_decisive_loss": base,
               "tuned_decisive_loss": best,
               "weights": cur, "weights_eg": eg_out}, open(a.out, "w"), indent=1)
    gain = 100 * (base - best) / base
    print(f"\ndecisive loss {base:.6f} -> {best:.6f}  ({gain:+.3f}%)")
    print(f"at ~4.7 Elo per 1% of decisive loss: about {4.7*gain:+.1f} Elo")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

"""Which cheaply-computable proxy for concept disagreement keeps the signal?

True spread (sum of |concept score| over non-material concepts) predicts eval
error at 1.68x, bottom third against top third. But `ceval.c` accumulates
everything into a single running total with no concept boundaries, so computing
true spread in C means restructuring 600 lines.

So test proxies first. Each is scored the same way -- mean |our eval - SF11
depth-13| in the bottom third against the top third -- so they are directly
comparable to the 1.68x baseline:

  spread_true   sum |concept|, non-material            the baseline
  net_nonmat    |eval - material_only|                 CHEAP: material is a
                                                       popcount sum, already
                                                       computed in ceval
  max_concept   max |concept|, non-material            one extra max
  top2          |pawn_structure| + |threats|           the two strongest single
                                                       predictors from the
                                                       previous run

If net_nonmat retains most of the signal it is nearly free to compute, since it
is one subtraction from values ceval already has. If only spread_true works, the
restructuring is the price of the idea and should be judged against its size.
"""
import json
import sys
from pathlib import Path

import chess

ROOT = Path("/home/joynerwk03/mission-control/projects/conceptchess")
sys.path.insert(0, str(ROOT))

from engine.evaluation import evaluate, evaluate_detailed   # noqa: E402

CLAMP = 1500


def main():
    rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
    recs = []
    for r in rows:
        b = chess.Board(r["fen"])
        sf = r["moves"][r["best"]]
        if abs(sf) > CLAMP:
            continue
        ours = evaluate(b)
        ours_stm = ours if b.turn == chess.WHITE else -ours
        err = abs(ours_stm - sf)
        det = evaluate_detailed(b)
        mat = 0.0
        vals = {}
        for c in det.concepts:
            nm = getattr(c, "name", "?")
            v = float(getattr(c, "score", 0.0))
            if nm.startswith("material"):
                mat += v
            else:
                vals[nm] = v
        nonmat = list(vals.values())
        recs.append({
            "err": err,
            "spread_true": sum(abs(v) for v in nonmat),
            "net_nonmat": abs(sum(nonmat)),
            "max_concept": max((abs(v) for v in nonmat), default=0.0),
            "top2": abs(vals.get("pawn_structure", 0.0)) + abs(vals.get("threats", 0.0)),
        })

    n = len(recs)
    print(f"{n} positions, overall mean error "
          f"{sum(r['err'] for r in recs)/n:.1f}cp\n")
    print(f"{'proxy':<14}{'bottom 3rd':>12}{'top 3rd':>10}{'ratio':>8}")
    for key in ("spread_true", "net_nonmat", "max_concept", "top2"):
        s = sorted(recs, key=lambda r: r[key])
        lo = s[:n // 3]
        hi = s[-(n // 3):]
        a = sum(r["err"] for r in lo) / len(lo)
        c = sum(r["err"] for r in hi) / len(hi)
        mark = "  <-- usable" if c / a > 1.25 else ""
        print(f"{key:<14}{a:>11.1f}c{c:>9.1f}c{c/a:>8.2f}{mark}")


if __name__ == "__main__":
    main()

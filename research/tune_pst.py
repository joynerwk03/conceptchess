"""Tune the piece-square TABLES themselves, against decisive-game loss.

Everything tuned in this project so far has been a *scalar*: `pst.knight` is a
multiplier on a knight table that has never moved. The tables are hand-made and
have been since v0, which makes them the largest block of untuned knowledge in
the evaluation -- and Texel tuning of piece-square tables is classically the
biggest single win available to an engine with hand-written ones.

Tuned by (piece, rank) rather than by individual square: 6 pieces x 8 ranks is
48 parameters instead of 384, which is tractable, far less prone to overfitting
21k positions, and captures the structure that matters -- how much a piece wants
to be advanced. Files are left alone; the hand tables already encode centrality
sensibly and the symmetric file structure is the part least likely to be wrong.

Against DECISIVE-game loss, because that is the objective that predicts Elo --
the all-games metric mispredicted by a factor of ten (see the 2026-08-05 entry).

Guardrails, all of them learned the hard way here:
  * bounds are +-30% of the CURRENT table value, so a rank cannot run away;
  * a held-out sample is scored at the end, because a 48-parameter fit reports
    an in-sample number that flatters it (the weight retune lost a quarter of
    its gain out of sample);
  * a loud warning if parameters are still moving on the last pass, which means
    the run reported its step size rather than an optimum.

    PYTHONPATH=. .venv/bin/python research/tune_pst.py --passes 12
"""
import argparse
import json
import random

import chess

from research.texel import ROOT

PIECES = [("PAWN_MG", chess.PAWN), ("PAWN_EG", chess.PAWN),
          ("KNIGHT", chess.KNIGHT), ("BISHOP", chess.BISHOP),
          ("ROOK", chess.ROOK), ("QUEEN", chess.QUEEN),
          ("KING_MG", chess.KING), ("KING_EG", chess.KING)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--sample", type=int, default=24000)
    ap.add_argument("--passes", type=int, default=12)
    ap.add_argument("--out", default=str(ROOT / "research/data/pst_tuned.json"))
    a = ap.parse_args()

    from engine.concepts import piece_placement as pp
    from engine.evaluation import evaluate, clear_caches

    tables = {name: getattr(pp, name) for name, _ in PIECES}

    def load(path, seed, lo, hi):
        rows = [json.loads(l) for l in open(path)]
        random.Random(seed).shuffle(rows)
        rows = rows[lo:hi]
        rows = [r for r in rows if r["res"] != 0.5]      # decisive only
        return [chess.Board(r["fen"]) for r in rows], [r["res"] for r in rows]

    fit_b, fit_r = load(a.data, 11, 0, a.sample)
    hold_b, hold_r = load(a.data, 777, 30000, 30000 + a.sample)
    print(f"{len(fit_b)} decisive fitting positions, {len(hold_b)} held out")

    def loss(boards, results, k):
        clear_caches()
        s = 0.0
        for b, r in zip(boards, results):
            p = 1.0 / (1.0 + 10.0 ** (-evaluate(b) / (k * 400.0)))
            s += (p - r) * (p - r)
        return s / len(boards)

    best_k, base = None, 1e9
    for k in (0.6, 0.8, 1.0):
        l = loss(fit_b, fit_r, k)
        if l < base:
            best_k, base = k, l
    hold_base = loss(hold_b, hold_r, best_k)
    print(f"K={best_k}  fit {base:.6f}  held-out {hold_base:.6f}")

    # (table, rank) -> the squares of that rank, from White's point of view.
    params = [(name, r) for name, _ in PIECES for r in range(1, 7)]
    original = {name: list(t) for name, t in tables.items()}
    best = base
    moved_last = {}

    for p in range(a.passes):
        improved = False
        for name, rank in params:
            t = tables[name]
            sqs = [rank * 8 + f for f in range(8)]
            cur = [t[s] for s in sqs]
            span = max(4.0, 0.10 * (max(abs(v) for v in cur) or 10.0))
            for delta in (span, -span):
                orig = [t[s] for s in sqs]
                ok = True
                for s in sqs:
                    v = t[s] + delta
                    lim = abs(original[name][s]) * 0.30 + 12.0
                    if abs(v - original[name][s]) > lim:
                        ok = False
                        break
                    t[s] = v
                if not ok:
                    for s, v in zip(sqs, orig):
                        t[s] = v
                    continue
                l = loss(fit_b, fit_r, best_k)
                if l < best - 1e-9:
                    best, improved = l, True
                    moved_last[(name, rank)] = p
                    print(f"  pass {p+1}: {name} rank{rank+1} {delta:+.1f}  "
                          f"loss {l:.6f}", flush=True)
                    break
                for s, v in zip(sqs, orig):
                    t[s] = v
        if not improved:
            print(f"converged after {p+1} passes")
            break
    else:
        still = [k for k, v in moved_last.items() if v >= a.passes - 2]
        if still:
            print(f"!! NOT CONVERGED -- still moving: {still[:6]}")

    hold = loss(hold_b, hold_r, best_k)
    json.dump({"k": best_k, "tables": {n: list(t) for n, t in tables.items()}},
              open(a.out, "w"), indent=1)
    gf = 100 * (base - best) / base
    gh = 100 * (hold_base - hold) / hold_base
    print(f"\nfit      {base:.6f} -> {best:.6f}   {gf:+.3f}%")
    print(f"HELD-OUT {hold_base:.6f} -> {hold:.6f}   {gh:+.3f}%"
          f"   ~{4.7*gh:+.1f} Elo")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

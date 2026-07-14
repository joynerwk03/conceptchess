"""Find and categorize positions where our eval diverges most from Stockfish.

Ranks the labeled eval set by |winprob(ours) - winprob(SF)|, buckets the worst
cases by position traits, and prints per-concept averages for the divergent
set vs the whole set — pointing at which concept family is mis-modeling.

Usage:
  python -m research.divergence            # summary + worst positions
  python -m research.divergence --n 40     # show more
"""

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

import chess

from engine.evaluation import evaluate, evaluate_detailed
from engine.context import EvalContext
from research.evalloss import winprob

DATA = Path(__file__).parent / "data"


def load(split="train"):
    return [json.loads(l) for l in
            (DATA / f"evalset_{split}.jsonl").read_text().splitlines()]


def analyze(split="train", top_n=150):
    rows = load(split)
    scored = []
    for r in rows:
        b = chess.Board(r["fen"])
        e = evaluate(b)
        err = (winprob(e) - winprob(r["sf_cp"])) ** 2
        scored.append((err, e, r["sf_cp"], r["fen"]))
    scored.sort(reverse=True)
    worst = scored[:top_n]

    traits = Counter()
    concept_worst = Counter()
    concept_all = Counter()
    for err, e, sf, fen in worst:
        b = chess.Board(fen)
        ctx = EvalContext(b)
        traits["ours_too_high" if e > sf else "ours_too_low"] += 1
        traits["middlegame" if ctx.phase > 0.6 else
               "endgame" if ctx.phase < 0.3 else "transition"] += 1
        qw = len(ctx.pieces[chess.WHITE][chess.QUEEN])
        qb = len(ctx.pieces[chess.BLACK][chess.QUEEN])
        traits["queens_on" if qw and qb else "queen_imbalance" if qw != qb
               else "queenless"] += 1
        bd = evaluate_detailed(b)
        for c in bd.concepts:
            concept_worst[c.name] += abs(c.score)
    # baseline concept magnitudes over a sample of the whole set
    for r in rows[::5]:
        bd = evaluate_detailed(chess.Board(r["fen"]))
        for c in bd.concepts:
            concept_all[c.name] += abs(c.score)

    print(f"worst {top_n} of {len(rows)} ({split}); traits:")
    for k, v in traits.most_common():
        print(f"  {k:<16} {v}")
    print("\nmean |concept| in worst set vs whole set (ratio >1 = overrepresented):")
    n_all = len(rows[::5])
    for name in concept_all:
        w = concept_worst[name] / top_n
        a = concept_all[name] / n_all
        ratio = w / a if a else float("inf")
        print(f"  {name:<15} worst {w:7.1f}  all {a:7.1f}  ratio {ratio:4.2f}")
    return worst


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=12)
    p.add_argument("--split", default="train")
    args = p.parse_args()
    worst = analyze(args.split)
    print(f"\nworst {args.n} positions:")
    for err, e, sf, fen in worst[:args.n]:
        print(f"  err {err:.3f} ours {e:+7.0f} sf {sf:+6.0f}  {fen}")


if __name__ == "__main__":
    main()

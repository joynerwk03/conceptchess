"""How much of the evaluation's error can change a move at all?

Six knowledge bundles in a row have tuned to zero, and the usual explanations
(too little data, too few terms) do not fit: `screen_loss` fits IN SAMPLE, so a
weight reaching exactly 0.000 has failed with every freedom to overfit. Which
raises a better question than "what term is missing": why does adding true chess
knowledge buy nothing?

Here is a mechanism worth testing. Texel tuning fits the evaluation to predict a
game's RESULT from a position. But a search never uses an evaluation that way.
It only ever COMPARES SIBLINGS -- the children of one node -- and picks the
best. Any error shared by all the siblings cancels exactly and cannot change a
single move. Only the part of the error that VARIES between siblings can.

So decompose, for each parent position:

    error_i        = eval(child_i) - deepsearch(child_i)
    common         = mean_i(error_i)          <- invisible to the search
    varying_i      = error_i - common         <- the only part that can matter

and report what share of the error variance is the varying part, plus how often
the evaluation's favourite child differs from the deep search's.

If the varying share is small, then most of what Texel tuning optimises is
invisible to move choice, and the objective itself is the constraint -- which
would explain the saturation better than any missing term does, and would say
to fit sibling DIFFERENCES rather than absolute outcomes.

    PYTHONPATH=. .venv/bin/python research/sibling_error.py --positions 300
"""
import argparse
import json
import random

import chess
import numpy as np

from research.texel import ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--positions", type=int, default=300)
    ap.add_argument("--movetime", type=float, default=0.25)
    ap.add_argument("--max-children", type=int, default=12)
    a = ap.parse_args()

    from engine.engine import Engine
    from engine.evaluation import evaluate, clear_caches

    rows = [json.loads(l) for l in open(a.data)]
    random.Random(2718).shuffle(rows)

    eng = Engine(use_book=False, use_tablebase=False)

    tot_var, tot_common, n_parents = [], [], 0
    agree = 0
    decided = 0
    for r in rows:
        if n_parents >= a.positions:
            break
        b = chess.Board(r["fen"])
        moves = list(b.legal_moves)
        if len(moves) < 3 or b.is_check():
            continue
        random.Random(n_parents).shuffle(moves)
        moves = moves[:a.max_children]

        # Everything below is from the PARENT MOVER's point of view, so that
        # "higher is better" means the same thing for both measurements.
        #   evaluate() returns White's view          -> flip if Black is to move
        #   best_move().score returns the CHILD's    -> always negate, since the
        #   side to move at the child is the parent mover's opponent
        mover_is_white = (b.turn == chess.WHITE)
        evals, searched = [], []
        for m in moves:
            b.push(m)
            clear_caches()
            e = evaluate(b)
            if not mover_is_white:
                e = -e
            s = -eng.best_move(b, movetime=a.movetime).score
            b.pop()
            evals.append(e)
            searched.append(s)

        ev = np.asarray(evals, dtype=float)
        sr = np.asarray(searched, dtype=float)
        if np.abs(sr).max() > 5000:        # a mate in the set makes scales absurd
            continue
        err = ev - sr
        common = float(np.mean(err))
        varying = err - common
        tot_common.append(common)
        tot_var.append(float(np.std(varying)))
        decided += 1
        if int(np.argmax(ev)) == int(np.argmax(sr)):
            agree += 1
        n_parents += 1
        if n_parents % 50 == 0:
            print(f"  {n_parents} parents", flush=True)

    common_sd = float(np.std(tot_common))
    varying_sd = float(np.mean(tot_var))
    print(f"\n{decided} parent positions, up to {a.max_children} children each, "
          f"deep search {a.movetime}s")
    print(f"  common error   (cancels between siblings): sd {common_sd:7.1f} cp")
    print(f"  VARYING error  (the only part that can    ")
    print(f"                  change a move)           : sd {varying_sd:7.1f} cp")
    share = varying_sd ** 2 / (varying_sd ** 2 + common_sd ** 2)
    print(f"  share of error variance that is visible to the search: {100*share:.1f}%")
    print(f"  evaluation's favourite child == search's favourite:    "
          f"{100*agree/max(decided,1):.1f}%")


if __name__ == "__main__":
    main()

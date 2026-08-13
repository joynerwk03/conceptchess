"""Prove the linear PST model predicts the REAL evaluator, before trusting it.

`tune_pst_linear.py` fits tables through a claim: that a table entry enters the
evaluation multiplied by a coefficient independent of the table, so a candidate
set of tables can be scored by dot product instead of by evaluating chess. If
that claim is wrong anywhere -- a table read somewhere else, a cache that
survives the mutation, a phase term I misread -- the tuner still produces
confident numbers, and they are about nothing. This project has shipped exactly
that failure before (an EPD parser that swallowed every error and reported all
terms dead; a bundle harness that paired against the wrong worktree).

So: perturb the tables for real, re-evaluate with the real evaluator, and
require the linear model to reproduce it.

    PYTHONPATH=. .venv/bin/python research/check_pst_linear.py
"""
import json
import random

import chess
import numpy as np

from research.texel import ROOT
from research.tune_pst_linear import BLOCKS, Model, collect, param_map


def main():
    from engine.concepts import piece_placement as pp
    from engine.evaluation import evaluate, clear_caches

    rows = [json.loads(l) for l in open(ROOT / "research/data/texel5.jsonl")]
    random.Random(5).shuffle(rows)
    boards = [chess.Board(r["fen"]) for r in rows[:300]]

    tables = {n: list(getattr(pp, n)) for n in BLOCKS}
    fmap, npar = param_map()
    model = Model(*collect(boards, tables), fmap, npar)

    # the model must reproduce the real evaluator at delta = 0 by construction
    base_err = np.abs(model.evals(np.zeros(npar))
                      - np.asarray([evaluate(b) for b in boards])).max()
    print(f"max |model - real| at delta=0 : {base_err:.9f}")

    rng = random.Random(99)
    delta = np.asarray([rng.uniform(-25, 25) for _ in range(npar)])
    pred = model.evals(delta)

    # now actually move the tables and re-evaluate for real
    dfull = delta[fmap]
    for i, name in enumerate(BLOCKS):
        t = getattr(pp, name)
        for sq in range(64):
            t[sq] += dfull[i * 64 + sq]
    clear_caches()
    real = np.asarray([evaluate(b) for b in boards])
    err = np.abs(pred - real).max()
    print(f"max |model - real| after a random +-25cp perturbation: {err:.9f}")
    print("VERDICT:", "linear model is exact -- safe to tune with"
          if err < 1e-6 and base_err < 1e-6 else
          "MODEL IS WRONG -- do not trust any number it produces")


if __name__ == "__main__":
    main()

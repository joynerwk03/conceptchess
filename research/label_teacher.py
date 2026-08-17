"""Label positions with an OUTSIDE evaluator's static evaluation.

Session 32 rejected distillation from this engine's OWN search: matching the
search better did not make the evaluation better, because the search's advantage
is tactical and tactics lie outside what a concept sum can represent. Fitting
towards it dragged parameters that do carry positional signal into compensating
for something they cannot express.

An outside evaluator is a different proposition. `research/eval_room.py`
measured that this evaluation is level with Stockfish 11's classical eval
(-2.96% outcome loss) and 16.94% behind a modern NNUE, with the gap spread
evenly across every interpretable bucket. That 16.94% is the only pool of
remaining evaluation Elo this project has ever managed to measure, and it is a
different function of the same board rather than a deeper search of it -- so it
is exactly the signal a static concept sum might be able to absorb some of.

**This does not weaken interpretability.** The model stays a sum of named
concepts, `evaluate()` still equals `evaluate_detailed().total`, the C eval still
mirrors the Python eval, and the search still maximises the number the breakdown
displays. Only the LABELS change, from "who won this game" to "what does a
stronger evaluator think of this position". What it gives up is that the
knowledge is no longer self-discovered, which is a question about what the
project is for rather than about the invariants -- and it is worth having the
measurement in hand either way.

The honest check stays the one from fit_to_search.py: whether fitting towards the
teacher also improves ordinary game-OUTCOME prediction, measured on an
INDEPENDENT generation run. If outcome loss gets worse while teacher distance
improves, the fit is chasing the teacher's quirks and is worth nothing.

    PYTHONPATH=. .venv/bin/python research/label_teacher.py --n 200000
"""
import argparse
import json
import multiprocessing as mp
import random

from research.eval_room import sf_chunk
from research.texel import ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel_all.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "research/data/teacher.jsonl"))
    ap.add_argument("--n", type=int, default=200000)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--engine", default="stockfish",
                    help="the teacher; its static eval is the label")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.data)]
    random.Random(20260817).shuffle(rows)
    rows = rows[:a.n]
    fens = [r["fen"] for r in rows]
    print(f"labelling {len(fens):,} positions with {a.engine}'s static eval")

    chunks = [(fens[i::a.workers], a.engine) for i in range(a.workers)]
    with mp.Pool(a.workers) as pool:
        parts = pool.map(sf_chunk, chunks)
    vals = [None] * len(fens)
    for i, part in enumerate(parts):
        vals[i::a.workers] = part

    kept = 0
    with open(a.out, "w") as fh:
        for r, v in zip(rows, vals):
            if v is None:                     # in check: the teacher declines
                continue
            fh.write(json.dumps({"fen": r["fen"], "res": r["res"],
                                 "sv": float(v)}) + "\n")
            kept += 1
    print(f"wrote {kept:,} labelled positions to {a.out} "
          f"({len(fens)-kept:,} skipped)")


if __name__ == "__main__":
    main()

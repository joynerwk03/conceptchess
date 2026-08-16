"""Label positions with the engine's own DEEP SEARCH score, not a game outcome.

Every fit in this project regresses on the result of the game a position came
from. That label is one bit summarising forty subsequent moves, so it is
enormously noisy per position: the reason ~100k positions are needed to resolve
anything, and the reason three weights drifted into chess nonsense in session 32
-- mate-drive fires only where the label is 1.0 whatever happens, so the
objective had no signal there at all.

A search score is a much lower-variance target for the same position. It is also
a STRONGER evaluator than the static evaluation being fitted -- that is precisely
why depth wins games -- so fitting the static eval towards it transfers what the
search discovers into the shallow nodes where pruning and ordering decisions are
actually made.

This is self-distillation and its limits should be stated plainly: the search
cannot teach the evaluation anything neither of them can see, so this will not
invent new chess knowledge. What it does is remove label noise and propagate
what the search already knows to the places the search cannot reach. It does not
break the self-reference loop -- only an outside label such as another engine's
evaluation would -- but it does replace a one-bit noisy target with a
hundred-centipawn-resolution one.

Scores are stored from WHITE's point of view, matching evaluate(), and mate
scores are dropped rather than clamped: they are not on the same scale and a
handful of them would dominate a squared-error fit.

    PYTHONPATH=. .venv/bin/python research/label_search.py --positions 40000
"""
import argparse
import json
import multiprocessing as mp
import os
import random

import chess

from research.texel import ROOT

_ENG = None
_MOVETIME = 0.2


def _engine():
    global _ENG
    if _ENG is None:
        from engine.engine import Engine
        os.environ["CC_THREADS"] = "1"
        _ENG = Engine(use_book=False, use_tablebase=False)
    return _ENG


def _label(row):
    b = chess.Board(row["fen"])
    r = _engine().best_move(b, movetime=_MOVETIME)
    if r.move is None:
        return None
    sc = r.score
    if abs(sc) > 20000:          # mate: a different scale, would dominate
        return None
    if b.turn == chess.BLACK:    # store from White's point of view, as evaluate()
        sc = -sc
    out = dict(row)
    out["sv"] = float(sc)
    return out


def _init(mt):
    global _MOVETIME
    _MOVETIME = mt
    _engine()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel_all.jsonl"))
    ap.add_argument("--positions", type=int, default=40000)
    ap.add_argument("--movetime", type=float, default=0.2)
    ap.add_argument("--workers", type=int, default=18)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--out", default=str(ROOT / "research/data/labelled.jsonl"))
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.data)]
    random.Random(a.seed).shuffle(rows)
    rows = rows[:a.positions]
    print(f"labelling {len(rows)} positions at {a.movetime}s each "
          f"on {a.workers} workers")

    n = dropped = 0
    with open(a.out, "w") as fh, mp.Pool(a.workers, initializer=_init,
                                         initargs=(a.movetime,)) as pool:
        for r in pool.imap_unordered(_label, rows, chunksize=16):
            if r is None:
                dropped += 1
                continue
            fh.write(json.dumps(r) + "\n")
            n += 1
            if n % 5000 == 0:
                print(f"  {n} labelled, {dropped} dropped (mate/no move)",
                      flush=True)
    print(f"wrote {n} labelled positions to {a.out} ({dropped} dropped)")


if __name__ == "__main__":
    main()

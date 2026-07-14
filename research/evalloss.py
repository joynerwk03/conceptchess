"""Eval loss: how closely our static evaluation matches Stockfish's.

loss = mean over positions of (winprob(our_cp) - winprob(sf_cp))^2,
winprob(cp) = 1 / (1 + 10^(-cp/400)). Bounded, scale-tolerant, and cheap:
one full pass over the ~2.2k-position set takes well under a second, so this
is the fast optimization target for evaluation experiments.

Usage: python -m research.evalloss          # prints train and val loss
"""

import json
from pathlib import Path

import chess

try:
    from engine.evaluation import evaluate, clear_caches
except ImportError:  # pre-session-2 engine versions have no cache API
    from engine.evaluation import evaluate

    def clear_caches():
        pass

DATA = Path(__file__).parent / "data"
_cache = {}


def _load(split):
    if split not in _cache:
        rows = [json.loads(ln) for ln in
                (DATA / f"evalset_{split}.jsonl").read_text().splitlines()]
        _cache[split] = [(chess.Board(r["fen"]), r["sf_cp"]) for r in rows]
    return _cache[split]


def winprob(cp):
    return 1.0 / (1.0 + 10.0 ** (-cp / 400.0))


def loss(split="val"):
    clear_caches()
    total = 0.0
    data = _load(split)
    for board, sf_cp in data:
        total += (winprob(evaluate(board)) - winprob(sf_cp)) ** 2
    return total / len(data)


if __name__ == "__main__":
    print(f"train loss: {loss('train'):.6f}")
    print(f"val loss:   {loss('val'):.6f}")

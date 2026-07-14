"""Compiled core: the C eval must stay identical to the Python eval.

This is the interpretability guarantee — the fast C search optimizes exactly
the number the Python explanation layer reports. If this test fails after an
eval change, regenerate core/eval_data.h and rebuild (see core/gen_eval_data.py),
or the C and Python evals have genuinely diverged.
"""

import random

import chess
import pytest

from engine import core
from engine.evaluation import evaluate

pytestmark = pytest.mark.skipif(not core.HAS_CORE, reason="compiled core not built")


def _positions(n=500, seed=7):
    rng = random.Random(seed)
    fens = [chess.STARTING_FEN]
    for _ in range(n):
        b = chess.Board()
        for _ in range(rng.randrange(2, 70)):
            ms = list(b.legal_moves)
            if not ms:
                break
            b.push(rng.choice(ms))
        fens.append(b.fen())
    return fens


def test_c_eval_matches_python():
    worst = 0.0
    for fen in _positions():
        py = float(evaluate(chess.Board(fen)))
        c = core.c_eval(fen)
        worst = max(worst, abs(py - c))
    assert worst < 0.01, f"C eval diverged from Python by {worst:.4f}cp"


def test_core_finds_mate():
    engine_move, score, depth, nodes, pv = core.search(
        chess.Board("6k1/5ppp/8/8/8/8/8/R6K w - - 0 1"), movetime=1.0)
    assert engine_move == chess.Move.from_uci("a1a8")
    assert score > 90000

"""Endgame technique: the mating-drive concept and basic mate conversion."""

import chess
import pytest

from engine.engine import Engine
from engine.evaluation import evaluate
from engine.concepts.mate_drive import MateDrive
from engine.context import EvalContext


def _md(fen):
    return MateDrive().score(EvalContext(chess.Board(fen)))


class TestMateDriveGradient:
    def test_zero_in_normal_positions(self):
        # Both sides have material -> concept must be silent.
        assert _md(chess.STARTING_FEN) == 0.0
        assert _md("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5") == 0.0

    def test_pushes_enemy_king_to_corner(self):
        # Same material (KR vs K); enemy king cornered should score higher for White.
        centre = _md("8/8/8/4k3/8/8/8/R3K3 w - - 0 1")
        corner = _md("k7/8/8/8/8/8/8/R3K3 w - - 0 1")
        assert corner > centre > 0

    def test_symmetric_sign(self):
        white_winning = _md("8/8/8/4k3/8/8/8/3QK3 w - - 0 1")
        black_winning = _md("3qk3/8/8/8/4K3/8/8/8 w - - 0 1")
        assert white_winning > 0 > black_winning

    def test_kpvk_not_triggered(self):
        # A lone pawn is not mating material — leave KPvK to other technique.
        assert _md("8/8/8/4k3/8/4P3/4K3/8 w - - 0 1") == 0.0

    def test_faithful(self):
        board = chess.Board("8/8/8/4k3/8/8/8/2B1KB2 w - - 0 1")
        from engine.evaluation import evaluate_detailed
        bd = evaluate_detailed(board)
        assert bd.total == pytest.approx(evaluate(board), abs=1e-6)
        for c in bd.concepts:
            assert sum(v for _, v in c.items) == pytest.approx(c.score, abs=1e-6), c.name


def _converts(fen, max_plies):
    """White mates the lone black king within max_plies under best defence."""
    board = chess.Board(fen)
    plies = 0
    while plies < max_plies and not board.is_game_over(claim_draw=True):
        r = Engine(use_book=False).best_move(board, movetime=0.2)
        if r.move is None:
            break
        board.push(r.move)
        plies += 1
        if board.is_game_over(claim_draw=True):
            break
        dr = Engine(use_book=False).best_move(board, movetime=0.1)
        if dr.move is None:
            break
        board.push(dr.move)
        plies += 1
    o = board.outcome(claim_draw=True)
    return o is not None and o.winner == chess.WHITE


@pytest.mark.slow
class TestMateConversion:
    # 120-ply budget: KBN takes ~80 plies under best defence and the winner
    # searches at 0.2s/move, so 100 was load-flaky (system load -> shallower
    # searches -> slower conversion). 120 still fails on any drawing bug --
    # the 50-move rule bites at ply 100 of shuffling regardless.
    def test_kbb_vs_k(self):
        assert _converts("8/8/8/4k3/8/8/8/2B1KB2 w - - 0 1", 120)

    def test_kbn_vs_k(self):
        assert _converts("8/8/8/4k3/8/8/8/2BNK3 w - - 0 1", 120)

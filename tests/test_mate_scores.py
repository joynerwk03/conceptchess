"""Mate-score correctness, and refusing to search illegal positions.

Both of these were live bugs found by William playing the analysis board, and
both are the kind that a strength gate would never have caught: the engine still
picked the right MOVE, it just reported nonsense about it and could not tell a
fast mate from a slow one.

1. **Mate scores are ply-relative.** `-S_MATE+ply` means "mated in `ply` plies
   from the root of THIS search", so storing it in a transposition table raw --
   which is shared across plies, across the moves of a game, and across the
   analysis board's repeated calls -- misreads it the moment the position is
   reached at a different distance from the root. It showed up as the analysis
   board reporting M9 for a mate in 2.

2. **Illegal positions must be refused, not searched.** `king_sq()` does `lsb()`
   on the king bitboard and `lsb(0)` is undefined; with a king missing it
   returns 64 and `attacked()` reads past the end of PAWN_ATK. If the side NOT
   to move is in check the root move list contains a king capture, which reaches
   the same place. Both segfault, and both are reachable from the GUI's
   paste-a-FEN box.
"""

import chess
import pytest

from engine import core
from engine.explain import mate_distance

# White to move, mates in 3 plies: Qf7+, king moves, Rh8#.
PRED = "8/3k4/7R/8/8/2K5/8/5Q2 w - - 0 1"
# Black to move and already in check; only Kc8/Kd8, both met by Rh8#.
MATED_IN_2 = "8/3k1Q2/7R/8/8/2K5/8/8 b - - 0 1"


class TestMateDistance:
    def test_mate_in_one_is_reported_as_one_ply(self):
        board = chess.Board("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
        _, score, _, _, _, _ = core.search(board, 1.0, 6)
        assert mate_distance(score) == 1

    def test_forced_mate_distance_is_exact(self):
        _, score, _, _, _, _ = core.search(chess.Board(PRED), 2.0, 12)
        assert mate_distance(score) == 3

    def test_being_mated_is_reported_from_the_loser_side(self):
        _, score, _, _, _, _ = core.search(chess.Board(MATED_IN_2), 2.0, 12)
        assert mate_distance(score) == -2

    def test_distance_survives_a_warm_transposition_table(self):
        """The actual bug: the same position, searched again after the TT has
        seen it at a DIFFERENT ply, must still report the same distance."""
        cold = core.search(chess.Board(MATED_IN_2), 2.0, 12)[1]
        core.search(chess.Board(PRED), 2.0, 12)          # stores it at ply 1
        warm = core.search(chess.Board(MATED_IN_2), 2.0, 12)[1]
        assert mate_distance(cold) == mate_distance(warm) == -2

    def test_predecessor_distance_after_the_successor_is_cached(self):
        """The reproduction that failed before the fix: searching the mate
        position first left a ply-0 score in the table, and the predecessor then
        read it at ply 1 and reported a 3-ply mate as 2."""
        core.search(chess.Board(MATED_IN_2), 2.0, 12)
        _, score, _, _, _, _ = core.search(chess.Board(PRED), 2.0, 12)
        assert mate_distance(score) == 3


class TestIllegalPositions:
    @pytest.mark.parametrize("fen, why", [
        ("8/3k4/7R/5Q2/8/2K5/8/8 w - - 0 1", "side not to move is in check"),
        ("8/3k4/8/8/8/8/8/8 w - - 0 1", "white king missing"),
        ("8/8/8/8/8/8/8/4K3 b - - 0 1", "black king missing"),
    ])
    def test_illegal_position_returns_no_move_instead_of_crashing(self, fen, why):
        move = core.search(chess.Board(fen), 0.5, 4)[0]
        assert move is None, why

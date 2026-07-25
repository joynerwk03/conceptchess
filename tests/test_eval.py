"""Evaluation invariants.

The faithfulness tests are the heart of this project: the explanation shown
to the user must be EXACTLY the evaluation the search used. Any eval change
that breaks these tests breaks the project's core promise.
"""

import random

import chess
import pytest

from engine.evaluation import evaluate, evaluate_detailed

FENS = [
    chess.STARTING_FEN,
    # Italian middlegame
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5",
    # Queenless middlegame
    "r1b1k2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1B1K2R w KQkq - 0 7",
    # Rook endgame
    "8/5pk1/6p1/8/8/6P1/5PK1/3r4 w - - 0 40",
    # Pawn endgame with passed pawn
    "8/8/4k3/8/2P5/8/5K2/8 w - - 0 50",
    # Sharp position, castled kings
    "r4rk1/1bq1bppp/p2ppn2/1p6/3NPP2/2N1B3/PPP1B1PP/R2Q1RK1 w - - 0 12",
]


def random_positions(n=25, plies=30, seed=42):
    rng = random.Random(seed)
    positions = []
    for _ in range(n):
        board = chess.Board()
        for _ in range(plies):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        positions.append(board)
    return positions


class TestFaithfulness:
    """Explanation must equal the evaluation used in search."""

    @pytest.mark.parametrize("fen", FENS)
    def test_detailed_total_matches_fast_eval(self, fen):
        board = chess.Board(fen)
        assert evaluate_detailed(board).total == pytest.approx(evaluate(board), abs=1e-6)

    @pytest.mark.parametrize("fen", FENS)
    def test_concept_items_sum_to_concept_score(self, fen):
        board = chess.Board(fen)
        for c in evaluate_detailed(board).concepts:
            assert sum(v for _, v in c.items) == pytest.approx(c.score, abs=1e-6), c.name

    def test_faithfulness_on_random_positions(self):
        for board in random_positions():
            bd = evaluate_detailed(board)
            assert bd.total == pytest.approx(evaluate(board), abs=1e-6), board.fen()
            for c in bd.concepts:
                assert sum(v for _, v in c.items) == pytest.approx(c.score, abs=1e-6), \
                    f"{c.name} @ {board.fen()}"


class TestSymmetry:
    """eval(mirrored position) == -eval(position)."""

    def test_symmetry(self):
        for board in random_positions(n=20):
            assert evaluate(board.mirror()) == pytest.approx(-evaluate(board), abs=1e-6), \
                board.fen()


class TestSanity:
    def test_startpos_near_zero(self):
        assert abs(evaluate(chess.Board())) < 50

    def test_extra_queen_is_big(self):
        board = chess.Board("rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        assert evaluate(board) > 700  # White has an extra queen

    def test_extra_rook_favors_black(self):
        board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/1NBQKBNR w Kkq - 0 1")
        assert evaluate(board) < -300  # White is missing a rook

    def test_passed_pawn_bonus(self):
        # Same material, White's c-pawn is passed, Black's h-pawn is blockaded by nothing
        with_passer = chess.Board("8/8/4k3/8/2P5/8/5K2/8 w - - 0 1")
        assert evaluate(with_passer) > 50


class TestModifiers:
    """Multiplicative modifiers: damp the eval but stay faithful (the marginal
    delta shown in the breakdown sums back to the total)."""

    from engine.weights import W
    OCB = "8/2k5/8/3b4/2P5/4B3/2K5/8 w - - 0 1"   # pure opp-bishops, White up a pawn
    MIXED = "8/2k5/8/3b4/2P5/4B1N1/2K5/8 w - - 0 1"  # + a knight -> not pure OCB

    def test_pure_ocb_is_damped(self):
        board = chess.Board(self.OCB)
        raw = sum(c.score for c in evaluate_detailed(board).concepts if c.name != "ocb")
        assert evaluate(board) == pytest.approx(raw * self.W["ocb.draw_scale"], abs=1e-6)
        assert 0 < evaluate(board) < raw   # White still better, but less so

    def test_ocb_breakdown_is_faithful(self):
        board = chess.Board(self.OCB)
        bd = evaluate_detailed(board)
        assert bd.total == pytest.approx(evaluate(board), abs=1e-6)
        ocb = [c for c in bd.concepts if c.name == "ocb"][0]
        assert sum(v for _, v in ocb.items) == pytest.approx(ocb.score, abs=1e-6)
        assert ocb.score < 0   # it reduced White's edge

    def test_modifier_inert_when_not_pure_ocb(self):
        board = chess.Board(self.MIXED)
        raw = sum(c.score for c in evaluate_detailed(board).concepts if c.name != "ocb")
        assert evaluate(board) == pytest.approx(raw, abs=1e-6)   # factor 1.0


class TestBackwardPawns:
    """A pawn whose neighbours have all advanced past it and whose stop square an
    enemy pawn covers is backward — penalized, doubly so on a half-open file."""

    def _bp(self, fen):
        from engine.concepts.backward_pawns import BackwardPawns
        from engine.context import EvalContext
        return BackwardPawns().score(EvalContext(chess.Board(fen)))

    def test_black_backward_pawn_penalized(self):
        # black d6 backward (c5,e5 advanced; d5 covered by white e4) -> good for White
        assert self._bp("rnbqkbnr/pp3ppp/3p4/2p1p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1") > 0

    def test_half_open_file_is_worse(self):
        # white e3 backward on a half-open file -> bad for White, doubled (-6*2)
        assert self._bp("4k3/8/8/3p1p2/3P1P2/4P3/8/4K3 w - - 0 1") == -12.0

    def test_no_false_positive_at_start(self):
        assert self._bp(chess.STARTING_FEN) == 0

    def test_symmetry(self):
        b = chess.Board("rnbqkbnr/pp3ppp/3p4/2p1p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1")
        assert evaluate(b.mirror()) == pytest.approx(-evaluate(b), abs=1e-6)


class TestConnectedPawns:
    """Connected pawns (phalanx or supported) score only when advanced (4th rank+)."""

    def _cp(self, fen):
        from engine.concepts.connected_pawns import ConnectedPawns
        from engine.context import EvalContext
        return ConnectedPawns().score(EvalContext(chess.Board(fen)))

    def test_advanced_phalanx_rewarded(self):
        # White duo on the 5th rank -> good for White
        assert self._cp("4k3/8/8/3PP3/8/8/8/4K3 w - - 0 1") > 0

    def test_starting_chain_scores_zero(self):
        assert self._cp(chess.STARTING_FEN) == 0

    def test_symmetry(self):
        b = chess.Board("4k3/8/8/4P3/3P4/8/8/4K3 w - - 0 1")
        assert evaluate(b.mirror()) == pytest.approx(-evaluate(b), abs=1e-6)

"""Search correctness: mates, tactics, time discipline."""

import time

import chess
import pytest

from engine.engine import Engine
from engine.search import MATE_THRESHOLD


@pytest.fixture
def engine():
    # Search tests exercise the search directly, not the opening book.
    return Engine(use_book=False)


class TestMates:
    def test_back_rank_mate_in_1(self, engine):
        board = chess.Board("6k1/5ppp/8/8/8/8/8/R6K w - - 0 1")
        r = engine.best_move(board, movetime=2.0)
        assert board.san(r.move) == "Ra8#"
        assert r.score > MATE_THRESHOLD

    def test_scholars_mate_in_1(self, engine):
        board = chess.Board(
            "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 0 1")
        r = engine.best_move(board, movetime=2.0)
        assert board.san(r.move) == "Qxf7#"

    def test_finds_forced_mate(self, engine):
        # Back-rank: Re8# is available.
        board = chess.Board("6k1/5ppp/8/8/8/8/1Q3PPP/4R1K1 w - - 0 1")
        r = engine.best_move(board, movetime=3.0)
        assert r.score > MATE_THRESHOLD

    def test_detects_being_mated(self, engine):
        # Black to move; whatever Black plays, Rb8# follows (Ra7 seals rank 7).
        board = chess.Board("7k/R7/8/7p/8/8/8/1R5K b - - 0 1")
        r = engine.best_move(board, movetime=2.0)
        assert r.score < -MATE_THRESHOLD


class TestTactics:
    def test_takes_hanging_queen(self, engine):
        board = chess.Board("rnb1kbnr/pppp1ppp/8/3q4/8/2N5/PPPP1PPP/R1BQKBNR w KQkq - 0 1")
        r = engine.best_move(board, movetime=2.0)
        assert r.move == chess.Move.from_uci("c3d5")

    def test_does_not_hang_queen(self, engine):
        # Any queen move to a square attacked by a defended pawn would be losing;
        # verify final eval isn't a queen down.
        board = chess.Board()
        board.push_san("e4"); board.push_san("e5")
        board.push_san("Nf3"); board.push_san("Nc6")
        r = engine.best_move(board, movetime=1.5)
        board.push(r.move)
        r2 = Engine().best_move(board, movetime=1.0)
        assert r2.score < 300  # opponent has no way to win big material


class TestDiscipline:
    def test_respects_time_limit(self, engine):
        board = chess.Board(
            "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5")
        start = time.perf_counter()
        engine.best_move(board, movetime=0.5)
        assert time.perf_counter() - start < 1.2

    def test_returns_legal_move(self, engine):
        board = chess.Board()
        r = engine.best_move(board, movetime=0.3)
        assert r.move in board.legal_moves

    def test_reaches_reasonable_depth(self, engine):
        r = engine.best_move(chess.Board(), movetime=2.0)
        assert r.depth >= 3

    def test_no_legal_moves(self, engine):
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")  # stalemate
        r = engine.best_move(board, movetime=0.5)
        assert r.move is None

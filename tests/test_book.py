"""Opening book: validity and integration."""

import chess

from engine.book import BOOK, lookup, LINES
from engine.engine import Engine


def test_all_book_moves_are_legal():
    """Every compiled book move is legal in its position (compilation parses
    SAN, so this is really a guard against future hand-edits)."""
    for epd, entries in BOOK.items():
        board = chess.Board(epd + " 0 1")
        legal = {m.uci() for m in board.legal_moves}
        for uci, name in entries:
            assert uci in legal, f"{uci} illegal in {epd} ({name})"


def test_book_covers_common_first_moves():
    board = chess.Board()
    move, name = lookup(board)
    assert move is not None and name
    # and a reply to 1.e4 exists
    board.push_san("e4")
    move, _ = lookup(board)
    assert move is not None


def test_engine_plays_book_then_searches():
    engine = Engine(book_seed=0)
    board = chess.Board()
    r = engine.best_move(board, movetime=0.2)
    assert r.book and r.depth == 0
    _, ex = engine.best_move_explained(board, movetime=0.2)
    assert ex["book"] and "Book move" in ex["explanation"][0]


def test_book_can_be_disabled():
    engine = Engine(use_book=False)
    r = engine.best_move(chess.Board(), movetime=0.3)
    assert not r.book and r.depth >= 1


def test_book_runs_out_into_search():
    # A deep, off-book position must fall through to a real search.
    engine = Engine(use_book=False)
    board = chess.Board("r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5")
    r = engine.best_move(board, movetime=0.3)
    assert not r.book and r.move in board.legal_moves

"""A small curated opening book of sound mainline theory.

Purpose: keep the engine out of early trouble and reach solid middlegames
(worth practical Elo at fast time controls, and it saves clock for the
positions that matter). Fully interpretable — a book move is reported as
such, by opening name, not as a search result.

The book is defined as SAN mainlines and compiled at import into a map from
position (board.epd, side-to-move aware, clocks ignored) to the set of book
moves for that position, tagged with the opening name. Because lines list
both sides' moves, the book works whichever colour the engine plays.
"""

import random

import chess

# name -> list of SAN mainlines (both sides' moves)
LINES = {
    "Ruy Lopez": [
        "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O",
        "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 O-O",
        "e4 e5 Nf3 Nc6 Bb5 Nf6 O-O Nxe4 d4 Nd6 Bxc6 dxc6 dxe5 Nf5",
    ],
    "Italian Game": [
        "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6 O-O O-O",
        "e4 e5 Nf3 Nc6 Bc4 Nf6 d3 Bc5 c3 d6 O-O O-O",
        "e4 e5 Nf3 Nc6 Bc4 Bc5 b4 Bxb4 c3 Ba5 d4",
    ],
    "Scotch Game": [
        "e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nf6 Nc3 Bb4 Nxc6 bxc6 Bd3 d5",
    ],
    "Petroff Defense": [
        "e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4 d4 d5 Bd3 Nc6 O-O Be7",
    ],
    "Sicilian Defense": [
        "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be2 e5 Nb3 Be7",
        "e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 Nf6 Nc3 e5 Ndb5 d6",
        "e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6 Nc3 Qc7",
        "e4 c5 Nc3 Nc6 g3 g6 Bg2 Bg7",
    ],
    "French Defense": [
        "e4 e6 d4 d5 Nc3 Nf6 e5 Nfd7 f4 c5",
        "e4 e6 d4 d5 Nd2 Nf6 e5 Nfd7 Bd3 c5 c3 Nc6",
        "e4 e6 d4 d5 exd5 exd5 Nf3 Nf6 Bd3 Bd6",
    ],
    "Caro-Kann Defense": [
        "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6 h4 h6 Nf3 Nd7",
        "e4 c6 d4 d5 exd5 cxd5 Bd3 Nc6 c3 Nf6",
    ],
    "Scandinavian Defense": [
        "e4 d5 exd5 Qxd5 Nc3 Qa5 d4 Nf6 Nf3 c6 Bc4 Bf5",
    ],
    "Queen's Gambit Declined": [
        "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 h6 Bh4 b6",
        "d4 d5 c4 e6 Nc3 Nf6 Nf3 Be7 Bg5 O-O e3 h6",
    ],
    "Slav Defense": [
        "d4 d5 c4 c6 Nf3 Nf6 Nc3 dxc4 a4 Bf5 e3 e6 Bxc4 Bb4",
        "d4 d5 c4 c6 Nc3 Nf6 Nf3 e6 e3 Nbd7",
    ],
    "Queen's Gambit Accepted": [
        "d4 d5 c4 dxc4 Nf3 Nf6 e3 e6 Bxc4 c5 O-O a6",
    ],
    "Nimzo-Indian Defense": [
        "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5 Nf3 c5",
        "d4 Nf6 c4 e6 Nc3 Bb4 Qc2 O-O a3 Bxc3 Qxc3 b6",
    ],
    "Queen's Indian Defense": [
        "d4 Nf6 c4 e6 Nf3 b6 g3 Ba6 b3 Bb4 Bd2 Be7",
    ],
    "King's Indian Defense": [
        "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6",
    ],
    "Grünfeld Defense": [
        "d4 Nf6 c4 g6 Nc3 d5 cxd5 Nxd5 e4 Nxc3 bxc3 Bg7 Nf3 c5",
    ],
    "English Opening": [
        "c4 e5 Nc3 Nf6 Nf3 Nc6 g3 d5 cxd5 Nxd5 Bg2 Nb6",
        "c4 Nf6 Nc3 e5 Nf3 Nc6 g3 d5 cxd5 Nxd5",
        "c4 c5 Nf3 Nf6 Nc3 Nc6 g3 g6 Bg2 Bg7",
    ],
    "Reti Opening": [
        "Nf3 d5 c4 e6 g3 Nf6 Bg2 Be7 O-O O-O",
        "Nf3 Nf6 c4 g6 g3 Bg7 Bg2 O-O",
    ],
}


def _compile(lines_by_name):
    """position epd -> list of (uci, name). Multiple lines through a position
    contribute multiple book moves (deduped by move)."""
    book = {}
    for name, lines in lines_by_name.items():
        for line in lines:
            board = chess.Board()
            for san in line.split():
                try:
                    move = board.parse_san(san)
                except ValueError:
                    raise ValueError(f"bad book move {san!r} in {name}: {line}")
                key = board.epd()
                bucket = book.setdefault(key, [])
                if not any(u == move.uci() for u, _ in bucket):
                    bucket.append((move.uci(), name))
                board.push(move)
    return book


BOOK = _compile(LINES)
MAX_BOOK_PLY = 16  # stop consulting the book past this many plies


def lookup(board, rng=None):
    """Return (move, opening_name) from the book, or (None, None)."""
    if board.ply() >= MAX_BOOK_PLY:
        return None, None
    entries = BOOK.get(board.epd())
    if not entries:
        return None, None
    rng = rng or random
    uci, name = rng.choice(entries)
    return chess.Move.from_uci(uci), name

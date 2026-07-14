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


# Breadth extension: more sidelines so common opponent replies stay in book,
# and a few more mainlines. Merged into LINES below.
_EXTRA = {
    "Ruy Lopez": [
        "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7 Re1 b5 Bb3 d6 c3 O-O h3 Na5 Bc2 c5 d4 Qc7",
        "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 b5 Bb3 Bc5 c3 d6 d4 Bb6",
        "e4 e5 Nf3 Nc6 Bb5 a6 Bxc6 dxc6 O-O f6 d4 exd4 Nxd4 c5",
    ],
    "Italian Game": [
        "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d3 d6 O-O O-O Re1 a6 a4 Ba7",
        "e4 e5 Nf3 Nc6 Bc4 Nf6 Ng5 d5 exd5 Na5 Bb5 c6 dxc6 bxc6",
        "e4 e5 Nf3 Nc6 Bc4 Nf6 d4 exd4 O-O Bc5 e5 d5",
    ],
    "Four Knights": [
        "e4 e5 Nf3 Nc6 Nc3 Nf6 Bb5 Bb4 O-O O-O d3 d6 Bg5 Bxc3",
    ],
    "Vienna Game": [
        "e4 e5 Nc3 Nf6 f4 d5 fxe5 Nxe4 Nf3 Be7",
    ],
    "Sicilian Najdorf": [
        "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be2 e5 Nb3 Be7 O-O O-O",
        "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Bg5 e6 f4 Be7",
        "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6 Be3 e5 Nb3 Be6",
    ],
    "Sicilian Dragon": [
        "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 g6 Be3 Bg7 f3 O-O Qd2 Nc6",
    ],
    "Sicilian Classical": [
        "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 Nc6 Bg5 e6 Qd2 Be7",
    ],
    "Sicilian Taimanov": [
        "e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6 Nc3 Qc7 Be2 a6 O-O Nf6",
    ],
    "Sicilian Rossolimo": [
        "e4 c5 Nf3 Nc6 Bb5 g6 O-O Bg7 Re1 e5 c3 Nge7",
        "e4 c5 Nf3 d6 Bb5 Nc6 O-O Bd7 Re1 Nf6",
    ],
    "French Winawer": [
        "e4 e6 d4 d5 Nc3 Bb4 e5 c5 a3 Bxc3 bxc3 Ne7 Qg4 O-O",
    ],
    "French Advance": [
        "e4 e6 d4 d5 e5 c5 c3 Nc6 Nf3 Qb6 a3 Nh6",
    ],
    "Caro-Kann Advance": [
        "e4 c6 d4 d5 e5 Bf5 Nf3 e6 Be2 c5 Be3 Qb6",
    ],
    "Caro-Kann Classical": [
        "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Nd7 Nf3 Ngf6 Nxf6 Nxf6 c3 Bg4",
    ],
    "Pirc Defense": [
        "e4 d6 d4 Nf6 Nc3 g6 Nf3 Bg7 Be2 O-O O-O c6",
    ],
    "Slav Defense": [
        "d4 d5 c4 c6 Nf3 Nf6 Nc3 dxc4 a4 Bf5 e3 e6 Bxc4 Bb4 O-O O-O",
        "d4 d5 c4 c6 Nc3 Nf6 e3 e6 Nf3 Nbd7 Bd3 dxc4 Bxc4 b5",
    ],
    "Semi-Slav Defense": [
        "d4 d5 c4 c6 Nf3 Nf6 Nc3 e6 e3 Nbd7 Bd3 dxc4 Bxc4 b5 Bd3 Bb7",
        "d4 d5 c4 e6 Nc3 Nf6 Nf3 c6 Bg5 h6 Bh4 dxc4",
    ],
    "Queen's Gambit Declined": [
        "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 Nbd7 Rc1 c6 Bd3 dxc4 Bxc4 Nd5",
        "d4 d5 c4 e6 Nc3 c5 cxd5 exd5 Nf3 Nc6 g3 Nf6 Bg2 Be7",
        "d4 d5 c4 e6 Nc3 Be7 Nf3 Nf6 Bf4 O-O e3 c5",
    ],
    "Catalan Opening": [
        "d4 Nf6 c4 e6 g3 d5 Bg2 Be7 Nf3 O-O O-O dxc4 Qc2 a6",
        "d4 Nf6 c4 e6 g3 d5 Bg2 dxc4 Nf3 Bb4 Bd2 a5",
    ],
    "King's Indian Defense": [
        "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O Be2 e5 O-O Nc6 d5 Ne7",
        "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 f3 O-O Be3 e5 d5 Nh5",
    ],
    "Grünfeld Defense": [
        "d4 Nf6 c4 g6 Nc3 d5 cxd5 Nxd5 e4 Nxc3 bxc3 Bg7 Bc4 c5 Ne2 Nc6",
    ],
    "Nimzo-Indian Defense": [
        "d4 Nf6 c4 e6 Nc3 Bb4 e3 O-O Bd3 d5 Nf3 c5 O-O Nc6 a3 Bxc3 bxc3 dxc4",
        "d4 Nf6 c4 e6 Nc3 Bb4 Qc2 d5 a3 Bxc3 Qxc3 Ne4",
    ],
    "English Opening": [
        "c4 e5 Nc3 Nf6 Nf3 Nc6 g3 d5 cxd5 Nxd5 Bg2 Nb6 O-O Be7 d3 O-O",
        "c4 c5 Nc3 Nc6 g3 g6 Bg2 Bg7 Nf3 Nf6 O-O O-O",
        "c4 e5 g3 Nf6 Bg2 d5 cxd5 Nxd5 Nc3 Nb6",
    ],
    "London System": [
        "d4 Nf6 Nf3 e6 Bf4 c5 e3 Nc6 c3 d5 Nbd2 Bd6",
        "d4 d5 Nf3 Nf6 Bf4 e6 e3 c5 c3 Nc6 Nbd2 Bd6",
    ],
    "Queen's Gambit Accepted": [
        "d4 d5 c4 dxc4 Nf3 Nf6 e3 e6 Bxc4 c5 O-O a6 dxc5 Qxd1 Rxd1 Bxc5",
    ],
}


def _merge():
    merged = {}
    for src in (LINES, _EXTRA):
        for name, lines in src.items():
            merged.setdefault(name, []).extend(lines)
    return merged


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


BOOK = _compile(_merge())
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

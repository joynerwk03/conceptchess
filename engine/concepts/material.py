"""Material: raw piece values."""

import chess

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

_PIECE_NAMES = {
    chess.PAWN: "pawns", chess.KNIGHT: "knights", chess.BISHOP: "bishops",
    chess.ROOK: "rooks", chess.QUEEN: "queens",
}


class Material:
    name = "material"
    display_name = "Material"

    def score(self, ctx):
        s = 0
        pieces = ctx.pieces
        for pt, val in PIECE_VALUES.items():
            if val:
                s += val * (len(pieces[chess.WHITE][pt]) - len(pieces[chess.BLACK][pt]))
        return s

    def details(self, ctx):
        items = []
        for pt, label in _PIECE_NAMES.items():
            diff = len(ctx.pieces[chess.WHITE][pt]) - len(ctx.pieces[chess.BLACK][pt])
            if diff:
                items.append((f"{label} ({diff:+d})", PIECE_VALUES[pt] * diff))
        return items

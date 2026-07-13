"""Material: raw piece values (tunable via engine.weights)."""

import chess

from engine.weights import W

_TYPES = (
    (chess.PAWN, "material.pawn", "pawns"),
    (chess.KNIGHT, "material.knight", "knights"),
    (chess.BISHOP, "material.bishop", "bishops"),
    (chess.ROOK, "material.rook", "rooks"),
    (chess.QUEEN, "material.queen", "queens"),
)


def piece_value(piece_type):
    for pt, key, _ in _TYPES:
        if pt == piece_type:
            return W[key]
    return 0


class Material:
    name = "material"
    display_name = "Material"

    def score(self, ctx):
        s = 0
        pieces = ctx.pieces
        for pt, key, _ in _TYPES:
            s += W[key] * (len(pieces[chess.WHITE][pt]) - len(pieces[chess.BLACK][pt]))
        return s

    def details(self, ctx):
        items = []
        for pt, key, label in _TYPES:
            diff = len(ctx.pieces[chess.WHITE][pt]) - len(ctx.pieces[chess.BLACK][pt])
            if diff:
                items.append((f"{label} ({diff:+d})", W[key] * diff))
        return items

"""Piece placement: piece-square tables (Michniewski's simplified eval tables).

Pawn and king tables are tapered between middlegame and endgame by ctx.phase.
Tables below are written visually (rank 8 at the top); converted at import.
"""

import chess

_PAWN_MG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      23,  18,  16,  28,  28,  16,  18,  23,
      47,  30,  20,  60,  60,  20,  30,  47,
      -6,  10,  20,  36,  36,  20,  10,  -6,
     -26, -16,  -5,  17,  17,  -5, -16, -26,
      -4,  -8,  -2,  -7,  -7,  -2,  -8,  -4,
     -16,   2, -16, -11, -11, -16,   2, -16,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_PAWN_EG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      85,  86,  46,  48,  48,  46,  86,  85,
      65,  71,  38,  30,  30,  38,  71,  65,
      47,  30,  36,  12,  12,  36,  30,  47,
      23,  23,   2,   8,   8,   2,  23,  23,
      15,   1,  29,  21,  21,  29,   1,  15,
      18,   6,  17,  18,  18,  17,   6,  18,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_KNIGHT_VIS = [
     -44, -49, -24, -18, -18, -24, -49, -44,
     -49, -12,  -7,  -2,  -2,  -7, -12, -49,
      -5,  -4,  20,  35,  35,  20,  -4,  -5,
     -12,  10,  23,  24,  24,  23,  10, -12,
      -8,   4,  24,  10,  10,  24,   4,  -8,
     -71, -15,   0,  14,  14,   0, -15, -71,
     -30, -43,   6, -17, -17,   6, -43, -30,
     -61, -75, -41, -40, -40, -41, -75, -61,
]

_BISHOP_VIS = [
     -34,  -4,  -6,  -6,  -6,  -6,  -4, -34,
      16,   9,   9,  13,  13,   9,   9,  16,
      -5,   2,   6,  15,  15,   6,   2,  -5,
       3,   2,   0,  13,  13,   0,   2,   3,
       8,  10,  -2,  17,  17,  -2,  10,   8,
       3,  23,  14,   1,   1,  14,  23,   3,
       0,   3,  10,   2,   2,  10,   3,   0,
     -29,  -4, -20, -28, -28, -20,  -4, -29,
]

_ROOK_VIS = [
       8,   7,   3,  -7,  -7,   3,   7,   8,
       1,  21,  -1,   2,   2,  -1,  21,   1,
      23,  16,  21,  21,  21,  21,  16,  23,
       7,  31,  23,  21,  21,  23,  31,   7,
      -2, -19,  -8,  -7,  -7,  -8, -19,  -2,
     -31, -18,  -5,  -9,  -9,  -5, -18, -31,
     -20, -24, -19, -16, -16, -19, -24, -20,
     -10,   1,  12,   4,   4,  12,   1, -10,
]

_QUEEN_VIS = [
      -7,   1,  -3,   4,   4,  -3,   1,  -7,
       7,  10,  12,  21,  21,  12,  10,   7,
      16,   3,  24,  39,  39,  24,   3,  16,
       4,  12,  -4,   9,   9,  -4,  12,   4,
      -2,   3, -11,  -7,  -7, -11,   3,  -2,
     -15, -12,   0,  -1,  -1,   0, -12, -15,
     -31, -31,   1, -21, -21,   1, -31, -31,
     -10,   0, -19,   5,   5, -19,   0, -10,
]

_KING_MG_VIS = [
     -25, -33, -33, -41, -40, -33, -33, -30,
     -10, -27, -16, -30, -26, -16, -18, -11,
     -10, -16, -29, -26, -39, -15, -15,  -9,
     -32, -39, -60, -75, -48, -57, -38, -50,
     -34, -24, -21, -57, -54, -26, -20, -17,
       6,   0,   1,  -5,  -4, -23,   6,   2,
      30,  19, -12, -10, -11,   1,   3,  15,
      17,  32,  20, -12,  11,  -1,  19,   6,
]

_KING_EG_VIS = [
     -41, -32, -24, -16, -15, -24, -33, -40,
     -14,  -8,  10,  27,  20,  11,  -2, -13,
     -15,   2,  25,  59,  39,  57,  16,  -9,
     -12,  11,  45,  32,  50,  46,  17, -13,
     -36,   8,  36,  38,  28,  31,  13, -10,
     -31,  -2,   6,  13,  16,  -2,  -1, -35,
     -57, -27,  -8,  12,  -8,  -5, -15, -55,
     -59, -59, -32, -50, -51, -26, -43, -88,
]


def _from_visual(vis):
    """Visual tables list a8..h1; index by square (a1=0) for White."""
    return [vis[chess.square_mirror(sq)] for sq in chess.SQUARES]


PAWN_MG = _from_visual(_PAWN_MG_VIS)
PAWN_EG = _from_visual(_PAWN_EG_VIS)
KNIGHT = _from_visual(_KNIGHT_VIS)
BISHOP = _from_visual(_BISHOP_VIS)
ROOK = _from_visual(_ROOK_VIS)
QUEEN = _from_visual(_QUEEN_VIS)
KING_MG = _from_visual(_KING_MG_VIS)
KING_EG = _from_visual(_KING_EG_VIS)

_FLAT = {chess.KNIGHT: KNIGHT, chess.BISHOP: BISHOP, chess.ROOK: ROOK, chess.QUEEN: QUEEN}
_SCALE_KEY = {chess.PAWN: "pst.pawn", chess.KNIGHT: "pst.knight",
              chess.BISHOP: "pst.bishop", chess.ROOK: "pst.rook",
              chess.QUEEN: "pst.queen", chess.KING: "pst.king"}

from engine.weights import W, wt


class PiecePlacement:
    name = "placement"
    display_name = "Piece placement"

    def score(self, ctx):
        phase = ctx.phase
        s = 0.0
        pieces = ctx.pieces
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            flip = 0 if color == chess.WHITE else 56
            for pt, table in _FLAT.items():
                w = wt(_SCALE_KEY[pt], ctx.phase)
                for sq in pieces[color][pt]:
                    s += sign * w * table[sq ^ flip]
            w = wt("pst.pawn", ctx.phase)
            for sq in pieces[color][chess.PAWN]:
                i = sq ^ flip
                s += sign * w * (phase * PAWN_MG[i] + (1 - phase) * PAWN_EG[i])
            ksq = ctx.king_sq[color]
            if ksq is not None:
                i = ksq ^ flip
                s += sign * wt("pst.king", ctx.phase) * (phase * KING_MG[i] + (1 - phase) * KING_EG[i])
        return s

    def details(self, ctx):
        phase = ctx.phase
        items = []
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            flip = 0 if color == chess.WHITE else 56
            for pt in chess.PIECE_TYPES:
                for sq in ctx.pieces[color][pt]:
                    i = sq ^ flip
                    if pt == chess.PAWN:
                        v = phase * PAWN_MG[i] + (1 - phase) * PAWN_EG[i]
                    elif pt == chess.KING:
                        v = phase * KING_MG[i] + (1 - phase) * KING_EG[i]
                    else:
                        v = _FLAT[pt][i]
                    v *= wt(_SCALE_KEY[pt], ctx.phase)
                    if v:
                        label = f"{cname} {chess.piece_name(pt)} on {chess.square_name(sq)}"
                        items.append((label, sign * v))
        return items

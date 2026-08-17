"""Piece placement: piece-square tables (Michniewski's simplified eval tables).

Pawn and king tables are tapered between middlegame and endgame by ctx.phase.
Tables below are written visually (rank 8 at the top); converted at import.
"""

import chess

_PAWN_MG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      27,  24,  23,  31,  31,  23,  24,  27,
      54,  31,  29,  76,  76,  29,  31,  54,
      -6,  12,  28,  39,  39,  28,  12,  -6,
     -13, -10,   7,  27,  27,   7, -10, -13,
       2,   4,   0,   4,   4,   0,   4,   2,
      -7,   9,  -1, -13, -13,  -1,   9,  -7,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_PAWN_EG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      91,  88,  51,  48,  48,  51,  88,  91,
      75,  78,  48,  40,  40,  48,  78,  75,
      56,  44,  40,  22,  22,  40,  44,  56,
      40,  27,  13,  20,  20,  13,  27,  40,
      24,  11,  27,  24,  24,  27,  11,  24,
      33,  18,  32,  27,  27,  32,  18,  33,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_KNIGHT_VIS = [
     -46, -49, -24, -16, -16, -24, -49, -46,
     -49,  -8,  -2,  -1,  -1,  -2,  -8, -49,
      -4,  -6,  22,  43,  43,  22,  -6,  -4,
       2,  12,  37,  37,  37,  37,  12,   2,
     -10,   8,  13,   6,   6,  13,   8, -10,
     -78, -15, -10,  19,  19, -10, -15, -78,
     -41, -48,  -6, -28, -28,  -6, -48, -41,
     -64, -97, -46, -41, -41, -46, -97, -64,
]

_BISHOP_VIS = [
     -32,  -6, -10,  -4,  -4, -10,  -6, -32,
       5,  -2,   3,   5,   5,   3,  -2,   5,
       5,  12,  -1,  16,  16,  -1,  12,   5,
      10,  10,   7,  18,  18,   7,  10,  10,
       6,   9,   6,  17,  17,   6,   9,   6,
       7,  13,   8,   8,   8,   8,  13,   7,
       0,   9,   7,   8,   8,   7,   9,   0,
     -36,  -5, -18, -22, -22, -18,  -5, -36,
]

_ROOK_VIS = [
      20,  16,   7,  -2,  -2,   7,  16,  20,
      11,  20,   9,  13,  13,   9,  20,  11,
      31,  19,  26,  32,  32,  26,  19,  31,
      -5,  26,  17,  19,  19,  17,  26,  -5,
     -13, -14, -12,  -7,  -7, -12, -14, -13,
     -24, -21, -17, -10, -10, -17, -21, -24,
     -33, -29, -21, -19, -19, -21, -29, -33,
     -13,  -7,  -1,   2,   2,  -1,  -7, -13,
]

_QUEEN_VIS = [
      -6,   5,  -2,   7,   7,  -2,   5,  -6,
       3,   5,  10,  22,  22,  10,   5,   3,
       9,   7,  26,  39,  39,  26,   7,   9,
       2,  14,   3,   9,   9,   3,  14,   2,
      -2,   8,  -7,   3,   3,  -7,   8,  -2,
     -11, -12,   8,   4,   4,   8, -12, -11,
     -31, -35,   6, -23, -23,   6, -35, -31,
     -16,  -4, -33,  -7,  -7, -33,  -4, -16,
]

_KING_MG_VIS = [
     -25, -32, -33, -40, -40, -33, -33, -30,
     -10, -27, -15, -29, -26, -15, -18, -11,
      -9, -14, -28, -25, -38, -14, -13,  -9,
     -32, -38, -57, -75, -48, -57, -35, -49,
     -36, -22, -20, -57, -54, -25, -23, -20,
       4,  -1,   2, -11,   5, -22,  10,  -3,
      31,  23,  -2,  -9, -13,   1,   1,  13,
       2,  23,  18, -21,   8,  -3,  28,  11,
]

_KING_EG_VIS = [
     -41, -28, -23, -12, -13, -23, -31, -39,
     -14,  -4,  14,  31,  22,  15,   0, -14,
      -9,  13,  32,  61,  44,  59,  27,  -9,
      -9,  13,  47,  34,  49,  44,  25,  -6,
     -36,  15,  28,  31,  29,  25,  11, -14,
     -37,  -8,   0,   4,   9,  -2,  -3, -38,
     -62, -30, -13,   9, -11,  -5, -24, -43,
     -73, -52, -39, -47, -53, -36, -45, -87,
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

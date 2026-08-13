"""Piece placement: piece-square tables (Michniewski's simplified eval tables).

Pawn and king tables are tapered between middlegame and endgame by ctx.phase.
Tables below are written visually (rank 8 at the top); converted at import.
"""

import chess

_PAWN_MG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      28,  22,  20,  23,  23,  20,  22,  28,
      39,  25,  24,  50,  50,  24,  25,  39,
      -4,  12,  25,  44,  44,  25,  12,  -4,
     -26, -20,  -3,  19,  19,  -3, -20, -26,
      -2, -10,  -4,  -9,  -9,  -4, -10,  -2,
     -15,   0, -13, -13, -13, -13,   0, -15,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_PAWN_EG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      70,  71,  57,  59,  59,  57,  71,  70,
      57,  59,  47,  37,  37,  47,  59,  57,
      39,  37,  43,  14,  14,  43,  37,  39,
      19,  19,   4,  10,  10,   4,  19,  19,
      19,  -1,  24,  18,  18,  24,  -1,  19,
      15,   8,  14,  15,  15,  14,   8,  15,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_KNIGHT_VIS = [
     -54, -41, -29, -22, -22, -29, -41, -54,
     -41, -15,  -9,   0,   0,  -9, -15, -41,
      -7,  -2,  25,  42,  42,  25,  -2,  -7,
     -14,  10,  28,  29,  29,  28,  10, -14,
     -10,   6,  20,  12,  12,  20,   6, -10,
     -65, -19,  -2,  12,  12,  -2, -19, -65,
     -37, -44,   4, -14, -14,   4, -44, -37,
     -51, -62, -34, -33, -33, -34, -62, -51,
]

_BISHOP_VIS = [
     -29,  -6,  -4,  -8,  -8,  -4,  -6, -29,
      13,  11,   7,  13,  13,   7,  11,  13,
      -3,   0,   8,  13,  13,   8,   0,  -3,
       1,   4,  -2,  16,  16,  -2,   4,   1,
       6,  12,   0,  14,  14,   0,  12,   6,
       5,  24,  12,   3,   3,  12,  24,   5,
       2,   1,   8,   0,   0,   8,   1,   2,
     -36,  -6, -21, -23, -23, -21,  -6, -36,
]

_ROOK_VIS = [
       6,   5,   1,  -9,  -9,   1,   5,   6,
       3,  19,  -3,   0,   0,  -3,  19,   3,
      19,  20,  18,  26,  26,  18,  20,  19,
       9,  26,  21,  26,  26,  21,  26,   9,
       0, -16,  -6,  -5,  -5,  -6, -16,   0,
     -29, -22,  -7, -11, -11,  -7, -22, -29,
     -24, -20, -16, -20, -20, -16, -20, -24,
     -10,   3,  10,   6,   6,  10,   3, -10,
]

_QUEEN_VIS = [
      -9,  -1,  -5,   2,   2,  -5,  -1,  -9,
       5,  12,  14,  18,  18,  14,  12,   5,
      13,   5,  25,  32,  32,  25,   5,  13,
       4,  10,  -2,  11,  11,  -2,  10,   4,
       1,   2, -13,  -5,  -5, -13,   2,  -4,
     -19,  -9,   2,  -1,  -1,   2, -14, -19,
     -26, -26,   4, -26, -26,  -1, -26, -26,
     -12,  -2, -16,   7,   7, -16,  -2, -12,
]

_KING_MG_VIS = [
     -30, -40, -40, -50, -49, -40, -40, -30,
     -12, -22, -20, -29, -31, -20, -22, -12,
     -12, -20, -24, -31, -32, -19, -19, -11,
     -39, -48, -50, -62, -59, -52, -47, -42,
     -29, -29, -26, -47, -45, -32, -24, -21,
       4,  -2,  -1,  -3,  -2, -19,   4,   0,
      25,  16, -15, -12, -13,   3,   5,  19,
      14,  38,  23, -10,  10,  -3,  23,   4,
]

_KING_EG_VIS = [
     -50, -39, -29, -20, -18, -29, -40, -49,
     -17,  -6,   8,  22,  17,   9,  -4, -16,
     -18,   4,  30,  49,  48,  47,  13, -11,
     -14,   9,  49,  39,  61,  38,  14, -16,
     -30,   6,  43,  47,  35,  32,  14, -12,
     -38,  -4,   8,  16,  20,   0,  -3, -39,
     -47, -33, -10,  10, -10,  -3, -18, -48,
     -59, -49, -33, -42, -46, -31, -46, -73,
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

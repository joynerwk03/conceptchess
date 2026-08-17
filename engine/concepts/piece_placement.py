"""Piece placement: piece-square tables (Michniewski's simplified eval tables).

Pawn and king tables are tapered between middlegame and endgame by ctx.phase.
Tables below are written visually (rank 8 at the top); converted at import.
"""

import chess

_PAWN_MG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      37,  40,  39,  33,  33,  39,  40,  37,
      45,  43,  46,  78,  78,  46,  43,  45,
       2,  10,  36,  41,  41,  36,  10,   2,
     -14, -15,  18,  26,  26,  18, -15, -14,
      -8,   0,   4,   1,   1,   4,   0,  -8,
     -13,   9,   9, -25, -25,   9,   9, -13,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_PAWN_EG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      58,  56,  28,  26,  26,  28,  56,  58,
      46,  48,  26,  20,  20,  26,  48,  46,
      32,  23,  20,   6,   6,  20,  23,  32,
      20,  10,   0,   5,   5,   0,  10,  20,
       8,   0,  10,  15,  15,  10,   0,   8,
      15,  14,  25,  41,  41,  25,  14,  15,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_KNIGHT_MG_VIS = [
     -68, -71, -40,  -2,  -2, -40, -71, -68,
     -39,  -2,   8,   9,   9,   8,  -2, -39,
       7,   6,  38,  64,  64,  38,   6,   7,
      12,  18,  56,  40,  40,  56,  18,  12,
     -19,  20,  26,  18,  18,  26,  20, -19,
     -68,  -9,   2,  22,  22,   2,  -9, -68,
     -61, -52, -18, -15, -15, -18, -52, -61,
     -90, -90, -68, -26, -26, -68, -90, -90,
]

_KNIGHT_EG_VIS = [
     -68, -71,  -8,  -2,  -2,  -8, -71, -68,
     -34, -19,   8,   9,   9,   8, -19, -34,
       7,   6,  38,  39,  39,  38,   6,   7,
      12,  25,  48,  56,  56,  48,  25,  12,
       2,  20,  26,  18,  18,  26,  20,   2,
     -48,  -6, -11,  34,  34, -11,  -6, -48,
     -61, -26,  -6, -11, -11,  -6, -26, -61,
     -90, -86, -24, -21, -21, -24, -86, -90,
]

_BISHOP_MG_VIS = [
     -14,   6, -20,   7,   7, -20,   6, -14,
      -6, -12,  -2,  -6,  -6,  -2, -12,  -6,
      16,  25,   9,  19,  19,   9,  25,  16,
      16,  22,  19,  32,  32,  19,  22,  16,
      15,  21,  17,  27,  27,  17,  21,  15,
      16,  13,  11,  17,  17,  11,  13,  16,
      10,  12,  19,   7,   7,  19,  12,  10,
     -17,   6, -10,  -6,  -6, -10,   6, -17,
]

_BISHOP_EG_VIS = [
     -20,   6,   2,   7,   7,   2,   6, -20,
       3,   8,   3,  16,  16,   3,   8,   3,
       7,   9,   3,  18,  18,   3,   9,   7,
       8,   2,  17,  13,  13,  17,   2,   8,
      12,  11,   8,   6,   6,   8,  11,  12,
       3,  12,   4,   8,   8,   4,  12,   3,
       3,  -3,   4,   5,   5,   4,  -3,   3,
     -24,  -2,  -4,  -6,  -6,  -4,  -2, -24,
]

_ROOK_MG_VIS = [
      35,   5,   2,   1,   1,   2,   5,  35,
      -2,   5,  -1,   4,   4,  -1,   5,  -2,
      13,   9,  37,  14,  14,  37,   9,  13,
     -14,  10,   6,   4,   4,   6,  10, -14,
     -22, -17, -22, -17, -17, -22, -17, -22,
     -29, -24, -23, -21, -21, -23, -24, -29,
     -38, -38, -28, -21, -21, -28, -38, -38,
     -24, -19, -11,  -8,  -8, -11, -19, -24,
]

_ROOK_EG_VIS = [
      10,  30,  19,   8,   8,  19,  30,  10,
      -2,   5,  -3,   0,   0,  -3,   5,  -2,
      13,  18,  10,  14,  14,  10,  18,  13,
       6,  11,  14,   4,   4,  14,  11,   6,
       0,   0,   1,  -8,  -8,   1,   0,   0,
      -8,  -6, -10, -15, -15, -10,  -6,  -8,
     -20, -12, -12, -21, -21, -12, -12, -20,
      -5,  -6,  -5,  -8,  -8,  -5,  -6,  -5,
]

_QUEEN_MG_VIS = [
       6,  16,   8,  19,  19,   8,  16,   6,
      -8,  -6,  -2,  11,  11,  -2,  -6,  -8,
      -3,  -5,  25,  19,  19,  25,  -5,  -3,
      -5,   0,  14,   2,   2,  14,   0,  -5,
     -12,  11,  -2,  -2,  -2,  -2,  11, -12,
     -17, -15,   9,  -3,  -3,   9, -15, -17,
     -17, -18,   2,  -7,  -7,   2, -18, -17,
     -23, -15, -29,  -9,  -9, -29, -15, -23,
]

_QUEEN_EG_VIS = [
       6,  16,   8,  19,  19,   8,  16,   6,
      14,  -6,  22,  38,  38,  22,  -6,  14,
      15,  19,  42,  33,  33,  42,  19,  15,
       3,  28,  14,  21,  21,  14,  28,   3,
       8,  -4,   5,  14,  14,   5,  -4,   8,
     -24,   1,  -4,  -7,  -7,  -4,   1, -24,
     -13, -54,  -6, -39, -39,  -6, -54, -13,
     -30, -15, -51, -19, -19, -51, -15, -30,
]

_KING_MG_VIS = [
     -41, -14, -39, -20, -20, -15, -15, -48,
     -22, -44,  -1, -12, -10,  -1,  -4, -24,
     -14,   0, -16, -38, -58,   0,   0,   3,
     -48, -54, -33, -67, -70, -34, -16, -61,
     -42,  -6,  -5, -52, -31, -17,  -9,  -9,
       2,   3,  -7,  -9,  -6, -22,  16, -14,
      23,  12,   8, -16, -10,  -1,  11,  14,
      -8,  19,  15, -10,   9,  -7,  29,  11,
]

_KING_EG_VIS = [
     -61, -33, -39, -25,   0,  -7, -13, -59,
     -28, -15,   0,  13,  14,   1,  10, -28,
     -13,  25,  30,  39,  41,  37,  44,   3,
     -21,  26,  25,  33,  43,  32,  17,   0,
     -17,   7,  14,  27,  19,  19,  -2, -15,
     -31,  -8,   8,  10,  11,   8, -10, -25,
     -54, -19,  -8,   6,   2,  -4, -18, -47,
     -48, -42, -23, -25, -32, -22, -48, -72,
]


def _from_visual(vis):
    """Visual tables list a8..h1; index by square (a1=0) for White."""
    return [vis[chess.square_mirror(sq)] for sq in chess.SQUARES]


PAWN_MG = _from_visual(_PAWN_MG_VIS)
PAWN_EG = _from_visual(_PAWN_EG_VIS)
# Knight, bishop, rook and queen are phase-tapered like pawns and kings. Both
# halves start from the single flat table these replaced, so the evaluation is
# bit-identical until a tuner moves them apart: the taper is capacity, not a new
# opinion about chess.
KNIGHT_MG = _from_visual(_KNIGHT_MG_VIS)
KNIGHT_EG = _from_visual(_KNIGHT_EG_VIS)
BISHOP_MG = _from_visual(_BISHOP_MG_VIS)
BISHOP_EG = _from_visual(_BISHOP_EG_VIS)
ROOK_MG = _from_visual(_ROOK_MG_VIS)
ROOK_EG = _from_visual(_ROOK_EG_VIS)
QUEEN_MG = _from_visual(_QUEEN_MG_VIS)
QUEEN_EG = _from_visual(_QUEEN_EG_VIS)
KING_MG = _from_visual(_KING_MG_VIS)
KING_EG = _from_visual(_KING_EG_VIS)

_TAPERED = {chess.KNIGHT: (KNIGHT_MG, KNIGHT_EG),
            chess.BISHOP: (BISHOP_MG, BISHOP_EG),
            chess.ROOK: (ROOK_MG, ROOK_EG),
            chess.QUEEN: (QUEEN_MG, QUEEN_EG)}
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
            for pt, (mg, eg) in _TAPERED.items():
                w = wt(_SCALE_KEY[pt], ctx.phase)
                for sq in pieces[color][pt]:
                    i = sq ^ flip
                    s += sign * w * (phase * mg[i] + (1 - phase) * eg[i])
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
                        mg, eg = _TAPERED[pt]
                        v = phase * mg[i] + (1 - phase) * eg[i]
                    v *= wt(_SCALE_KEY[pt], ctx.phase)
                    if v:
                        label = f"{cname} {chess.piece_name(pt)} on {chess.square_name(sq)}"
                        items.append((label, sign * v))
        return items

"""Piece placement: piece-square tables (Michniewski's simplified eval tables).

Pawn and king tables are tapered between middlegame and endgame by ctx.phase.
Tables below are written visually (rank 8 at the top); converted at import.
"""

import chess

_PAWN_MG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      24,  24,  24,  24,  24,  24,  24,  24,
      22,  22,  32,  42,  42,  32,  22,  22,
       9,   9,  14,  29,  29,  14,   9,   9,
     -12, -12, -12,   8,   8, -12, -12, -12,
      -3, -13, -18,  -8,  -8, -18, -13,  -3,
      -7,  -2,  -2, -32, -32,  -2,  -2,  -7,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_PAWN_EG_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
      64,  64,  64,  64,  64,  64,  64,  64,
      50,  50,  50,  50,  50,  50,  50,  50,
      34,  34,  34,  34,  34,  34,  34,  34,
       7,   7,   7,   7,   7,   7,   7,   7,
      13,  13,  13,  13,  13,  13,  13,  13,
       4,   4,   4,   4,   4,   4,   4,   4,
       0,   0,   0,   0,   0,   0,   0,   0,
]

_KNIGHT_VIS = [
     -50, -40, -30, -30, -30, -30, -40, -50,
     -44, -24,  -4,  -4,  -4,  -4, -24, -44,
     -18,  12,  22,  27,  27,  22,  12, -18,
     -18,  17,  27,  32,  32,  27,  17, -18,
     -18,  12,  27,  32,  32,  27,  12, -18,
     -42,  -7,  -2,   3,   3,  -2,  -7, -42,
     -48, -28,  -8,  -3,  -3,  -8, -28, -48,
     -50, -40, -30, -30, -30, -30, -40, -50,
]

_BISHOP_VIS = [
     -20, -10, -10, -10, -10, -10, -10, -20,
       2,  12,  12,  12,  12,  12,  12,   2,
      -6,   4,   9,  14,  14,   9,   4,  -6,
      -6,   9,   9,  14,  14,   9,   9,  -6,
      -6,   4,  14,  14,  14,  14,   4,  -6,
      -6,  14,  14,  14,  14,  14,  14,  -6,
      -6,   9,   4,   4,   4,   4,   9,  -6,
     -20, -10, -10, -10, -10, -10, -10, -20,
]

_ROOK_VIS = [
       0,   0,   0,   0,   0,   0,   0,   0,
       5,  10,  10,  10,  10,  10,  10,   5,
       7,  12,  12,  12,  12,  12,  12,   7,
       7,  12,  12,  12,  12,  12,  12,   7,
     -13,  -8,  -8,  -8,  -8,  -8,  -8, -13,
     -17, -12, -12, -12, -12, -12, -12, -17,
     -13,  -8,  -8,  -8,  -8,  -8,  -8, -13,
       0,   0,   0,   5,   5,   0,   0,   0,
]

_QUEEN_VIS = [
     -20, -10, -10,  -5,  -5, -10, -10, -20,
       2,  12,  12,  12,  12,  12,  12,   2,
       2,  12,  17,  17,  17,  17,  12,   2,
      -5,   0,   5,   5,   5,   5,   0,  -5,
     -12, -12,  -7,  -7,  -7,  -7, -12, -17,
     -22,  -7,  -7,  -7,  -7,  -7, -12, -22,
     -22, -12,  -7, -12, -12, -12, -12, -22,
     -20, -10, -10,  -5,  -5, -10, -10, -20,
]

_KING_MG_VIS = [
     -30, -40, -40, -50, -50, -40, -40, -30,
     -12, -22, -22, -32, -32, -22, -22, -12,
     -12, -22, -22, -32, -32, -22, -22, -12,
     -40, -50, -50, -60, -60, -50, -50, -40,
     -20, -30, -30, -40, -40, -30, -30, -20,
       2,  -8,  -8,  -8,  -8,  -8,  -8,   2,
      12,  12,  -8,  -8,  -8,  -8,  12,  12,
      20,  30,  10,   0,   0,  10,  30,  20,
]

_KING_EG_VIS = [
     -50, -40, -30, -20, -20, -30, -40, -50,
     -18,  -8,   2,  12,  12,   2,  -8, -18,
     -18,   2,  32,  42,  42,  32,   2, -18,
     -17,   3,  43,  53,  53,  43,   3, -17,
     -17,   3,  43,  53,  53,  43,   3, -17,
     -38, -18,  12,  22,  22,  12, -18, -38,
     -30, -30,   0,   0,   0,   0, -30, -30,
     -50, -30, -30, -30, -30, -30, -50, -50,
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

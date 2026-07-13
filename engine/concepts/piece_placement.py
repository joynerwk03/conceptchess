"""Piece placement: piece-square tables (Michniewski's simplified eval tables).

Pawn and king tables are tapered between middlegame and endgame by ctx.phase.
Tables below are written visually (rank 8 at the top); converted at import.
"""

import chess

_PAWN_MG_VIS = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
]

_PAWN_EG_VIS = [
     0,  0,  0,  0,  0,  0,  0,  0,
    80, 80, 80, 80, 80, 80, 80, 80,
    50, 50, 50, 50, 50, 50, 50, 50,
    30, 30, 30, 30, 30, 30, 30, 30,
    15, 15, 15, 15, 15, 15, 15, 15,
     5,  5,  5,  5,  5,  5,  5,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,
]

_KNIGHT_VIS = [
   -50,-40,-30,-30,-30,-30,-40,-50,
   -40,-20,  0,  0,  0,  0,-20,-40,
   -30,  0, 10, 15, 15, 10,  0,-30,
   -30,  5, 15, 20, 20, 15,  5,-30,
   -30,  0, 15, 20, 20, 15,  0,-30,
   -30,  5, 10, 15, 15, 10,  5,-30,
   -40,-20,  0,  5,  5,  0,-20,-40,
   -50,-40,-30,-30,-30,-30,-40,-50,
]

_BISHOP_VIS = [
   -20,-10,-10,-10,-10,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -10,  5,  5, 10, 10,  5,  5,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10, 10, 10, 10, 10, 10, 10,-10,
   -10,  5,  0,  0,  0,  0,  5,-10,
   -20,-10,-10,-10,-10,-10,-10,-20,
]

_ROOK_VIS = [
     0,  0,  0,  0,  0,  0,  0,  0,
     5, 10, 10, 10, 10, 10, 10,  5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
    -5,  0,  0,  0,  0,  0,  0, -5,
     0,  0,  0,  5,  5,  0,  0,  0,
]

_QUEEN_VIS = [
   -20,-10,-10, -5, -5,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0,  5,  5,  5,  5,  0,-10,
    -5,  0,  5,  5,  5,  5,  0, -5,
     0,  0,  5,  5,  5,  5,  0, -5,
   -10,  5,  5,  5,  5,  5,  0,-10,
   -10,  0,  5,  0,  0,  0,  0,-10,
   -20,-10,-10, -5, -5,-10,-10,-20,
]

_KING_MG_VIS = [
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -20,-30,-30,-40,-40,-30,-30,-20,
   -10,-20,-20,-20,-20,-20,-20,-10,
    20, 20,  0,  0,  0,  0, 20, 20,
    20, 30, 10,  0,  0, 10, 30, 20,
]

_KING_EG_VIS = [
   -50,-40,-30,-20,-20,-30,-40,-50,
   -30,-20,-10,  0,  0,-10,-20,-30,
   -30,-10, 20, 30, 30, 20,-10,-30,
   -30,-10, 30, 40, 40, 30,-10,-30,
   -30,-10, 30, 40, 40, 30,-10,-30,
   -30,-10, 20, 30, 30, 20,-10,-30,
   -30,-30,  0,  0,  0,  0,-30,-30,
   -50,-30,-30,-30,-30,-30,-50,-50,
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
                for sq in pieces[color][pt]:
                    s += sign * table[sq ^ flip]
            for sq in pieces[color][chess.PAWN]:
                i = sq ^ flip
                s += sign * (phase * PAWN_MG[i] + (1 - phase) * PAWN_EG[i])
            ksq = ctx.king_sq[color]
            if ksq is not None:
                i = ksq ^ flip
                s += sign * (phase * KING_MG[i] + (1 - phase) * KING_EG[i])
        return s

    def details(self, ctx):
        phase = ctx.phase
        items = []
        board = ctx.board
        for sq, piece in sorted(ctx.piece_map.items()):
            color, pt = piece.color, piece.piece_type
            sign = 1 if color == chess.WHITE else -1
            i = sq if color == chess.WHITE else sq ^ 56
            if pt == chess.PAWN:
                v = phase * PAWN_MG[i] + (1 - phase) * PAWN_EG[i]
            elif pt == chess.KING:
                v = phase * KING_MG[i] + (1 - phase) * KING_EG[i]
            else:
                v = _FLAT[pt][i]
            if v:
                label = f"{'White' if color else 'Black'} {chess.piece_name(pt)} on {chess.square_name(sq)}"
                items.append((label, sign * v))
        return items

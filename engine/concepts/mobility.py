"""Mobility: how many squares each piece can reach.

Counts attacked squares not occupied by friendly pieces and not controlled
by enemy pawns (safe mobility), weighted per piece
type, centered on a typical count so the concept reads as a bonus for active
pieces and a penalty for cramped ones.
"""

import chess

from engine.weights import W

# piece type -> (weight key, typical square count)
MOBILITY_PARAMS = {
    chess.KNIGHT: ("mob.knight", 4),
    chess.BISHOP: ("mob.bishop", 6),
    chess.ROOK: ("mob.rook", 7),
    chess.QUEEN: ("mob.queen", 13),
}


class Mobility:
    name = "mobility"
    display_name = "Mobility"

    @staticmethod
    def _pawn_attacks(board, color):
        pawns = board.pawns & board.occupied_co[color]
        if color == chess.WHITE:
            return ((pawns << 7) & ~chess.BB_FILE_H) | ((pawns << 9) & ~chess.BB_FILE_A)
        return ((pawns >> 7) & ~chess.BB_FILE_A) | ((pawns >> 9) & ~chess.BB_FILE_H)

    def score(self, ctx):
        s = 0
        board = ctx.board
        occ = ctx.occupied_co
        attacks = ctx.attacks
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            own = occ[color]
            unsafe = self._pawn_attacks(board, not color)
            for pt, (key, typical) in MOBILITY_PARAMS.items():
                w = W[key]
                for sq in ctx.pieces[color][pt]:
                    n = chess.popcount(attacks[sq] & ~own & ~unsafe)
                    s += sign * w * (n - typical)
        return s

    def details(self, ctx):
        items = []
        board = ctx.board
        occ = ctx.occupied_co
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = occ[color]
            unsafe = self._pawn_attacks(board, not color)
            for pt, (key, typical) in MOBILITY_PARAMS.items():
                w = W[key]
                for sq in ctx.pieces[color][pt]:
                    n = chess.popcount(ctx.attacks[sq] & ~own & ~unsafe)
                    v = sign * w * (n - typical)
                    if v:
                        label = (f"{cname} {chess.piece_name(pt)} on "
                                 f"{chess.square_name(sq)} ({n} squares)")
                        items.append((label, v))
        return items

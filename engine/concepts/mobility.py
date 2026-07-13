"""Mobility: how many squares each piece can reach.

Counts attacked squares not occupied by friendly pieces, weighted per piece
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

    def score(self, ctx):
        s = 0
        board = ctx.board
        occ = ctx.occupied_co
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            own = occ[color]
            for pt, (key, typical) in MOBILITY_PARAMS.items():
                w = W[key]
                for sq in ctx.pieces[color][pt]:
                    n = chess.popcount(board.attacks_mask(sq) & ~own)
                    s += sign * w * (n - typical)
        return s

    def details(self, ctx):
        items = []
        board = ctx.board
        occ = ctx.occupied_co
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = occ[color]
            for pt, (key, typical) in MOBILITY_PARAMS.items():
                w = W[key]
                for sq in ctx.pieces[color][pt]:
                    n = chess.popcount(board.attacks_mask(sq) & ~own)
                    v = sign * w * (n - typical)
                    if v:
                        label = (f"{cname} {chess.piece_name(pt)} on "
                                 f"{chess.square_name(sq)} ({n} squares)")
                        items.append((label, v))
        return items

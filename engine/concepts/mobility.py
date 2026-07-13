"""Mobility: how many squares each piece can reach.

Counts attacked squares not occupied by friendly pieces, weighted per piece
type, centered on a typical count so the concept reads as a bonus for active
pieces and a penalty for cramped ones.
"""

import chess

# (weight cp per square, typical square count) per piece type
MOBILITY_PARAMS = {
    chess.KNIGHT: (4, 4),
    chess.BISHOP: (3, 6),
    chess.ROOK: (2, 7),
    chess.QUEEN: (1, 13),
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
            for pt, (w, typical) in MOBILITY_PARAMS.items():
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
            for pt, (w, typical) in MOBILITY_PARAMS.items():
                for sq in ctx.pieces[color][pt]:
                    n = chess.popcount(board.attacks_mask(sq) & ~own)
                    v = sign * w * (n - typical)
                    if v:
                        label = (f"{cname} {chess.piece_name(pt)} on "
                                 f"{chess.square_name(sq)} ({n} squares)")
                        items.append((label, v))
        return items

"""Mobility: how many squares each piece can reach.

Counts attacked squares not occupied by friendly pieces and not controlled
by enemy pawns (safe mobility), weighted per piece
type, centered on a typical count so the concept reads as a bonus for active
pieces and a penalty for cramped ones.
"""

import chess

from engine.weights import W, wt

# piece type -> (weight key, typical square count)
MOBILITY_PARAMS = {
    chess.KNIGHT: ("mob.knight", 4),
    chess.BISHOP: ("mob.bishop", 6),
    chess.ROOK: ("mob.rook", 7),
    chess.QUEEN: ("mob.queen", 13),
}


_NAME = {chess.KNIGHT: "knight", chess.BISHOP: "bishop",
         chess.ROOK: "rook", chess.QUEEN: "queen"}
_MAXN = {chess.KNIGHT: 8, chess.BISHOP: 13, chess.ROOK: 14, chess.QUEEN: 27}


def _curve(pt, n, phase):
    """Score for `n` safe squares, from the fitted per-count table.

    A linear weight cannot express the real shape of mobility -- the 4th square
    a knight gains is worth more than its 8th -- so each count carries its own
    value, as Stockfish's Mobility[piece][count] does. Counts above the table
    clamp to the top entry; a queen with 28 safe squares is not a distinct
    concept from one with 27.
    """
    if n > _MAXN[pt]:
        n = _MAXN[pt]
    return wt(f"mob.{_NAME[pt]}.{n}", phase)


class Mobility:
    name = "mobility"
    display_name = "Mobility"

    def score(self, ctx):
        s = 0
        occ = ctx.occupied_co
        attacks = ctx.attacks
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            own = occ[color]
            unsafe = ctx.pawn_attacks[not color]
            for pt, (key, typical) in MOBILITY_PARAMS.items():
                w = wt(key, ctx.phase)
                for sq in ctx.pieces[color][pt]:
                    n = chess.popcount(attacks[sq] & ~own & ~unsafe)
                    s += sign * _curve(pt, n, ctx.phase)
        return s

    def details(self, ctx):
        items = []
        occ = ctx.occupied_co
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = occ[color]
            unsafe = ctx.pawn_attacks[not color]
            for pt, (key, typical) in MOBILITY_PARAMS.items():
                w = wt(key, ctx.phase)
                for sq in ctx.pieces[color][pt]:
                    n = chess.popcount(ctx.attacks[sq] & ~own & ~unsafe)
                    v = sign * _curve(pt, n, ctx.phase)
                    if v:
                        label = (f"{cname} {chess.piece_name(pt)} on "
                                 f"{chess.square_name(sq)} ({n} squares)")
                        items.append((label, v))
        return items

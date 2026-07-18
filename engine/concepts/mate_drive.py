"""Mating drive: technique for winning 'bare king' endgames.

When one side is down to a lone king and the other has enough to force mate,
raw material already decides the game — but the winning side still has to
*drive the enemy king to the edge/corner* and *bring its own king up* to
deliver mate. Plain material + PSTs give no gradient for that, so the engine
shuffles until the 50-move rule (it failed to mate K+2B in the diagnostic).

This concept adds that gradient, and only in those positions, so it never
touches normal middlegames. Interpretable: it reports "driving the black king
toward the corner" with the two components.
"""

import chess

from engine.weights import W

# Center-manhattan distance: 0 at the four central squares, 6 at the corners.
# Larger = enemy king more cornered = better for the mating side.
_CMD = []
for sq in chess.SQUARES:
    f, r = chess.square_file(sq), chess.square_rank(sq)
    _CMD.append(max(3 - f, f - 4) + max(3 - r, r - 4))


def _has_mating_material(ctx, color):
    """Enough to force mate against a lone king: a queen/rook, or two minors."""
    p = ctx.pieces[color]
    if p[chess.QUEEN] or p[chess.ROOK]:
        return True
    return len(p[chess.KNIGHT]) + len(p[chess.BISHOP]) >= 2


def _bare_king(ctx, color):
    p = ctx.pieces[color]
    return not (p[chess.PAWN] or p[chess.KNIGHT] or p[chess.BISHOP]
                or p[chess.ROOK] or p[chess.QUEEN])


_PIECE_CP = {chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500,
             chess.QUEEN: 900}


def _mopup_target(ctx, loser):
    """Pawnless defender that the winner dominates by at least a rook:
    the mop-up case (KR vs KB, KQ vs KN, ...). The drive gradient applies
    at half strength — the defender's piece can delay but not save it."""
    p = ctx.pieces[loser]
    if p[chess.PAWN]:
        return False
    lmat = sum(_PIECE_CP[t] * len(p[t]) for t in _PIECE_CP)
    if lmat == 0:
        return False        # bare king: the full-strength branch handles it
    w = ctx.pieces[not loser]
    wmat = sum(_PIECE_CP[t] * len(w[t]) for t in _PIECE_CP)
    return wmat - lmat >= 500


class MateDrive:
    name = "mate_drive"
    display_name = "Mating drive"

    def _components(self, ctx):
        """Return (sign, winner_name, corner_cp, kingprox_cp) or None."""
        for winner, loser, sign, wname in (
                (chess.WHITE, chess.BLACK, 1, "White"),
                (chess.BLACK, chess.WHITE, -1, "Black")):
            full = _bare_king(ctx, loser) and _has_mating_material(ctx, winner)
            mopup = (not full) and _mopup_target(ctx, loser)
            if full or mopup:
                lk = ctx.king_sq[loser]
                wk = ctx.king_sq[winner]
                if lk is None or wk is None:
                    return None
                scale = 1.0 if full else 0.5
                md = (abs(chess.square_file(lk) - chess.square_file(wk))
                      + abs(chess.square_rank(lk) - chess.square_rank(wk)))
                corner = W["mate_drive.corner"] * _CMD[lk] * scale
                kingprox = W["mate_drive.king_prox"] * (14 - md) * scale
                return sign, wname, sign * corner, sign * kingprox
        return None

    def score(self, ctx):
        c = self._components(ctx)
        return 0.0 if c is None else c[2] + c[3]

    def details(self, ctx):
        c = self._components(ctx)
        if c is None:
            return []
        sign, wname, corner, kingprox = c
        loser = "black" if sign > 0 else "white"
        return [
            (f"{wname} driving the {loser} king toward the corner", corner),
            (f"{wname} king approaching for mate", kingprox),
        ]

"""Threats: enemy pieces we bear down on.

Two kinds, both interpretable:
  - a piece attacked by a *lower-value* attacker (a pawn hitting a minor/rook/
    queen, a minor hitting a rook/queen, a rook hitting a queen) — it must move
    or drop material, so it's real pressure even when defended;
  - a piece attacked and *undefended* (en prise / hanging).

Scored as a fraction of the threatened piece's value. Terms are added per piece
in a fixed order (pawn, minor, rook, hanging) so the compiled C eval mirrors
this sum byte-for-byte.
"""

import chess

from engine.weights import W, W_EG, wt

_VALUE = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
          chess.ROOK: 500, chess.QUEEN: 900}


def _pawn_attacks(pawns, color):
    if color == chess.WHITE:
        return ((pawns << 7) & ~chess.BB_FILE_H) | ((pawns << 9) & ~chess.BB_FILE_A)
    return ((pawns >> 7) & ~chess.BB_FILE_A) | ((pawns >> 9) & ~chess.BB_FILE_H)



# Threat value by (kind, victim), rather than weight * victim value. The old
# form forced a threat on a queen to be worth exactly nine times a threat on a
# pawn; these rows can say otherwise. Seeded to the old products so introducing
# them changed nothing, then fitted on decisive-game loss.
_KINDS = ("pawn", "minor", "rook", "hanging")
_VICTIMS = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)


# Fitted on decisive-game loss, replacing `weight * VALUE[victim]`. The old form
# forced a threat on a queen to be worth nine times one on a pawn; these numbers
# say otherwise, most sharply for hanging pieces -- a hanging bishop outweighs a
# hanging knight, and hanging rooks and queens are worth less than material
# would suggest, big pieces usually being defended.
_ORDER = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
_TAB_MG = [
    [15.53, 49.62, 54.67, 90.80, 90.80],   # pawn
    [2.72, 8.70, 8.98, 39.39, 41.32],   # minor
    [7.53, 24.10, 24.85, 37.65, 78.63],   # rook
    [8.04, 33.56, 37.53, 37.53, 37.53],   # hanging
]
_TAB_EG = [
    [3.46, 9.04, 9.04, 32.02, 96.96],   # pawn
    [9.59, 24.77, 24.77, 24.77, 119.40],   # minor
    [1.44, 4.61, 4.75, 7.20, 90.78],   # rook
    [11.35, 28.01, 31.49, 55.84, 123.98],   # hanging
]
THREAT_MG = {k: dict(zip(_ORDER, _TAB_MG[i])) for i, k in enumerate(_KINDS)}
THREAT_EG = {k: dict(zip(_ORDER, _TAB_EG[i])) for i, k in enumerate(_KINDS)}


def _threat(kind, victim, phase):
    mg = THREAT_MG[kind][victim]
    eg = THREAT_EG[kind][victim]
    return mg if mg == eg else phase * mg + (1.0 - phase) * eg


class Threats:
    name = "threats"
    display_name = "Threats"

    def score(self, ctx):
        return sum(v for _, v in self._items(ctx, labels=False))

    def details(self, ctx):
        return self._items(ctx, labels=True)

    def _items(self, ctx, labels):
        items = []
        w_pawn = wt("threat.pawn", ctx.phase)
        w_minor = wt("threat.minor", ctx.phase)
        w_rook = wt("threat.rook", ctx.phase)
        w_hang = wt("threat.hanging", ctx.phase)
        init = wt("threat.initiative", ctx.phase)
        board = ctx.board
        attacked_by = ctx.attacked_by
        for color, sign, cname in ((chess.WHITE, 1, "Black"), (chess.BLACK, -1, "White")):
            # color = the attacker; iterate the enemy's pieces. The side to move
            # can execute its threats immediately, so scale them up.
            enemy = not color
            w = 1.0 + init if color == board.turn else 1.0
            pawns = board.pawns & ctx.occupied_co[color]
            pawn_atk = _pawn_attacks(pawns, color)
            minor_atk = 0
            for pt in (chess.KNIGHT, chess.BISHOP):
                for sq in ctx.pieces[color][pt]:
                    minor_atk |= ctx.attacks[sq]
            rook_atk = 0
            for sq in ctx.pieces[color][chess.ROOK]:
                rook_atk |= ctx.attacks[sq]
            atk, dfd = attacked_by[color], attacked_by[enemy]
            for pt in (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                val = _VALUE[pt]
                pname = chess.piece_name(pt)
                for sq in ctx.pieces[enemy][pt]:
                    m = 1 << sq
                    sqn = chess.square_name(sq)
                    if (pawn_atk & m) and pt >= chess.KNIGHT:
                        items.append(
                            (f"{cname} {pname} on {sqn} attacked by a pawn" if labels else None,
                             sign * w * _threat("pawn", pt, ctx.phase)))
                    if (minor_atk & m) and pt >= chess.ROOK:
                        items.append(
                            (f"{cname} {pname} on {sqn} attacked by a minor" if labels else None,
                             sign * w * _threat("minor", pt, ctx.phase)))
                    if (rook_atk & m) and pt == chess.QUEEN:
                        items.append(
                            (f"{cname} queen on {sqn} attacked by a rook" if labels else None,
                             sign * w * _threat("rook", pt, ctx.phase)))
                    if (atk & m) and not (dfd & m):
                        items.append(
                            (f"{cname} {pname} on {sqn} is hanging" if labels else None,
                             sign * w * _threat("hanging", pt, ctx.phase)))
        return items

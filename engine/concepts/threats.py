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

from engine.weights import W

_VALUE = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
          chess.ROOK: 500, chess.QUEEN: 900}


def _pawn_attacks(pawns, color):
    if color == chess.WHITE:
        return ((pawns << 7) & ~chess.BB_FILE_H) | ((pawns << 9) & ~chess.BB_FILE_A)
    return ((pawns >> 7) & ~chess.BB_FILE_A) | ((pawns >> 9) & ~chess.BB_FILE_H)


class Threats:
    name = "threats"
    display_name = "Threats"

    def score(self, ctx):
        return sum(v for _, v in self._items(ctx, labels=False))

    def details(self, ctx):
        return self._items(ctx, labels=True)

    def _items(self, ctx, labels):
        items = []
        w_pawn, w_minor = W["threat.pawn"], W["threat.minor"]
        w_rook, w_hang = W["threat.rook"], W["threat.hanging"]
        board = ctx.board
        attacked_by = ctx.attacked_by
        for color, sign, cname in ((chess.WHITE, 1, "Black"), (chess.BLACK, -1, "White")):
            # color = the attacker; iterate the enemy's pieces.
            enemy = not color
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
                             sign * w_pawn * val))
                    if (minor_atk & m) and pt >= chess.ROOK:
                        items.append(
                            (f"{cname} {pname} on {sqn} attacked by a minor" if labels else None,
                             sign * w_minor * val))
                    if (rook_atk & m) and pt == chess.QUEEN:
                        items.append(
                            (f"{cname} queen on {sqn} attacked by a rook" if labels else None,
                             sign * w_rook * val))
                    if (atk & m) and not (dfd & m):
                        items.append(
                            (f"{cname} {pname} on {sqn} is hanging" if labels else None,
                             sign * w_hang * val))
        return items

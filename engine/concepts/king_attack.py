"""King attack: piece pressure on the zone around the enemy king.

Counts attacked squares in the 3x3 king zone, weighted by attacker type,
and only when at least two pieces join the attack (one piece rarely mates).
Scaled by phase — attacks need material on the board.
"""

import chess

from engine.weights import W

_UNIT = {chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 5}


class KingAttack:
    name = "king_attack"
    display_name = "King attack"

    def score(self, ctx):
        return sum(v for _, v in self._items(ctx, labels=False))

    def details(self, ctx):
        return self._items(ctx, labels=True)

    def _items(self, ctx, labels):
        items = []
        phase = ctx.phase
        if phase < 0.05:
            return items
        board = ctx.board
        scale = W["kattack.scale"]
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            ksq = ctx.king_sq[not color]
            if ksq is None:
                continue
            zone = chess.BB_KING_ATTACKS[ksq] | (1 << ksq)
            units = 0
            attackers = 0
            for pt, w in _UNIT.items():
                for sq in ctx.pieces[color][pt]:
                    hits = chess.popcount(ctx.attacks[sq] & zone)
                    if hits:
                        units += w * hits
                        attackers += 1
            if attackers >= 2:
                v = sign * scale * units * units / 10 * phase
                if labels:
                    items.append((f"{cname} attack on enemy king "
                                  f"({attackers} attackers, {units} units)", v))
                else:
                    items.append((None, v))
            # proximity gradient: pieces closing in on the king matter before
            # they attack the zone (smooth, like the s12 passer king race —
            # gradients give the search direction where discrete rules don't)
            prox = 0
            for pt, w in _UNIT.items():
                for sq in ctx.pieces[color][pt]:
                    d = chess.square_distance(sq, ksq)
                    if d < 4:
                        prox += w * (4 - d)
            if prox:
                pv = sign * W["kattack.proximity"] * prox * phase
                if labels:
                    items.append((f"{cname} pieces near the enemy king "
                                  f"({prox} closeness units)", pv))
                else:
                    items.append((None, pv))
        return items

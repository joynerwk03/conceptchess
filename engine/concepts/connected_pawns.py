"""Connected pawns: mutually-supporting pawns, worth more as they advance.

A pawn is *connected* when a friendly pawn stands beside it (a phalanx, same rank
on an adjacent file) or defends it (an adjacent-file pawn one rank behind).
Connected pawns are hard to attack and, when advanced, cramp the enemy and cover
key squares — a structural *strength* that mirrors the doubled/isolated/backward
*weaknesses* but which nothing here rewarded. The bonus is scaled by how far the
pawn has advanced (only from the 4th rank up), so the starting pawn chain earns
nothing and an advanced duo earns real credit.

Summed per pawn in a fixed order so the compiled C eval mirrors it byte-for-byte.
"""

import chess

from engine.weights import W


class ConnectedPawns:
    name = "connected"
    display_name = "Connected pawns"

    def score(self, ctx):
        return sum(v for _, v in self._items(ctx, labels=False))

    def details(self, ctx):
        return self._items(ctx, labels=True)

    def _items(self, ctx, labels):
        items = []
        w = W["pawn.connected"]
        board = ctx.board
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = board.pawns & ctx.occupied_co[color]
            for sq in ctx.pieces[color][chess.PAWN]:
                f, r = chess.square_file(sq), chess.square_rank(sq)
                rel = r if color == chess.WHITE else 7 - r     # 0..7, how advanced
                adv = rel - 2
                if adv <= 0:
                    continue                                    # only 4th rank and up
                back = r - 1 if color == chess.WHITE else r + 1
                phalanx = supported = False
                for af in (f - 1, f + 1):
                    if af < 0 or af > 7:
                        continue
                    if own & (1 << chess.square(af, r)):
                        phalanx = True
                    if 0 <= back <= 7 and (own & (1 << chess.square(af, back))):
                        supported = True
                if phalanx or supported:
                    v = sign * w * adv
                    items.append((f"{cname} connected pawn on {chess.square_name(sq)}"
                                  if labels else None, v))
        return items

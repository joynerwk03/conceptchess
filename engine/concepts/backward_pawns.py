"""Backward pawns: a pawn left behind its neighbours that can't advance.

A pawn is *backward* when its own pawns on adjacent files have all advanced past
it (so they can never defend it) AND the square in front of it is covered by an
enemy pawn (so it can't safely advance to catch up). Such a pawn is a permanent,
long-horizon weakness — it's a chronic target, especially on a half-open file
where enemy rooks can pile on it. That "chronic weakness over many moves" is
exactly what a fixed-depth search struggles to see, and it isn't captured by the
existing doubled/isolated terms (a backward pawn has neighbours; it's just been
left behind).

Summed per pawn in a fixed order so the compiled C eval mirrors it byte-for-byte.
"""

import chess

from engine.weights import W


def _pawn_attacks(pawns, color):
    if color == chess.WHITE:
        return ((pawns << 7) & ~chess.BB_FILE_H) | ((pawns << 9) & ~chess.BB_FILE_A)
    return ((pawns >> 7) & ~chess.BB_FILE_A) | ((pawns >> 9) & ~chess.BB_FILE_H)


class BackwardPawns:
    name = "backward"
    display_name = "Backward pawns"

    def score(self, ctx):
        return sum(v for _, v in self._items(ctx, labels=False))

    def details(self, ctx):
        return self._items(ctx, labels=True)

    def _items(self, ctx, labels):
        items = []
        w = W["pawn.backward"]
        board = ctx.board
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = board.pawns & ctx.occupied_co[color]
            enemy = board.pawns & ctx.occupied_co[not color]
            enemy_atk = _pawn_attacks(enemy, not color)
            for sq in ctx.pieces[color][chess.PAWN]:
                f, r = chess.square_file(sq), chess.square_rank(sq)
                adj = 0
                if f > 0:
                    adj |= chess.BB_FILES[f - 1]
                if f < 7:
                    adj |= chess.BB_FILES[f + 1]
                own_adj = own & adj
                if not own_adj:
                    continue                                   # isolated, not backward
                if color == chess.WHITE:
                    support = adj & ((1 << ((r + 1) * 8)) - 1)  # adj squares on ranks <= r
                    stop = sq + 8
                else:
                    support = adj & ~((1 << (r * 8)) - 1)       # adj squares on ranks >= r
                    stop = sq - 8
                if own_adj & support:
                    continue                                   # a neighbour is level/behind
                if stop < 0 or stop > 63:
                    continue
                if not (enemy_atk & (1 << stop)):
                    continue                                   # can advance safely
                half_open = not (enemy & chess.BB_FILES[f])
                mult = 2 if half_open else 1
                v = -sign * w * mult
                items.append(
                    (f"{cname} backward pawn on {chess.square_name(sq)}"
                     f"{' (half-open file)' if half_open else ''}" if labels else None, v))
        return items

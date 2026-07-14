"""Threats: pieces attacked and not defended (en prise)."""

import chess

from engine.weights import W

_VALUE = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
          chess.ROOK: 500, chess.QUEEN: 900}


class Threats:
    name = "threats"
    display_name = "Threats"

    def score(self, ctx):
        return sum(v for _, v in self._items(ctx, labels=False))

    def details(self, ctx):
        return self._items(ctx, labels=True)

    def _items(self, ctx, labels):
        items = []
        frac = W["threat.hanging"]
        attacked_by = ctx.attacked_by
        for color, sign, cname in ((chess.WHITE, 1, "Black"), (chess.BLACK, -1, "White")):
            # color = attacker; iterate the *enemy*'s pieces
            enemy = not color
            atk, dfd = attacked_by[color], attacked_by[enemy]
            for pt, sqs in ctx.pieces[enemy].items():
                if pt == chess.KING:
                    continue
                for sq in sqs:
                    if (atk >> sq) & 1 and not (dfd >> sq) & 1:
                        v = sign * frac * _VALUE[pt]
                        if labels:
                            items.append(
                                (f"{cname} {chess.piece_name(pt)} on "
                                 f"{chess.square_name(sq)} is hanging", v))
                        else:
                            items.append((None, v))
        return items

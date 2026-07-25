"""Opposite-colored-bishop drawishness — a MULTIPLICATIVE eval modifier.

Pure opposite-colored-bishop endings (one bishop each, on opposite colors, and
no other pieces) are famously drawish: an extra pawn or even two often fails to
win, because the defending bishop controls squares the attacker's bishop can
never contest. So the whole evaluation is scaled toward zero here.

This is fundamentally multiplicative — it re-weights the *entire* positional
verdict — so it can't be a normal additive concept. Interpretability is kept the
way William proposed: the breakdown shows the modifier's marginal effect,
``(factor - 1) x running_eval`` — the exact number of centipawns it moved the
score by. Those deltas still sum into the total, so the explanation remains
faithful to the number search uses.

A modifier exposes ``factor(ctx)`` (multiplicative, 1.0 = no effect) and
``item_label(ctx)`` instead of a concept's ``score``/``details``.
"""

import chess

from engine.weights import W


class OppositeBishops:
    name = "ocb"
    display_name = "Opposite bishops"

    def _is_pure_ocb(self, ctx):
        wp = ctx.pieces[chess.WHITE]
        bp = ctx.pieces[chess.BLACK]
        if len(wp[chess.BISHOP]) != 1 or len(bp[chess.BISHOP]) != 1:
            return False
        # only bishops, pawns and kings on the board
        for pt in (chess.KNIGHT, chess.ROOK, chess.QUEEN):
            if wp[pt] or bp[pt]:
                return False
        w_light = bool(chess.BB_LIGHT_SQUARES & chess.BB_SQUARES[wp[chess.BISHOP][0]])
        b_light = bool(chess.BB_LIGHT_SQUARES & chess.BB_SQUARES[bp[chess.BISHOP][0]])
        return w_light != b_light   # opposite colors

    def factor(self, ctx):
        return W["ocb.draw_scale"] if self._is_pure_ocb(ctx) else 1.0

    def item_label(self, ctx):
        return "opposite-colored bishops (drawish)"

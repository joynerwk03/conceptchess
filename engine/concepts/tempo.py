"""Tempo: small bonus for the side to move."""

import chess

from engine.weights import W, wt


class Tempo:
    name = "tempo"
    display_name = "Tempo"

    def score(self, ctx):
        return (wt("tempo", ctx.phase) if ctx.board.turn == chess.WHITE else -wt("tempo", ctx.phase))

    def details(self, ctx):
        side = "White" if ctx.board.turn == chess.WHITE else "Black"
        return [(f"{side} to move", self.score(ctx))]

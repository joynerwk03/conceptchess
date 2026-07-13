"""Tempo: small bonus for the side to move."""

import chess

from engine.weights import W


class Tempo:
    name = "tempo"
    display_name = "Tempo"

    def score(self, ctx):
        return W["tempo"] if ctx.board.turn == chess.WHITE else -W["tempo"]

    def details(self, ctx):
        side = "White" if ctx.board.turn == chess.WHITE else "Black"
        return [(f"{side} to move", self.score(ctx))]

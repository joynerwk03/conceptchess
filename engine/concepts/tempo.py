"""Tempo: small bonus for the side to move."""

import chess

TEMPO_BONUS = 10


class Tempo:
    name = "tempo"
    display_name = "Tempo"

    def score(self, ctx):
        return TEMPO_BONUS if ctx.board.turn == chess.WHITE else -TEMPO_BONUS

    def details(self, ctx):
        side = "White" if ctx.board.turn == chess.WHITE else "Black"
        return [(f"{side} to move", self.score(ctx))]

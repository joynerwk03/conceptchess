"""Pawn structure: doubled, isolated, and passed pawns."""

import chess

DOUBLED_PENALTY = 15       # per extra pawn on a file
ISOLATED_PENALTY = 12      # per isolated pawn
# Passed pawn bonus by rank (from the pawn's own side; rank index 0-7).
PASSED_BONUS = [0, 10, 15, 20, 35, 60, 100, 0]
PASSED_EG_SCALE = 1.5      # passed pawns matter more in the endgame


class PawnStructure:
    name = "pawn_structure"
    display_name = "Pawn structure"

    def score(self, ctx):
        return sum(v for _, v in self.details(ctx))

    def details(self, ctx):
        items = []
        phase = ctx.phase
        passed_scale = phase + (1 - phase) * PASSED_EG_SCALE
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            for f in range(8):
                ranks = own[f]
                if not ranks:
                    continue
                if len(ranks) > 1:
                    items.append((f"{cname} doubled pawns on {chr(97 + f)}-file",
                                  -sign * DOUBLED_PENALTY * (len(ranks) - 1)))
                neighbors = (own[f - 1] if f > 0 else []) + (own[f + 1] if f < 7 else [])
                if not neighbors:
                    items.append((f"{cname} isolated pawn(s) on {chr(97 + f)}-file",
                                  -sign * ISOLATED_PENALTY * len(ranks)))
                for r in ranks:
                    if self._is_passed(color, f, r, enemy):
                        rel_rank = r if color == chess.WHITE else 7 - r
                        sq = chess.square_name(chess.square(f, r))
                        items.append((f"{cname} passed pawn on {sq}",
                                      sign * PASSED_BONUS[rel_rank] * passed_scale))
        return items

    @staticmethod
    def _is_passed(color, file, rank, enemy_files):
        for f in (file - 1, file, file + 1):
            if 0 <= f <= 7:
                for er in enemy_files[f]:
                    if (color == chess.WHITE and er > rank) or (color == chess.BLACK and er < rank):
                        return False
        return True

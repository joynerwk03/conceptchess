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

    def __init__(self):
        # (white_pawn_bb, black_pawn_bb) -> (base_score, raw_passed_bonus).
        # Pawn structure only changes on pawn moves/captures, so this hits
        # nearly always. Phase scaling is applied outside the cache.
        self._cache = {}

    def score(self, ctx):
        board = ctx.board
        key = (board.pawns & ctx.occupied_co[1], board.pawns & ctx.occupied_co[0])
        cached = self._cache.get(key)
        if cached is None:
            cached = self._compute(ctx)
            if len(self._cache) > 200_000:
                self._cache.clear()
            self._cache[key] = cached
        base, passed_raw = cached
        phase = ctx.phase
        return base + passed_raw * (phase + (1 - phase) * PASSED_EG_SCALE)

    def _compute(self, ctx):
        """Same arithmetic as details(), split into phase-free parts."""
        base = 0.0
        passed_raw = 0.0
        is_passed = self._is_passed
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            for f in range(8):
                ranks = own[f]
                if not ranks:
                    continue
                n = len(ranks)
                if n > 1:
                    base -= sign * DOUBLED_PENALTY * (n - 1)
                if not ((f > 0 and own[f - 1]) or (f < 7 and own[f + 1])):
                    base -= sign * ISOLATED_PENALTY * n
                for r in ranks:
                    if is_passed(color, f, r, enemy):
                        rel_rank = r if color == chess.WHITE else 7 - r
                        passed_raw += sign * PASSED_BONUS[rel_rank]
        return base, passed_raw

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

"""Pawn structure: doubled, isolated, and passed pawns."""

import chess

from engine.weights import W

# Passed pawn base bonus by rank (from the pawn's own side; rank index 0-7),
# scaled by W["pawn.passed_scale"].
PASSED_BONUS = [0, 10, 15, 20, 35, 60, 100, 0]


class PawnStructure:
    name = "pawn_structure"
    display_name = "Pawn structure"

    def __init__(self):
        # (white_pawn_bb, black_pawn_bb) -> (base_score, [(sign, sq, raw_bonus)]).
        # Pawn structure only changes on pawn moves/captures, so this hits
        # nearly always. Phase scaling and blockade checks (which depend on
        # piece occupancy, not just pawns) are applied outside the cache.
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
        base, passers = cached
        phase = ctx.phase
        scale = phase + (1 - phase) * W["pawn.passed_eg_scale"]
        occupied = ctx.board.occupied
        blocked_mult = W["pawn.blocked_passer"]
        s = base
        for sign, sq, raw in passers:
            front = sq + 8 if sign > 0 else sq - 8
            mult = blocked_mult if (0 <= front <= 63 and (occupied >> front) & 1) else 1.0
            s += raw * mult * scale
        return s

    def _compute(self, ctx):
        """Same arithmetic as details(), split into phase-free parts."""
        base = 0.0
        passers = []
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
                    base -= sign * W["pawn.doubled"] * (n - 1)
                if not ((f > 0 and own[f - 1]) or (f < 7 and own[f + 1])):
                    base -= sign * W["pawn.isolated"] * n
                for r in ranks:
                    if is_passed(color, f, r, enemy):
                        rel_rank = r if color == chess.WHITE else 7 - r
                        passers.append((sign, chess.square(f, r),
                                        sign * PASSED_BONUS[rel_rank] * W["pawn.passed_scale"]))
        return base, passers

    def details(self, ctx):
        items = []
        phase = ctx.phase
        passed_scale = phase + (1 - phase) * W["pawn.passed_eg_scale"]
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            for f in range(8):
                ranks = own[f]
                if not ranks:
                    continue
                if len(ranks) > 1:
                    items.append((f"{cname} doubled pawns on {chr(97 + f)}-file",
                                  -sign * W["pawn.doubled"] * (len(ranks) - 1)))
                neighbors = (own[f - 1] if f > 0 else []) + (own[f + 1] if f < 7 else [])
                if not neighbors:
                    items.append((f"{cname} isolated pawn(s) on {chr(97 + f)}-file",
                                  -sign * W["pawn.isolated"] * len(ranks)))
                for r in ranks:
                    if self._is_passed(color, f, r, enemy):
                        rel_rank = r if color == chess.WHITE else 7 - r
                        sq = chess.square(f, r)
                        front = sq + 8 if color == chess.WHITE else sq - 8
                        blocked = 0 <= front <= 63 and (ctx.board.occupied >> front) & 1
                        mult = W["pawn.blocked_passer"] if blocked else 1.0
                        tag = " (blockaded)" if blocked else ""
                        items.append((f"{cname} passed pawn on {chess.square_name(sq)}{tag}",
                                      sign * PASSED_BONUS[rel_rank] * mult
                                      * W["pawn.passed_scale"] * passed_scale))
        return items

    @staticmethod
    def _is_passed(color, file, rank, enemy_files):
        for f in (file - 1, file, file + 1):
            if 0 <= f <= 7:
                for er in enemy_files[f]:
                    if (color == chess.WHITE and er > rank) or (color == chess.BLACK and er < rank):
                        return False
        return True

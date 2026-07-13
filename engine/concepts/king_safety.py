"""King safety: pawn shield and open files near the king.

Scaled by game phase — an exposed king matters in the middlegame,
not in a pawn endgame.
"""

import chess

MISSING_SHIELD_PENALTY = 12   # per shield file with no friendly pawn nearby
OPEN_FILE_PENALTY = 15        # per fully open file adjacent to / on the king's file


class KingSafety:
    name = "king_safety"
    display_name = "King safety"

    def __init__(self):
        # (wp_bb, bp_bb, wk_sq, bk_sq) -> phase-free raw penalty.
        self._cache = {}

    def score(self, ctx):
        phase = ctx.phase
        if phase < 0.05:
            return 0.0
        board = ctx.board
        key = (board.pawns & ctx.occupied_co[1], board.pawns & ctx.occupied_co[0],
               ctx.king_sq[chess.WHITE], ctx.king_sq[chess.BLACK])
        raw = self._cache.get(key)
        if raw is None:
            raw = self._compute(ctx)
            if len(self._cache) > 200_000:
                self._cache.clear()
            self._cache[key] = raw
        return raw * phase

    def _compute(self, ctx):
        """Same arithmetic as details(), with the phase factor left out."""
        raw = 0.0
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            ksq = ctx.king_sq[color]
            if ksq is None:
                continue
            kf, kr = ksq & 7, ksq >> 3
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            missing = 0
            open_files = 0
            for f in (kf - 1, kf, kf + 1):
                if not 0 <= f <= 7:
                    continue
                if color == chess.WHITE:
                    shielded = any(kr < r <= kr + 2 for r in own[f])
                else:
                    shielded = any(kr - 2 <= r < kr for r in own[f])
                if not shielded:
                    missing += 1
                if not own[f] and not enemy[f]:
                    open_files += 1
            raw -= sign * (MISSING_SHIELD_PENALTY * missing + OPEN_FILE_PENALTY * open_files)
        return raw

    def details(self, ctx):
        items = []
        phase = ctx.phase
        if phase < 0.05:
            return items
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            ksq = ctx.king_sq[color]
            if ksq is None:
                continue
            kf, kr = chess.square_file(ksq), chess.square_rank(ksq)
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            missing = 0
            open_files = 0
            for f in (kf - 1, kf, kf + 1):
                if not 0 <= f <= 7:
                    continue
                # Shield: a friendly pawn within 2 ranks in front of the king.
                if color == chess.WHITE:
                    shielded = any(kr < r <= kr + 2 for r in own[f])
                else:
                    shielded = any(kr - 2 <= r < kr for r in own[f])
                if not shielded:
                    missing += 1
                if not own[f] and not enemy[f]:
                    open_files += 1
            if missing:
                items.append((f"{cname} king shield gaps ({missing})",
                              -sign * MISSING_SHIELD_PENALTY * missing * phase))
            if open_files:
                items.append((f"Open file(s) near {cname} king ({open_files})",
                              -sign * OPEN_FILE_PENALTY * open_files * phase))
        return items

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

    def score(self, ctx):
        return sum(v for _, v in self.details(ctx))

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

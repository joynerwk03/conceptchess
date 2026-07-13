"""Piece activity: bishop pair, rooks on open/semi-open files, rook on 7th."""

import chess

BISHOP_PAIR = 30
ROOK_OPEN_FILE = 20
ROOK_SEMI_OPEN = 10
ROOK_ON_SEVENTH = 20


class PieceActivity:
    name = "activity"
    display_name = "Piece activity"

    def score(self, ctx):
        return sum(v for _, v in self.details(ctx))

    def details(self, ctx):
        items = []
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            if len(ctx.pieces[color][chess.BISHOP]) >= 2:
                items.append((f"{cname} bishop pair", sign * BISHOP_PAIR))
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            seventh = 6 if color == chess.WHITE else 1
            for sq in ctx.pieces[color][chess.ROOK]:
                f = chess.square_file(sq)
                name = chess.square_name(sq)
                if not own[f] and not enemy[f]:
                    items.append((f"{cname} rook on open {chr(97 + f)}-file",
                                  sign * ROOK_OPEN_FILE))
                elif not own[f]:
                    items.append((f"{cname} rook on semi-open {chr(97 + f)}-file",
                                  sign * ROOK_SEMI_OPEN))
                if chess.square_rank(sq) == seventh:
                    items.append((f"{cname} rook on {name} (7th rank)",
                                  sign * ROOK_ON_SEVENTH))
        return items

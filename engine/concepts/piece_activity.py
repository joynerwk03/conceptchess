"""Piece activity: bishop pair, rooks on open/semi-open files, rook on 7th."""

import chess

from engine.weights import W, wt


class PieceActivity:
    name = "activity"
    display_name = "Piece activity"

    def score(self, ctx):
        # Same arithmetic as details(), without building labels (hot path).
        s = 0
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            if len(ctx.pieces[color][chess.BISHOP]) >= 2:
                s += sign * wt("act.bishop_pair", ctx.phase)
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            seventh = 6 if color == chess.WHITE else 1
            for sq in ctx.pieces[color][chess.ROOK]:
                f = sq & 7
                if not own[f]:
                    s += sign * (wt("act.rook_open", ctx.phase) if not enemy[f] else wt("act.rook_semi", ctx.phase))
                if sq >> 3 == seventh:
                    s += sign * wt("act.rook_seventh", ctx.phase)
        return s

    def details(self, ctx):
        items = []
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            if len(ctx.pieces[color][chess.BISHOP]) >= 2:
                items.append((f"{cname} bishop pair", sign * wt("act.bishop_pair", ctx.phase)))
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            seventh = 6 if color == chess.WHITE else 1
            for sq in ctx.pieces[color][chess.ROOK]:
                f = chess.square_file(sq)
                name = chess.square_name(sq)
                if not own[f] and not enemy[f]:
                    items.append((f"{cname} rook on open {chr(97 + f)}-file",
                                  sign * wt("act.rook_open", ctx.phase)))
                elif not own[f]:
                    items.append((f"{cname} rook on semi-open {chr(97 + f)}-file",
                                  sign * wt("act.rook_semi", ctx.phase)))
                if chess.square_rank(sq) == seventh:
                    items.append((f"{cname} rook on {name} (7th rank)",
                                  sign * wt("act.rook_seventh", ctx.phase)))
        return items

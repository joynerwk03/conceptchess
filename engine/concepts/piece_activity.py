"""Piece activity: bishop pair, bad bishops, rooks on open/semi-open files,
rook on 7th."""

import chess as _c
_LIGHT = _c.BB_LIGHT_SQUARES

import chess

from engine.weights import W


class PieceActivity:
    name = "activity"
    display_name = "Piece activity"

    def score(self, ctx):
        # Same arithmetic as details(), without building labels (hot path).
        s = 0
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            if len(ctx.pieces[color][chess.BISHOP]) >= 2:
                s += sign * W["act.bishop_pair"]
            pawns_bb = ctx.board.pawns & ctx.occupied_co[color]
            for sq in ctx.pieces[color][chess.BISHOP]:
                same = pawns_bb & (_LIGHT if (1 << sq) & _LIGHT else ~_LIGHT)
                excess = chess.popcount(same) - 2
                if excess > 0:
                    s -= sign * W["act.bad_bishop"] * excess
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            seventh = 6 if color == chess.WHITE else 1
            for sq in ctx.pieces[color][chess.ROOK]:
                f = sq & 7
                if not own[f]:
                    s += sign * (W["act.rook_open"] if not enemy[f] else W["act.rook_semi"])
                if sq >> 3 == seventh:
                    s += sign * W["act.rook_seventh"]
        return s

    def details(self, ctx):
        items = []
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            if len(ctx.pieces[color][chess.BISHOP]) >= 2:
                items.append((f"{cname} bishop pair", sign * W["act.bishop_pair"]))
            pawns_bb = ctx.board.pawns & ctx.occupied_co[color]
            for sq in ctx.pieces[color][chess.BISHOP]:
                same = pawns_bb & (_LIGHT if (1 << sq) & _LIGHT else ~_LIGHT)
                excess = chess.popcount(same) - 2
                if excess > 0:
                    items.append((f"{cname} bad bishop on {chess.square_name(sq)} "
                                  f"({excess + 2} own pawns on its color)",
                                  -sign * W["act.bad_bishop"] * excess))
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            seventh = 6 if color == chess.WHITE else 1
            for sq in ctx.pieces[color][chess.ROOK]:
                f = chess.square_file(sq)
                name = chess.square_name(sq)
                if not own[f] and not enemy[f]:
                    items.append((f"{cname} rook on open {chr(97 + f)}-file",
                                  sign * W["act.rook_open"]))
                elif not own[f]:
                    items.append((f"{cname} rook on semi-open {chr(97 + f)}-file",
                                  sign * W["act.rook_semi"]))
                if chess.square_rank(sq) == seventh:
                    items.append((f"{cname} rook on {name} (7th rank)",
                                  sign * W["act.rook_seventh"]))
        return items

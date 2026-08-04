"""Material imbalance and space — what the piece count alone does not say.

Phase 3 bundle D. Two ideas a plain material sum cannot express:

**Imbalance.** A knight and a rook are not worth fixed numbers. Kaufman's
result, which every strong classical engine encodes somehow: a knight gains
value as pawns stay on (it needs closed positions and safe squares) and a rook
loses value as pawns stay on (it needs open files). Two rooks are worth less
than twice one rook, and two knights less than twice one knight, because they
duplicate each other's work. All four of those are statements about the *mix*,
so they cannot live in `material.*`, which is a per-piece constant that SEE also
reads for exchange arithmetic.

**Space.** Safe squares behind your own pawns on the central files, in the
middlegame, worth more the more pieces you still have to put on them. It is the
one classical term that measures room to manoeuvre rather than any particular
piece's placement.

Deliberately Python-only for now: the loss screen (see the 2026-08-04 LOG entry)
needs only the Python eval, and a bundle earns its C mirror by being worth
>=0.3% outcome loss first. Porting a term that turns out to be worth 0.1% is how
bundle C cost an afternoon.
"""

import chess

from engine.weights import wt

CENTER_FILES = (chess.BB_FILE_C | chess.BB_FILE_D
                | chess.BB_FILE_E | chess.BB_FILE_F)
SPACE_MASK = {
    chess.WHITE: CENTER_FILES & (chess.BB_RANK_2 | chess.BB_RANK_3 | chess.BB_RANK_4),
    chess.BLACK: CENTER_FILES & (chess.BB_RANK_7 | chess.BB_RANK_6 | chess.BB_RANK_5),
}
FULL = (1 << 64) - 1


class Imbalance:
    name = "imbalance"
    display_name = "Imbalance & space"

    def _items(self, ctx):
        items = []
        board = ctx.board
        phase = ctx.phase
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = ctx.occupied_co[color]
            pawns = ctx.pieces[color][chess.PAWN]
            n_pawns = len(pawns)
            n_knights = len(ctx.pieces[color][chess.KNIGHT])
            n_rooks = len(ctx.pieces[color][chess.ROOK])

            # CONTROL TERM, and the reason it exists. `rook_pawns * (pawns - 5)`
            # has a constant component whenever the average pawn count in the
            # data is not five -- so a tuner with no other way to adjust the
            # rook's value (material.* is frozen, since SEE reads it) can drive
            # rook_pawns large simply because rooks are mispriced at a flat 500,
            # and it would look like it had discovered Kaufman. This flat term
            # gives it the honest way to say that instead. If rook_pawns stays
            # large with this available, the pawn-count interaction is real.
            if n_rooks:
                items.append((f"{cname} rook value adjustment",
                              sign * wt("imbalance.rook_flat", phase) * n_rooks))

            # A knight wants pawns on; a rook wants them off. Measured against
            # five, the count where the standard piece values were calibrated.
            if n_knights and n_pawns != 5:
                v = wt("imbalance.knight_pawns", phase) * n_knights * (n_pawns - 5)
                items.append((f"{cname} knights with {n_pawns} pawns", sign * v))
            if n_rooks and n_pawns != 5:
                v = -wt("imbalance.rook_pawns", phase) * n_rooks * (n_pawns - 5)
                items.append((f"{cname} rooks with {n_pawns} pawns", sign * v))

            # Redundancy: the second one of a pair duplicates the first's work.
            if n_rooks >= 2:
                items.append((f"{cname} rook pair (redundant)",
                              -sign * wt("imbalance.rook_pair", phase)))
            if n_knights >= 2:
                items.append((f"{cname} knight pair (redundant)",
                              -sign * wt("imbalance.knight_pair", phase)))

            # Space: safe central squares to manoeuvre into, worth more the more
            # pieces are still looking for somewhere to go.
            if phase > 0.4:
                own_pawns_bb = board.pawns & own
                unsafe = ctx.pawn_attacks[not color]
                safe = SPACE_MASK[color] & ~own_pawns_bb & ~unsafe
                behind = own_pawns_bb
                if color == chess.WHITE:
                    behind |= behind >> 8
                    behind |= behind >> 16
                else:
                    behind |= (behind << 8) & FULL
                    behind |= (behind << 16) & FULL
                bonus = (chess.popcount(safe)
                         + chess.popcount(behind & safe & ~ctx.attacked_by[not color]))
                pieces = chess.popcount(own)
                weight = max(0, pieces - 3)
                if bonus and weight:
                    v = wt("space.scale", phase) * bonus * weight * weight / 16.0
                    items.append((f"{cname} space ({bonus} safe central squares)",
                                  sign * v))
        return items

    def score(self, ctx):
        return sum(v for _, v in self._items(ctx))

    def details(self, ctx):
        return self._items(ctx)

"""Minor pieces: outposts, minors behind pawns, bad bishops, long diagonals.

Phase 3 bundle A of research/SCHEDULE.md — the per-piece placement judgements a
classical engine makes that a plain PST cannot, because they depend on the pawn
structure around the piece rather than on the square alone. A knight on d5 is
worth a lot when it is defended by a pawn and no enemy pawn can ever chase it,
and very little when it is loose.

Ideas from reading Stockfish 11; nothing copied. Each term is a named, separately
displayable judgement, so the breakdown still reads as chess.

score() and details() both go through `_items`, so they cannot drift apart --
this concept has six sub-terms and duplicating the arithmetic twice, the way the
older concepts do, is how a faithfulness bug gets written.
"""

import chess

from engine.context import ATTACK_SPAN
from engine.weights import wt

CENTER = chess.BB_D4 | chess.BB_E4 | chess.BB_D5 | chess.BB_E5
CENTER_FILES = chess.BB_FILE_C | chess.BB_FILE_D | chess.BB_FILE_E | chess.BB_FILE_F
LONG_DIAGONALS = 0
for _sq in range(64):
    _f, _r = _sq & 7, _sq >> 3
    if _f == _r or _f + _r == 7:
        LONG_DIAGONALS |= 1 << _sq

LIGHT_SQUARES = 0
for _sq in range(64):
    if ((_sq >> 3) + (_sq & 7)) & 1:
        LIGHT_SQUARES |= 1 << _sq
DARK_SQUARES = ~LIGHT_SQUARES & ((1 << 64) - 1)


def _bishop_attacks_through_pieces(sq, pawns):
    """Bishop attacks with only PAWNS blocking: what the bishop would see if the
    pieces in the way moved. That is the right question for a long diagonal."""
    mask = chess.BB_DIAG_MASKS[sq]
    return chess.BB_DIAG_ATTACKS[sq][pawns & mask]


class MinorPieces:
    name = "minor_pieces"
    display_name = "Minor pieces"

    def _items(self, ctx):
        items = []
        board = ctx.board
        phase = ctx.phase
        all_pawns = board.pawns
        occupied = board.occupied

        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = ctx.occupied_co[color]
            own_pawns = all_pawns & own
            enemy_pawns = all_pawns & ctx.occupied_co[not color]
            pawn_atk = ctx.pawn_attacks[color]
            up = 8 if color == chess.WHITE else -8

            # Bad-bishop amplifier: our own pawns with something directly in
            # front of them, on the central files. A blocked centre is what
            # turns "pawns on my colour" into a real problem.
            blocked = own_pawns & (occupied >> up if up > 0 else occupied << -up)
            blocked_centre = bin(blocked & CENTER_FILES).count("1")

            for pt, pname in ((chess.KNIGHT, "knight"), (chess.BISHOP, "bishop")):
                for sq in ctx.pieces[color][pt]:
                    rel_rank = (sq >> 3) if color == chess.WHITE else 7 - (sq >> 3)
                    name = chess.square_name(sq)

                    # Outpost: on the 4th-6th rank, defended by one of our
                    # pawns, and permanently safe from enemy pawns.
                    #
                    # Knights only. The first cut scored bishop outposts too,
                    # at half a knight's bonus, and the tuner drove that weight
                    # to exactly 0.0 -- which is chess: a knight needs a
                    # permanent square because it is short-range, while a bishop
                    # already radiates down a diagonal from anywhere safe.
                    if (pt == chess.KNIGHT and 3 <= rel_rank <= 5
                            and (pawn_atk >> sq) & 1
                            and not (ATTACK_SPAN[color][sq] & enemy_pawns)):
                        items.append((f"{cname} {pname} outpost on {name}",
                                      sign * wt("minor.outpost_knight", phase)))

                    # A minor tucked in behind a pawn is sheltered from attack.
                    ahead = sq + up
                    if rel_rank < 4 and 0 <= ahead <= 63 and (all_pawns >> ahead) & 1:
                        items.append((f"{cname} {pname} behind pawn on {name}",
                                      sign * wt("minor.behind_pawn", phase)))

                    if pt == chess.BISHOP:
                        same_colour = (LIGHT_SQUARES if ((sq >> 3) + (sq & 7)) & 1
                                       else DARK_SQUARES)
                        n = bin(own_pawns & same_colour).count("1")
                        if n:
                            pen = wt("minor.bishop_pawns", phase) * n * (1 + blocked_centre)
                            items.append((f"{cname} bishop on {name} blocked by "
                                          f"{n} own pawn{'s' if n != 1 else ''} "
                                          f"on its colour", -sign * pen))
                        if ((LONG_DIAGONALS >> sq) & 1) and bin(
                                _bishop_attacks_through_pieces(sq, all_pawns)
                                & CENTER).count("1") > 1:
                            items.append((f"{cname} bishop on {name} rakes the centre",
                                          sign * wt("minor.long_diagonal", phase)))
        return items

    def score(self, ctx):
        return sum(v for _, v in self._items(ctx))

    def details(self, ctx):
        return self._items(ctx)

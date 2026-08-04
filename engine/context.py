"""EvalContext: shared, precomputed position facts.

Built once per evaluation so each concept avoids re-scanning the board.
Anything two or more concepts need should live here. This is the hottest
code in the engine (built at every leaf) — bitboard arithmetic only, no
dict/piece_map building.
"""

import chess

_MAX_PHASE = 24  # 4N+4B + 4R*2 + 2Q*4 at the starting position


def _squares(bb):
    """Squares of a bitboard, LSB first."""
    sqs = []
    while bb:
        lsb = bb & -bb
        sqs.append(lsb.bit_length() - 1)
        bb ^= lsb
    return sqs


def _pawn_atk(pawns, color):
    """Squares attacked by `color`'s pawns."""
    if color == chess.WHITE:
        return ((pawns << 7) & ~chess.BB_FILE_H) | ((pawns << 9) & ~chess.BB_FILE_A)
    return ((pawns >> 7) & ~chess.BB_FILE_A) | ((pawns >> 9) & ~chess.BB_FILE_H)


def _build_attack_spans():
    """ATTACK_SPAN[color][sq]: squares where an ENEMY pawn could sit and, by
    advancing, eventually attack `sq` — the adjacent files, ahead of `sq` from
    the enemy's point of view. Empty means no enemy pawn can ever challenge the
    square, which is what makes it an outpost."""
    spans = {chess.WHITE: [0] * 64, chess.BLACK: [0] * 64}
    for sq in range(64):
        f, r = sq & 7, sq >> 3
        for adj in (f - 1, f + 1):
            if not 0 <= adj <= 7:
                continue
            for rr in range(8):
                bit = 1 << (rr * 8 + adj)
                if rr > r:
                    spans[chess.WHITE][sq] |= bit   # black pawns come downward
                elif rr < r:
                    spans[chess.BLACK][sq] |= bit
    return spans


ATTACK_SPAN = _build_attack_spans()


class EvalContext:
    __slots__ = ("board", "pieces", "pawn_files", "king_sq", "phase", "occupied_co",
                 "attacks", "attacked_by", "pawn_attacks")

    def __init__(self, board: chess.Board):
        self.board = board
        occ_w = board.occupied_co[chess.WHITE]
        occ_b = board.occupied_co[chess.BLACK]
        self.occupied_co = (occ_b, occ_w)  # indexable by color bool

        # pieces[color][piece_type] -> list of squares
        self.pieces = {
            chess.WHITE: {
                chess.PAWN: _squares(board.pawns & occ_w),
                chess.KNIGHT: _squares(board.knights & occ_w),
                chess.BISHOP: _squares(board.bishops & occ_w),
                chess.ROOK: _squares(board.rooks & occ_w),
                chess.QUEEN: _squares(board.queens & occ_w),
                chess.KING: _squares(board.kings & occ_w),
            },
            chess.BLACK: {
                chess.PAWN: _squares(board.pawns & occ_b),
                chess.KNIGHT: _squares(board.knights & occ_b),
                chess.BISHOP: _squares(board.bishops & occ_b),
                chess.ROOK: _squares(board.rooks & occ_b),
                chess.QUEEN: _squares(board.queens & occ_b),
                chess.KING: _squares(board.kings & occ_b),
            },
        }

        # Attack masks for sliders/knights, shared by mobility + king attack.
        attacks = {}
        am = board.attacks_mask
        for color in (chess.WHITE, chess.BLACK):
            cp = self.pieces[color]
            for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                for sq in cp[pt]:
                    attacks[sq] = am(sq)
        self.attacks = attacks

        # Full attack-union mask per color (pieces + pawns + king).
        atk_w = atk_b = 0
        for color in (chess.WHITE, chess.BLACK):
            cp = self.pieces[color]
            acc = 0
            for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                for sq in cp[pt]:
                    acc |= attacks[sq]
            pawns = board.pawns & (occ_w if color == chess.WHITE else occ_b)
            acc |= _pawn_atk(pawns, color)
            if cp[chess.KING]:
                acc |= chess.BB_KING_ATTACKS[cp[chess.KING][0]]
            if color == chess.WHITE:
                atk_w = acc
            else:
                atk_b = acc
        self.attacked_by = (atk_b, atk_w)  # indexable by color bool
        # Pawn attacks alone, indexable by color bool. Mobility needs them to
        # subtract unsafe squares; outposts need them to find defended ones.
        self.pawn_attacks = (_pawn_atk(board.pawns & occ_b, chess.BLACK),
                             _pawn_atk(board.pawns & occ_w, chess.WHITE))

        phase = ((board.knights | board.bishops).bit_count()
                 + 2 * board.rooks.bit_count()
                 + 4 * board.queens.bit_count())
        self.phase = phase / _MAX_PHASE if phase < _MAX_PHASE else 1.0

        # pawn_files[color][file] -> list of ranks with a pawn of that color
        pawn_files = {
            chess.WHITE: [[] for _ in range(8)],
            chess.BLACK: [[] for _ in range(8)],
        }
        for color in (chess.WHITE, chess.BLACK):
            files = pawn_files[color]
            for sq in self.pieces[color][chess.PAWN]:
                files[sq & 7].append(sq >> 3)
        self.pawn_files = pawn_files

        wk = self.pieces[chess.WHITE][chess.KING]
        bk = self.pieces[chess.BLACK][chess.KING]
        self.king_sq = {
            chess.WHITE: wk[0] if wk else None,
            chess.BLACK: bk[0] if bk else None,
        }

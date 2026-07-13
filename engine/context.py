"""EvalContext: shared, precomputed position facts.

Built once per evaluation so each concept avoids re-scanning the board.
Anything two or more concepts need should live here.
"""

import chess

# Phase weights: total 24 at the starting position (4N+4B+4R*2+2Q*4).
_PHASE_WEIGHTS = {chess.KNIGHT: 1, chess.BISHOP: 1, chess.ROOK: 2, chess.QUEEN: 4}
_MAX_PHASE = 24


class EvalContext:
    __slots__ = (
        "board", "piece_map", "pieces", "pawn_files", "king_sq", "phase",
        "occupied", "occupied_co",
    )

    def __init__(self, board: chess.Board):
        self.board = board
        self.piece_map = board.piece_map()
        self.occupied = board.occupied
        self.occupied_co = (board.occupied_co[chess.BLACK], board.occupied_co[chess.WHITE])

        # pieces[color][piece_type] -> list of squares
        pieces = {
            chess.WHITE: {pt: [] for pt in chess.PIECE_TYPES},
            chess.BLACK: {pt: [] for pt in chess.PIECE_TYPES},
        }
        phase = 0
        for sq, piece in self.piece_map.items():
            pieces[piece.color][piece.piece_type].append(sq)
            phase += _PHASE_WEIGHTS.get(piece.piece_type, 0)
        self.pieces = pieces
        self.phase = min(1.0, phase / _MAX_PHASE)  # 1.0 = middlegame, 0.0 = bare endgame

        # pawn_files[color][file] -> sorted list of ranks with a pawn of that color
        pawn_files = {
            chess.WHITE: [[] for _ in range(8)],
            chess.BLACK: [[] for _ in range(8)],
        }
        for color in (chess.WHITE, chess.BLACK):
            for sq in pieces[color][chess.PAWN]:
                pawn_files[color][chess.square_file(sq)].append(chess.square_rank(sq))
        self.pawn_files = pawn_files

        self.king_sq = {
            chess.WHITE: board.king(chess.WHITE),
            chess.BLACK: board.king(chess.BLACK),
        }

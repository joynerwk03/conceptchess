"""Search: iterative-deepening negamax with alpha-beta pruning.

Features: transposition table, MVV-LVA + killer + history move ordering,
quiescence search with delta pruning, null-move pruning, check extension,
soft time management.

Scores inside the search are centipawns from the side-to-move's perspective.
"""

import time
from dataclasses import dataclass, field

import chess

from engine.evaluation import evaluate
from engine.concepts.material import PIECE_VALUES

MATE_SCORE = 100_000
MATE_THRESHOLD = 90_000

TT_EXACT, TT_LOWER, TT_UPPER = 0, 1, 2


class TimeUp(Exception):
    pass


@dataclass
class SearchResult:
    move: chess.Move = None
    score: float = 0.0          # cp, side-to-move perspective; mate scores near +/-MATE_SCORE
    depth: int = 0
    nodes: int = 0
    time: float = 0.0
    pv: list = field(default_factory=list)

    @property
    def nps(self):
        return int(self.nodes / self.time) if self.time > 0 else 0


class Searcher:
    def __init__(self):
        self.tt = {}
        self.nodes = 0
        self.stop_time = None
        self.killers = [[None, None] for _ in range(128)]
        self.history = {}

    def search(self, board, movetime=1.0, max_depth=64, info_callback=None):
        """Iterative deepening. movetime is a soft budget in seconds."""
        # Work on a private copy: a TimeUp mid-line would otherwise leave
        # pushed moves on the caller's board.
        board = board.copy()
        start = time.perf_counter()
        self.stop_time = start + movetime
        self.nodes = 0
        self.killers = [[None, None] for _ in range(128)]
        self.history = {}
        if len(self.tt) > 2_000_000:
            self.tt.clear()

        result = SearchResult()
        root_moves = list(board.legal_moves)
        if not root_moves:
            return result

        for depth in range(1, max_depth + 1):
            try:
                score, move = self._search_root(board, depth, root_moves)
            except TimeUp:
                break
            result.move = move
            result.score = score
            result.depth = depth
            result.nodes = self.nodes
            result.time = time.perf_counter() - start
            result.pv = self._extract_pv(board, depth)
            if info_callback:
                info_callback(result)
            # Stop early on forced mate or if there's no time for another iteration.
            if abs(score) > MATE_THRESHOLD:
                break
            if time.perf_counter() - start > movetime * 0.5:
                break
        result.time = time.perf_counter() - start
        result.nodes = self.nodes
        return result

    def _search_root(self, board, depth, root_moves):
        alpha, beta = -MATE_SCORE, MATE_SCORE
        best_move = None
        tt_move = self._tt_move(board)
        ordered = self._order_moves(board, root_moves, tt_move, 0)
        for move in ordered:
            board.push(move)
            score = -self._negamax(board, depth - 1, -beta, -alpha, 1)
            board.pop()
            if score > alpha:
                alpha = score
                best_move = move
        # Keep the best root move first for the next iteration.
        if best_move in root_moves:
            root_moves.remove(best_move)
            root_moves.insert(0, best_move)
        self.tt[board._transposition_key()] = (depth, TT_EXACT, alpha, best_move)
        return alpha, best_move

    def _negamax(self, board, depth, alpha, beta, ply):
        self.nodes += 1
        if not self.nodes & 1023 and time.perf_counter() > self.stop_time:
            raise TimeUp

        if board.is_repetition(2) or board.halfmove_clock >= 100 or board.is_insufficient_material():
            return 0

        in_check = board.is_check()
        if in_check:
            depth += 1  # check extension

        if depth <= 0:
            return self._quiescence(board, alpha, beta, ply)

        key = board._transposition_key()
        tt_entry = self.tt.get(key)
        tt_move = None
        if tt_entry is not None:
            tt_depth, tt_flag, tt_score, tt_move = tt_entry
            if tt_depth >= depth and ply > 0:
                if tt_flag == TT_EXACT:
                    return tt_score
                if tt_flag == TT_LOWER and tt_score >= beta:
                    return tt_score
                if tt_flag == TT_UPPER and tt_score <= alpha:
                    return tt_score

        # Null-move pruning: skip a turn; if we still beat beta, prune.
        if (depth >= 3 and not in_check and beta < MATE_THRESHOLD
                and self._has_non_pawn_material(board)):
            board.push(chess.Move.null())
            score = -self._negamax(board, depth - 3, -beta, -beta + 1, ply + 1)
            board.pop()
            if score >= beta:
                return beta

        moves = list(board.legal_moves)
        if not moves:
            return -MATE_SCORE + ply if in_check else 0

        ordered = self._order_moves(board, moves, tt_move, ply)
        best_score = -MATE_SCORE - 1
        best_move = None
        orig_alpha = alpha
        for i, move in enumerate(ordered):
            is_quiet = not board.is_capture(move) and move.promotion is None
            board.push(move)
            # Late move reductions: well-ordered quiet moves late in the list
            # rarely matter — search them shallower, re-search on surprise.
            # (Checks are safe: the in-check extension restores depth below.)
            if (depth >= 3 and i >= 4 and is_quiet and not in_check):
                score = -self._negamax(board, depth - 2, -alpha - 1, -alpha, ply + 1)
                if score > alpha:
                    score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            else:
                score = -self._negamax(board, depth - 1, -beta, -alpha, ply + 1)
            board.pop()
            if score > best_score:
                best_score = score
                best_move = move
            if score > alpha:
                alpha = score
            if alpha >= beta:
                if is_quiet and ply < len(self.killers):
                    k = self.killers[ply]
                    if k[0] != move:
                        k[1] = k[0]
                        k[0] = move
                    hk = (board.turn, move.from_square, move.to_square)
                    self.history[hk] = self.history.get(hk, 0) + depth * depth
                break

        flag = TT_EXACT
        if best_score <= orig_alpha:
            flag = TT_UPPER
        elif best_score >= beta:
            flag = TT_LOWER
        self.tt[key] = (depth, flag, best_score, best_move)
        return best_score

    def _quiescence(self, board, alpha, beta, ply):
        self.nodes += 1
        if not self.nodes & 1023 and time.perf_counter() > self.stop_time:
            raise TimeUp

        stand_pat = evaluate(board)
        if board.turn == chess.BLACK:
            stand_pat = -stand_pat
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        captures = list(board.generate_legal_captures())
        # Non-capturing queen promotions are tactically loud too.
        promo_rank = chess.BB_RANK_7 if board.turn == chess.WHITE else chess.BB_RANK_2
        if board.pawns & board.occupied_co[board.turn] & promo_rank:
            captures.extend(
                m for m in board.generate_legal_moves(
                    board.pawns & promo_rank, ~board.occupied)
                if m.promotion == chess.QUEEN)
        captures.sort(key=lambda m: self._mvv_lva(board, m), reverse=True)
        for move in captures:
            # Delta pruning: even winning the victim can't raise alpha.
            victim = self._victim_value(board, move)
            if stand_pat + victim + 200 < alpha:
                continue
            board.push(move)
            score = -self._quiescence(board, -beta, -alpha, ply + 1)
            board.pop()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    # ----- move ordering helpers -----

    def _order_moves(self, board, moves, tt_move, ply):
        killers = self.killers[ply] if ply < len(self.killers) else (None, None)
        history = self.history
        turn = board.turn

        def key(move):
            if move == tt_move:
                return 1_000_000
            if board.is_capture(move):
                return 100_000 + self._mvv_lva(board, move)
            if move.promotion == chess.QUEEN:
                return 90_000
            if move == killers[0]:
                return 80_000
            if move == killers[1]:
                return 79_000
            return history.get((turn, move.from_square, move.to_square), 0)

        return sorted(moves, key=key, reverse=True)

    def _mvv_lva(self, board, move):
        victim = self._victim_value(board, move)
        attacker = board.piece_type_at(move.from_square)
        return victim * 10 - PIECE_VALUES.get(attacker, 0)

    @staticmethod
    def _victim_value(board, move):
        if move.promotion:
            return PIECE_VALUES[chess.QUEEN]
        if board.is_en_passant(move):
            return PIECE_VALUES[chess.PAWN]
        vt = board.piece_type_at(move.to_square)
        return PIECE_VALUES.get(vt, 0)

    @staticmethod
    def _has_non_pawn_material(board):
        c = board.turn
        return bool(board.knights & board.occupied_co[c]
                    or board.bishops & board.occupied_co[c]
                    or board.rooks & board.occupied_co[c]
                    or board.queens & board.occupied_co[c])

    def _tt_move(self, board):
        entry = self.tt.get(board._transposition_key())
        return entry[3] if entry else None

    def _extract_pv(self, board, max_len):
        pv = []
        b = board.copy(stack=False)
        seen = set()
        for _ in range(max_len):
            key = b._transposition_key()
            if key in seen:
                break
            seen.add(key)
            entry = self.tt.get(key)
            if not entry or entry[3] is None or entry[3] not in b.legal_moves:
                break
            pv.append(entry[3])
            b.push(entry[3])
        return pv

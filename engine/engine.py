"""Top-level engine API.

By default the engine searches with the compiled core (engine/core.py) — a
C move generator + search + a fast eval that is cross-checked identical to the
Python concept eval. The Python explanation layer stays authoritative for the
"why": breakdowns come from evaluate_detailed, so the displayed concepts are
exactly the numbers the fast search optimized. Pass use_core=False to search
in pure Python (used by tests of the Python search and the contrastive
alternative).
"""

import random
import time

import chess

from engine.search import Searcher, SearchResult
from engine.explain import explain_move, book_explanation
from engine.evaluation import evaluate, evaluate_detailed
from engine import book
from engine import core


class Engine:
    def __init__(self, use_book=True, book_seed=None, use_core=True):
        self.searcher = Searcher()
        self.use_book = use_book
        self.use_core = use_core and core.HAS_CORE
        self._rng = random.Random(book_seed)

    def _book_result(self, board):
        if not self.use_book:
            return None, None
        move, name = book.lookup(board, self._rng)
        if move is None:
            return None, None
        r = SearchResult(move=move, score=0.0, depth=0, nodes=0, time=0.0)
        r.book = True
        r.book_name = name
        return r, name

    def best_move(self, board, movetime=1.0, max_depth=64, info_callback=None):
        """Search and return a SearchResult (or a book move in the opening)."""
        r, _ = self._book_result(board)
        if r is not None:
            return r
        if self.use_core:
            t = time.perf_counter()
            move, score, depth, nodes, pv, second = core.search(board, movetime, max_depth)
            r = SearchResult(move=move, score=score, depth=depth, nodes=nodes,
                             time=time.perf_counter() - t, pv=pv)
            r.root_ranking = [move, second] if move else []
            return r
        return self.searcher.search(board, movetime=movetime, max_depth=max_depth,
                                    info_callback=info_callback)

    def best_move_explained(self, board, movetime=1.0, max_depth=64):
        """Search and return (SearchResult, explanation dict).

        The concept breakdown and expected line are always shown. The
        contrastive runner-up comparison is produced when searching in pure
        Python (it needs the full root ranking)."""
        r, name = self._book_result(board)
        if r is not None:
            return r, book_explanation(board, r.move, name)
        result = self.best_move(board, movetime=movetime, max_depth=max_depth)
        if not result.move:
            return result, None
        sub_time = max(0.05, result.time * 0.3) if result.time else 0.2

        if self.use_core:
            def sub_search(bd):
                _, sc, _, _, pv, _ = core.search(bd, movetime=sub_time)
                return sc, pv
        else:
            def sub_search(bd):
                depth = max(2, result.depth - 2)
                r = self.searcher.search(bd, movetime=sub_time, max_depth=depth)
                return r.score, r.pv

        explanation = explain_move(board, result, sub_search=sub_search)
        return result, explanation

    def new_game(self):
        self.searcher = Searcher()

    @staticmethod
    def static_eval(board):
        return evaluate(board)

    @staticmethod
    def static_eval_detailed(board):
        return evaluate_detailed(board)

"""Top-level engine API."""

import random

import chess

from engine.search import Searcher
from engine.explain import explain_move, book_explanation
from engine.evaluation import evaluate, evaluate_detailed
from engine import book


class Engine:
    def __init__(self, use_book=True, book_seed=None):
        self.searcher = Searcher()
        self.use_book = use_book
        self._rng = random.Random(book_seed)

    def _book_result(self, board):
        """A SearchResult for a book move, or None."""
        if not self.use_book:
            return None, None
        move, name = book.lookup(board, self._rng)
        if move is None:
            return None, None
        from engine.search import SearchResult
        r = SearchResult(move=move, score=0.0, depth=0, nodes=0, time=0.0)
        r.book = True
        r.book_name = name
        return r, name

    def best_move(self, board, movetime=1.0, max_depth=64, info_callback=None):
        """Search and return a SearchResult (or a book move in the opening)."""
        r, _ = self._book_result(board)
        if r is not None:
            return r
        return self.searcher.search(board, movetime=movetime, max_depth=max_depth,
                                    info_callback=info_callback)

    def best_move_explained(self, board, movetime=1.0, max_depth=64):
        """Search and return (SearchResult, explanation dict).

        In the opening this returns a book move with a book explanation;
        otherwise the explanation includes a contrastive comparison against
        the runner-up root move (briefly sub-searched)."""
        r, name = self._book_result(board)
        if r is not None:
            return r, book_explanation(board, r.move, name)
        result = self.best_move(board, movetime=movetime, max_depth=max_depth)
        explanation = (explain_move(board, result, searcher=self.searcher)
                       if result.move else None)
        return result, explanation

    def new_game(self):
        self.searcher = Searcher()

    @staticmethod
    def static_eval(board):
        return evaluate(board)

    @staticmethod
    def static_eval_detailed(board):
        return evaluate_detailed(board)

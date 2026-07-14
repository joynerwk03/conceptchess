"""Top-level engine API."""

import chess

from engine.search import Searcher
from engine.explain import explain_move
from engine.evaluation import evaluate, evaluate_detailed


class Engine:
    def __init__(self):
        self.searcher = Searcher()

    def best_move(self, board, movetime=1.0, max_depth=64, info_callback=None):
        """Search and return a SearchResult."""
        return self.searcher.search(board, movetime=movetime, max_depth=max_depth,
                                    info_callback=info_callback)

    def best_move_explained(self, board, movetime=1.0, max_depth=64):
        """Search and return (SearchResult, explanation dict).

        The explanation includes a contrastive comparison against the
        runner-up root move (briefly sub-searched)."""
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

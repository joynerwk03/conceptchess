"""Candidate iteration metrics for session 3 (move-ranking family).

Session-2 lesson: absolute eval agreement with SF (evalloss) is a bad tuning
target because play depends on ranking *sibling* moves correctly. These
metrics measure exactly that, on the SF multipv labels from make_moveset.py.

- rank_agreement:  our static eval picks SF's best move among SF's top-3
- qrank_agreement: same, but move values come from quiescence search
- move_match:      full engine search (fixed shallow depth) matches SF's best

All report percentages over positions where SF's margin between best and
second move is >= GAP centipawns (ambiguous positions carry no signal).
Higher is better.
"""

import json
from pathlib import Path

import chess

try:
    from engine.evaluation import evaluate, clear_caches
except ImportError:  # pre-session-2 engine versions have no cache API
    from engine.evaluation import evaluate

    def clear_caches():
        pass

DATA = Path(__file__).parent / "data"
GAP = 30  # cp; minimum SF margin between best and 2nd move
_cache = {}


def _load(split):
    if split not in _cache:
        rows = [json.loads(l) for l in
                (DATA / f"moves_{split}.jsonl").read_text().splitlines()]
        keep = []
        for r in rows:
            if len(r["moves"]) < 2:
                continue
            board = chess.Board(r["fen"])
            sign = 1 if board.turn == chess.WHITE else -1
            margin = sign * (r["moves"][0][1] - r["moves"][1][1])
            if margin >= GAP:
                keep.append((board, [chess.Move.from_uci(u) for u, _ in r["moves"]]))
        _cache[split] = keep
    return _cache[split]


def _agreement(split, value_fn):
    clear_caches()
    data = _load(split)
    hits = 0
    for board, moves in data:
        sign = 1 if board.turn == chess.WHITE else -1
        best_i, best_v = 0, -1e18
        for i, mv in enumerate(moves):
            board.push(mv)
            v = sign * value_fn(board)
            board.pop()
            if v > best_v:
                best_v, best_i = v, i
        hits += best_i == 0
    return 100.0 * hits / len(data)


def rank_agreement(split="val"):
    """Static eval ranks SF's best move first (%)."""
    return _agreement(split, evaluate)


def qrank_agreement(split="val"):
    """Quiescence value ranks SF's best move first (%)."""
    from engine.search import Searcher, MATE_SCORE
    s = Searcher()
    s.stop_time = float("inf")

    def qval(board):
        q = s._quiescence(board, -MATE_SCORE, MATE_SCORE, 0)
        return q if board.turn == chess.WHITE else -q

    return _agreement(split, qval)


def move_match(split="val", depth=3, limit=250):
    """Engine search at fixed depth picks SF's best move (%)."""
    from engine.engine import Engine
    clear_caches()
    data = _load(split)[:limit]
    engine = Engine()
    hits = 0
    for board, moves in data:
        engine.new_game()
        r = engine.best_move(board, movetime=60, max_depth=depth)
        hits += r.move == moves[0]
    return 100.0 * hits / len(data)


if __name__ == "__main__":
    for name, fn in (("rank_agreement", rank_agreement),
                     ("qrank_agreement", qrank_agreement)):
        print(f"{name}: train {fn('train'):.2f}%  val {fn('val'):.2f}%")
    print(f"move_match(d3): val {move_match('val'):.2f}%")

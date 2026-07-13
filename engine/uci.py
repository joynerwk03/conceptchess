"""Minimal UCI interface.

Run with: python -m engine.uci
Used by the research match harness (and any standard chess GUI).
"""

import sys

import chess

from engine.engine import Engine
from engine.explain import mate_distance
from engine.search import MATE_SCORE

ENGINE_NAME = "ConceptChess"


def _score_info(score):
    md = mate_distance(score)
    if md is not None:
        moves = (abs(md) + 1) // 2
        return f"mate {moves if md > 0 else -moves}"
    return f"cp {int(score)}"


def main():
    engine = Engine()
    board = chess.Board()

    for line in sys.stdin:
        parts = line.strip().split()
        if not parts:
            continue
        cmd = parts[0]

        if cmd == "uci":
            print(f"id name {ENGINE_NAME}")
            print("id author autoresearch")
            print("uciok", flush=True)
        elif cmd == "isready":
            print("readyok", flush=True)
        elif cmd == "ucinewgame":
            engine.new_game()
            board = chess.Board()
        elif cmd == "position":
            board = _parse_position(parts[1:])
        elif cmd == "go":
            movetime = _parse_go(parts[1:], board)
            max_depth = 64
            if "depth" in parts:
                max_depth = int(parts[parts.index("depth") + 1])

            def info(r):
                pv = " ".join(m.uci() for m in r.pv)
                print(f"info depth {r.depth} score {_score_info(r.score)} "
                      f"nodes {r.nodes} nps {r.nps} pv {pv}", flush=True)

            result = engine.best_move(board, movetime=movetime, max_depth=max_depth,
                                      info_callback=info)
            move = result.move.uci() if result.move else "0000"
            print(f"bestmove {move}", flush=True)
        elif cmd == "quit":
            break


def _parse_position(args):
    board = chess.Board()
    i = 0
    if args and args[0] == "startpos":
        i = 1
    elif args and args[0] == "fen":
        fen = " ".join(args[1:7])
        board = chess.Board(fen)
        i = 7
    if i < len(args) and args[i] == "moves":
        for uci in args[i + 1:]:
            board.push(chess.Move.from_uci(uci))
    return board


def _parse_go(args, board):
    """Return a movetime in seconds from go parameters."""
    params = {}
    i = 0
    while i < len(args) - 1:
        params[args[i]] = args[i + 1]
        i += 2
    if "movetime" in params:
        return int(params["movetime"]) / 1000
    if "depth" in params:
        return 3600  # depth-limited searches shouldn't hit the clock
    my_time = params.get("wtime" if board.turn == chess.WHITE else "btime")
    my_inc = params.get("winc" if board.turn == chess.WHITE else "binc", 0)
    if my_time is not None:
        remaining = int(my_time) / 1000
        inc = int(my_inc) / 1000
        # Spend ~1/25 of remaining time plus most of the increment.
        return max(0.05, remaining / 25 + inc * 0.8)
    return 1.0


if __name__ == "__main__":
    main()

"""Build the labeled evaluation set for the eval-loss metric.

Positions come from fast self-play games (realistic distribution) plus some
random-walk games (diversity). Each position is filtered to be quiet (not in
check, quiescence ~= static eval) and labeled with Stockfish's eval at fixed
depth. Output: research/data/evalset_train.jsonl / evalset_val.jsonl with
{"fen": ..., "sf_cp": ...} lines. Generated ONCE and committed — the metric
is only comparable across experiments if the set never changes.

Usage: python -m research.make_evalset
"""

import json
import random
import shutil
from pathlib import Path

import chess
import chess.engine

from engine.engine import Engine
from engine.evaluation import evaluate
from engine.search import Searcher, MATE_SCORE

OUT_DIR = Path(__file__).parent / "data"
SF_DEPTH = 12
CLIP = 1200  # cp; mates clipped here too
TARGET = 3000
VAL_FRACTION = 1 / 3

OPENING_PLIES = 6


def selfplay_positions(n_games, rng, movetime=0.05):
    """Fast self-play; collect all positions after the opening."""
    positions = []
    for g in range(n_games):
        engine = Engine()
        board = chess.Board()
        for _ in range(OPENING_PLIES):  # randomized opening for diversity
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        plies = 0
        while not board.is_game_over(claim_draw=True) and plies < 160:
            r = engine.best_move(board, movetime=movetime)
            if r.move is None:
                break
            board.push(r.move)
            plies += 1
            positions.append(board.fen())
        print(f"  selfplay game {g + 1}/{n_games}: {plies} plies")
    return positions


def randomwalk_positions(n_games, rng):
    positions = []
    for _ in range(n_games):
        board = chess.Board()
        for _ in range(rng.randrange(10, 70)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
            positions.append(board.fen())
    return positions


def is_quiet(board, searcher):
    """Quiet = not in check and quiescence agrees with the static eval."""
    if board.is_check():
        return False
    static = evaluate(board)
    stm = static if board.turn == chess.WHITE else -static
    searcher.nodes = 0
    searcher.stop_time = float("inf")
    q = searcher._quiescence(board, -MATE_SCORE, MATE_SCORE, 0)
    return abs(q - stm) < 30


def main():
    rng = random.Random(2026)
    OUT_DIR.mkdir(exist_ok=True)

    print("generating self-play positions...")
    fens = selfplay_positions(24, rng)
    print("generating random-walk positions...")
    fens += randomwalk_positions(40, rng)
    fens = list(dict.fromkeys(fens))  # dedupe, keep order
    rng.shuffle(fens)
    print(f"{len(fens)} unique candidate positions")

    searcher = Searcher()
    sf = chess.engine.SimpleEngine.popen_uci(shutil.which("stockfish"))
    rows = []
    try:
        for fen in fens:
            if len(rows) >= TARGET:
                break
            board = chess.Board(fen)
            if board.is_game_over() or not is_quiet(board, searcher):
                continue
            info = sf.analyse(board, chess.engine.Limit(depth=SF_DEPTH))
            cp = info["score"].white().score(mate_score=CLIP + 1)
            cp = max(-CLIP, min(CLIP, cp))
            rows.append({"fen": fen, "sf_cp": cp})
            if len(rows) % 250 == 0:
                print(f"  labeled {len(rows)}/{TARGET}")
    finally:
        sf.quit()

    n_val = int(len(rows) * VAL_FRACTION)
    val, train = rows[:n_val], rows[n_val:]
    for name, part in (("train", train), ("val", val)):
        path = OUT_DIR / f"evalset_{name}.jsonl"
        path.write_text("\n".join(json.dumps(r) for r in part) + "\n")
        print(f"wrote {len(part)} -> {path}")


if __name__ == "__main__":
    main()

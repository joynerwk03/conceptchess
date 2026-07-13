"""Mine verified tactics positions with Stockfish.

Generates EPD test suites where each position has a UNIQUE clearly-best move
(multipv gap >= --gap centipawns at --depth), verified by Stockfish. This is
the ground truth for the tactics accuracy metric.

Usage:
  python -m research.make_suite --count 24 --out tests/suites/tactics_v1.epd
  python -m research.make_suite --count 50 --gap 250 --min-eval 150 --out research/suites/hard.epd
"""

import argparse
import random
import shutil
import sys

import chess
import chess.engine

STOCKFISH = shutil.which("stockfish")


def random_position(rng, min_plies=12, max_plies=60):
    board = chess.Board()
    for _ in range(rng.randrange(min_plies, max_plies)):
        moves = list(board.legal_moves)
        if not moves:
            break
        board.push(rng.choice(moves))
    return board


def analyze(sf, board, depth):
    infos = sf.analyse(board, chess.engine.Limit(depth=depth), multipv=2)
    if len(infos) < 2:
        return None
    best = infos[0]["score"].pov(board.turn)
    second = infos[1]["score"].pov(board.turn)
    move = infos[0]["pv"][0]
    return best, second, move


def cp(score, mate_value=10_000):
    return score.score(mate_score=mate_value)


def mine(count, depth, gap, min_eval, max_eval, seed):
    if not STOCKFISH:
        sys.exit("stockfish not found on PATH")
    rng = random.Random(seed)
    sf = chess.engine.SimpleEngine.popen_uci(STOCKFISH)
    found = []
    seen = set()
    tried = 0
    try:
        while len(found) < count and tried < count * 200:
            tried += 1
            board = random_position(rng)
            if board.is_game_over() or board.fen() in seen:
                continue
            seen.add(board.fen())
            res = analyze(sf, board, depth)
            if res is None:
                continue
            best, second, move = res
            b, s = cp(best), cp(second)
            # Unique winning tactic: best move clearly wins, alternatives clearly worse.
            if b < min_eval or b > max_eval:
                continue
            if b - s < gap:
                continue
            epd = board.epd(bm=move)
            found.append(epd)
            print(f"[{len(found)}/{count}] {epd}   (best {b:+d} vs second {s:+d})")
    finally:
        sf.quit()
    return found


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=24)
    p.add_argument("--depth", type=int, default=16, help="Stockfish verification depth")
    p.add_argument("--gap", type=int, default=200,
                   help="min cp gap between best and 2nd-best move")
    p.add_argument("--min-eval", type=int, default=150,
                   help="best move must win at least this much (cp)")
    p.add_argument("--max-eval", type=int, default=3000,
                   help="skip already-totally-won positions")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    epds = mine(args.count, args.depth, args.gap, args.min_eval, args.max_eval, args.seed)
    with open(args.out, "w") as f:
        f.write("\n".join(epds) + "\n")
    print(f"wrote {len(epds)} positions to {args.out}")


if __name__ == "__main__":
    main()

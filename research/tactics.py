"""Run an EPD tactics suite against the engine and report accuracy.

Usage:
  python -m research.tactics tests/suites/tactics_v1.epd --movetime 1.0
"""

import argparse
import time

import chess

from engine.engine import Engine


def run_suite(path, movetime=1.0, verbose=True):
    with open(path) as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    solved = 0
    results = []
    engine = Engine()
    start = time.perf_counter()
    for i, line in enumerate(lines, 1):
        board, ops = chess.Board.from_epd(line)
        best_moves = ops.get("bm", [])
        engine.new_game()
        r = engine.best_move(board, movetime=movetime)
        ok = r.move in best_moves
        solved += ok
        results.append((line, r.move, ok))
        if verbose:
            expect = "/".join(board.san(m) for m in best_moves)
            got = board.san(r.move) if r.move else "-"
            mark = "ok " if ok else "FAIL"
            print(f"[{i:3d}] {mark} expected {expect:<8} got {got:<8} depth {r.depth}")
    elapsed = time.perf_counter() - start
    pct = 100 * solved / len(lines) if lines else 0
    if verbose:
        print(f"\n{solved}/{len(lines)} solved ({pct:.1f}%) in {elapsed:.1f}s "
              f"at {movetime}s/move")
    return {"solved": solved, "total": len(lines), "pct": pct, "movetime": movetime}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("suite")
    p.add_argument("--movetime", type=float, default=1.0)
    args = p.parse_args()
    run_suite(args.suite, args.movetime)


if __name__ == "__main__":
    main()

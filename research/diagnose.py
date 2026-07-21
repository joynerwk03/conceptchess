"""Weak-concept diagnosis: turn engine mistakes into targeted eval work.

For each position in a Stockfish-verified suite where the engine picks a
different move than the verified best, this reports which CONCEPT most
accounts for the engine preferring its (worse) move — the static evaluation
of the position after each move, broken down by concept, differenced.

If the engine plays E where Stockfish says B is clearly best, and the engine's
static eval ranks E above B, the concept with the largest delta favouring E is
the one mis-valuing the position. Aggregated over many misses, a pattern in
that column is a concrete eval-improvement target (unlike guessing).

Usage:
  python -m research.diagnose tests/suites/tactics_quiet.epd --movetime 0.3
"""

import argparse
from collections import defaultdict
from pathlib import Path

import chess

from engine.engine import Engine
from engine.evaluation import evaluate_detailed


def _concept_scores(board):
    """name -> cp (White's perspective)."""
    bd = evaluate_detailed(board)
    return {c.name: c.score for c in bd.concepts}, bd.total


def diagnose(path, movetime):
    lines = [l.strip() for l in Path(path).read_text().splitlines() if l.strip()]
    engine = Engine(use_book=False)
    misses = 0
    solved = 0
    culprit_mass = defaultdict(float)   # concept -> summed cp it wrongly favoured
    culprit_count = defaultdict(int)
    for ln in lines:
        board, ops = chess.Board().from_epd(ln)
        best = ops.get("bm", [None])
        best = best[0] if isinstance(best, list) else best
        if best is None:
            continue
        r = engine.best_move(board, movetime=movetime)
        if r.move == best:
            solved += 1
            continue
        misses += 1
        # static eval (side-to-move POV) after the engine's move vs the best move
        stm = board.turn
        sign = 1 if stm == chess.WHITE else -1
        def after(mv):
            b = board.copy(); b.push(mv)
            sc, tot = _concept_scores(b)
            return sc, tot
        e_sc, e_tot = after(r.move)
        b_sc, b_tot = after(best)
        # positive delta = concept favours the engine's (worse) move from stm POV
        print(f"\n{board.fen()}")
        print(f"  engine: {r.move}  (static {sign*e_tot:+.0f})   "
              f"best: {best}  (static {sign*b_tot:+.0f})")
        deltas = []
        for name in e_sc:
            d = sign * (e_sc[name] - b_sc[name])   # >0: this concept prefers engine's move
            if abs(d) >= 5:
                deltas.append((d, name))
        deltas.sort(reverse=True)
        for d, name in deltas[:4]:
            print(f"    {name:16s} {d:+.0f}")
        if deltas and deltas[0][0] > 0:
            culprit_mass[deltas[0][1]] += deltas[0][0]
            culprit_count[deltas[0][1]] += 1

    n = solved + misses
    print(f"\n=== {solved}/{n} solved; {misses} misses ===")
    if culprit_mass:
        print("top concepts favouring the WRONG move (mass, count):")
        for name in sorted(culprit_mass, key=lambda k: -culprit_mass[k]):
            print(f"  {name:16s} {culprit_mass[name]:+7.0f}cp  "
                  f"({culprit_count[name]} positions)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("suite")
    p.add_argument("--movetime", type=float, default=0.3)
    a = p.parse_args()
    diagnose(a.suite, a.movetime)


if __name__ == "__main__":
    main()

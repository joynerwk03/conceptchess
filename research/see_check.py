"""Verify static exchange evaluation against brute force.

SEE is load-bearing in two places, and one of them is destructive:

    order()   ranks a capture by see(); losing captures drop below quiet history
    qsearch() `if(is_capture(b,m) && see(b,m) < 0) continue;`  -- PRUNED OUTRIGHT

A mis-ordered capture costs a little time. A capture wrongly scored negative is
never searched at all, at every quiescence node, for the whole game. That is
tactical blindness with no symptom any evaluation metric can show: the eval is
faithful, the tests pass, the tree looks healthy, and the engine simply does not
see a class of tactic. It is exactly the kind of defect worth hunting with
ground truth rather than with games, since a gate resolving +/-23 Elo would
never isolate it.

The reference here is the definition rather than another implementation of the
same algorithm: play out the exchange on the target square exhaustively, trying
every capture available to each side in turn and taking the best line, with the
standard option to stand pat. Both the engine's swap algorithm and this
brute-force minimax should agree on the sign, which is what the pruning uses.

Positions are drawn from real games so the material and pin structures are
realistic, and only positions with at least one capture are graded.

    PYTHONPATH=. .venv/bin/python research/see_check.py --n 3000
"""
import argparse
import json
import random

import chess

from engine.search import ORDER_VALUES, Searcher

_see = Searcher._see
from research.texel import ROOT


def brute_see(board, move, depth=0):
    """Exhaustive exchange value on move.to_square, from the mover's side.

    The definition rather than the algorithm: capture, then let the opponent
    choose their best recapture on that square or decline, recursively. Standing
    pat is allowed at every step after the first, which is what makes SEE a
    lower bound on the exchange rather than a forced sequence.
    """
    to = move.to_square
    if board.is_en_passant(move):
        victim = ORDER_VALUES[chess.PAWN]
    else:
        vt = board.piece_type_at(to)
        if vt is None:
            return 0
        victim = ORDER_VALUES[vt]
    board.push(move)
    try:
        best = 0                      # opponent may decline to recapture
        for reply in board.legal_moves:
            if reply.to_square != to or not board.is_capture(reply):
                continue
            val = brute_see(board, reply, depth + 1)
            if val > best:
                best = val
        return victim - best
    finally:
        board.pop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel4.jsonl"))
    ap.add_argument("--n", type=int, default=3000, help="captures to grade")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.data)]
    random.Random(a.seed).shuffle(rows)

    graded = sign_bad = value_bad = 0
    prunable_bad = 0
    examples = []
    for r in rows:
        if graded >= a.n:
            break
        b = chess.Board(r["fen"])
        for mv in b.legal_moves:
            if graded >= a.n:
                break
            if not b.is_capture(mv):
                continue
            graded += 1
            got = _see(b, mv)
            want = brute_see(b, mv)
            if got != want:
                value_bad += 1
            if (got < 0) != (want < 0):
                sign_bad += 1
                # the damaging case: qsearch prunes it, brute force says it wins
                if got < 0 <= want:
                    prunable_bad += 1
                if len(examples) < 10:
                    examples.append((b.fen(), mv.uci(), got, want))

    print(f"\n{graded:,} captures graded against brute-force exchange")
    print(f"  exact value mismatches : {value_bad:,} "
          f"({100*value_bad/max(graded,1):.2f}%)")
    print(f"  SIGN mismatches        : {sign_bad:,} "
          f"({100*sign_bad/max(graded,1):.2f}%)   <- what pruning keys on")
    print(f"  wrongly pruned (see<0, truth>=0): {prunable_bad:,}")
    if examples:
        print("\n  examples (fen, move, see, brute):")
        for fen, mv, got, want in examples:
            print(f"    {mv}  see={got:>6}  brute={want:>6}   {fen}")
    else:
        print("\n  no sign disagreements found")


if __name__ == "__main__":
    main()

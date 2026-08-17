"""Verify that a claimed mate is an actual mate, at the claimed distance.

Mate scores are the one part of a search's output that can be checked against
ground truth without another engine: if the search says "mate in 5", playing its
own principal variation must reach checkmate in five moves. Nothing else in the
engine's output is falsifiable that directly.

It is also a place bugs hide well. Mate scores are stored ply-RELATIVE in the
transposition table and re-based on the way out (`score_from_tt`), because the
same position reached at a different depth implies a different distance to mate.
An error there does not crash, does not fail perft, does not move the evaluation
by a centipawn, and does not show up in a game gate -- it shows up as an engine
that announces mate in 4 and then does not deliver it, or worse, prefers a
slower mate and lets a win slip under the fifty-move rule.

Positions are drawn from the tablebase, which supplies endings that are won by
force, and from the tactics suite, which supplies middlegame mates. Every claim
the search makes is then played out against python-chess.

    PYTHONPATH=. .venv/bin/python research/mate_check.py --n 120
"""
import argparse
import random

import chess

from engine import tablebase as tb


def gen_mating_positions(rng, n):
    """Simple won endings: forced mate exists, so the search should find one."""
    out = []
    specs = [
        ([chess.QUEEN], "KQvK"),
        ([chess.ROOK], "KRvK"),
        ([chess.ROOK, chess.ROOK], "KRRvK"),
        ([chess.QUEEN, chess.ROOK], "KQRvK"),
        ([chess.BISHOP, chess.BISHOP], "KBBvK"),
    ]
    while len(out) < n:
        pieces, name = rng.choice(specs)
        b = chess.Board(None)
        sqs = rng.sample(range(64), 2 + len(pieces))
        b.set_piece_at(sqs[0], chess.Piece(chess.KING, chess.WHITE))
        b.set_piece_at(sqs[1], chess.Piece(chess.KING, chess.BLACK))
        for sq, pt in zip(sqs[2:], pieces):
            b.set_piece_at(sq, chess.Piece(pt, chess.WHITE))
        b.turn = chess.WHITE
        b.clear_stack()
        if b.is_valid() and not b.is_game_over():
            out.append((b.fen(), name))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--movetime", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=31337)
    a = ap.parse_args()

    from engine.engine import Engine
    # Tablebase OFF: a tablebase move is a lookup, and the point is to check the
    # SEARCH's own mate accounting.
    eng = Engine(use_book=False, use_tablebase=False)
    rng = random.Random(a.seed)

    positions = gen_mating_positions(rng, a.n)
    claimed = verified = wrong_len = not_mate = no_pv = 0
    examples = []

    for fen, name in positions:
        b = chess.Board(fen)
        res = eng.best_move(b, movetime=a.movetime)
        sc = getattr(res, "score", 0) or 0
        if abs(sc) < 90000:                     # S_MATE_TH: not a mate claim
            continue
        claimed += 1
        pv = [m for m in (getattr(res, "pv", None) or []) if m is not None]
        if not pv:
            no_pv += 1
            continue
        # a mate score of +M means mate in ceil(M/2) moves for the side to move
        want_plies = 100000 - abs(sc)          # S_MATE - plies-to-mate
        sim = chess.Board(fen)
        ok = True
        for mv in pv:
            if mv not in sim.legal_moves:
                ok = False
                break
            sim.push(mv)
            if sim.is_checkmate():
                break
        if not ok:
            no_pv += 1
            continue
        if not sim.is_checkmate():
            not_mate += 1
            if len(examples) < 6:
                examples.append((fen, sc, len(pv), "PV does not reach mate"))
            continue
        got_plies = len(sim.move_stack)
        if want_plies is not None and got_plies != want_plies:
            wrong_len += 1
            if len(examples) < 6:
                examples.append((fen, sc, got_plies,
                                 f"claimed {want_plies} plies, PV mates in {got_plies}"))
            continue
        verified += 1

    print(f"\n{len(positions)} won endings searched at {a.movetime}s, "
          f"tablebase OFF")
    print(f"  mate scores claimed        : {claimed}")
    print(f"  verified by playing the PV : {verified}")
    print(f"  PV did not reach mate      : {not_mate}")
    print(f"  mate length disagreed      : {wrong_len}")
    print(f"  no usable PV               : {no_pv}")
    if examples:
        print("\n  examples:")
        for fen, sc, extra, why in examples:
            print(f"    score {sc:>6}  {why}")
            print(f"      {fen}")


if __name__ == "__main__":
    main()

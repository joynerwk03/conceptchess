"""Which CONCEPTS talk the search into the wrong move?

The lesson of 2026-08-05, three times over (drawishness, KPK, the king shelter):
**an evaluation error only costs Elo if it changes which move you pick.** Being
more right about a drawn ending, or about a position whose result was never in
doubt, is worth exactly nothing. So stop hunting for positions the evaluation
scores wrongly and hunt for positions where its error *flips the decision*.

Method, which only this engine can run: take the positions where a short search
picks a different move from the long reference search. For each, evaluate the
position after the shallow choice and after the reference choice, and diff the
two breakdowns **concept by concept**. A concept that consistently scores the
wrong move higher than the right one is the concept doing the misleading.

Every other engine's evaluation is one number, so it can tell you a move was
wrong but never which of its own judgements was responsible.

What this does NOT prove: a concept topping the table might be innocent and
merely correlated (a sharp position moves threats *and* king attack together).
It is a place to look, not a verdict -- everything it nominates still has to
clear the decisive-game loss screen and then a gate.

    PYTHONPATH=. .venv/bin/python research/blame.py [--fast 0.1] [--limit N]
"""
import argparse
import collections
import json
import os
import pathlib
import statistics

import chess

ROOT = pathlib.Path(__file__).parent.parent
TRUTH = ROOT / "research" / "data" / "search_truth.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", type=float, default=0.1)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--quiet-only", action="store_true",
                    help="only disagreements where NEITHER move is a capture or "
                         "promotion. The unfiltered table is dominated by "
                         "material -- shallow search grabs a pawn the deep "
                         "search rejects -- which is a horizon effect, not an "
                         "evaluation bias. Filtering it out is what isolates "
                         "positional judgement.")
    a = ap.parse_args()

    os.environ["CC_THREADS"] = "1"
    from engine.engine import Engine
    from engine.evaluation import evaluate_detailed

    truth = json.loads(TRUTH.read_text())["items"]
    if a.limit:
        truth = truth[:a.limit]
    eng = Engine(use_book=False, use_tablebase=False)

    # concept -> list of (score after shallow choice) - (score after deep choice),
    # signed from the mover's point of view. Positive means this concept liked
    # the move that turned out to be wrong.
    blame = collections.defaultdict(list)
    disagreements = 0

    for i, t in enumerate(truth):
        board = chess.Board(t["fen"])
        deep = chess.Move.from_uci(t["move"])
        r = eng.best_move(board.copy(), movetime=a.fast)
        if r.move is None or r.move == deep or deep not in board.legal_moves:
            continue
        if a.quiet_only:
            noisy = (board.is_capture(r.move) or board.is_capture(deep)
                     or r.move.promotion or deep.promotion)
            if noisy:
                continue
        disagreements += 1
        sign = 1 if board.turn == chess.WHITE else -1

        def parts(mv):
            b2 = board.copy()
            b2.push(mv)
            return {c.name: c.score for c in evaluate_detailed(b2).concepts}

        pw, pr = parts(r.move), parts(deep)
        for name in pw:
            blame[name].append(sign * (pw[name] - pr.get(name, 0.0)))
        if (i + 1) % 200 == 0:
            print(f"  [{i+1}/{len(truth)}] {disagreements} disagreements", flush=True)

    print(f"\n{disagreements} positions where the {a.fast}s search differs from "
          f"the reference, of {len(truth)}\n")
    print(f"{'concept':18s} {'mean':>9s} {'median':>9s} {'>0':>7s}   "
          f"reads as")
    print("-" * 78)
    rows = []
    for name, vals in blame.items():
        if not vals:
            continue
        rows.append((statistics.mean(vals), statistics.median(vals),
                     100 * sum(1 for v in vals if v > 0) / len(vals), name))
    for mean, med, pos, name in sorted(rows, key=lambda r: -r[0]):
        verdict = ("OVER-VALUES the wrong move" if mean > 2 else
                   "under-values it" if mean < -2 else "neutral")
        print(f"{name:18s} {mean:+9.1f} {med:+9.1f} {pos:6.0f}%   {verdict}")
    print()
    print("Positive mean = this concept scored the move the short search chose")
    print("HIGHER than the move the long search chose. That is the signature of a")
    print("concept talking the engine into mistakes.")


if __name__ == "__main__":
    main()

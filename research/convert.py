"""Can the engine actually FINISH a won endgame, and how efficiently?

Every strength number in this project comes from games against an opponent, which
measures whether the engine gets INTO good positions. None of them measures
whether it can convert one. William's report -- "very poor endgame technique,
delaying the promotion of the pawn way too long and not finding an efficient
checkmate, although it did eventually find one" -- is invisible to a match gate,
because against a strong opponent those games are still won, just slowly, and
these endings barely occur at all.

So: put the engine in a position, let it play BOTH sides (itself as a defender
playing on), and count the moves. The fifty-move rule is enforced, because a
technique failure that draws a won game is exactly the failure worth catching.

Ground truth comes from the SYZYGY TABLEBASE, not from hand-written expectations.
That matters: the first version of this file asserted that two K+P vs K positions
were "easy wins" and reported the engine as failing to convert them. The
tablebase says both are theoretical DRAWS -- the engine was right and the
benchmark was wrong. A benchmark that can indict correct play is worse than none.

Usage:
  python -m research.convert                    # the default suite
  python -m research.convert --movetime 1.0
"""

import argparse

import chess

from engine import tablebase as tb
from engine.engine import Engine

SUITE = [
    ("KQ vs K   (corner)",     "8/8/8/8/8/2k5/8/K2Q4 w - - 0 1"),
    ("KQ vs K   (centre)",     "8/8/4k3/8/8/8/2Q5/4K3 w - - 0 1"),
    ("KR vs K   (centre)",     "8/8/4k3/8/8/8/8/R3K3 w - - 0 1"),
    ("KR vs K   (edge)",       "7k/8/8/8/8/8/8/R3K3 w - - 0 1"),
    ("KPvK      (drawn)",      "8/8/8/4k3/8/4P3/4K3/8 w - - 0 1"),
    ("KPvK      (drawn, opp)", "8/8/4k3/8/4P3/4K3/8/8 w - - 0 1"),
    ("KBB vs K",               "8/8/4k3/8/8/8/2BB4/4K3 w - - 0 1"),
    ("KQ vs KR",               "8/8/4k3/7r/8/8/3Q4/4K3 w - - 0 1"),
    # --- five men: newly covered once the 3-4-5 Syzygy set was completed.
    # Each verified legal, five-man and tablebase-covered before being added.
    ("KRP vs KR             ", "8/8/8/8/1k6/8/1P1K4/1R4r1 w - - 0 1"),
    ("KBN vs KP             ", "8/8/8/8/4k3/4p3/3BN3/4K3 w - - 0 1"),
    ("KQ vs KRP             ", "8/8/8/8/8/1k6/1p1r4/1K5Q w - - 0 1"),
    ("KRB vs KR             ", "8/8/4k3/7r/8/8/3B1R2/4K3 w - - 0 1"),
    ("KPP vs KP             ", "8/8/8/8/2k5/4p3/1PP1K3/8 w - - 0 1"),
    ("KQ vs KBN             ", "8/8/4k3/8/5n2/4b3/3Q4/4K3 w - - 0 1"),
    ("KRP vs KB             ", "8/8/4k3/8/4b3/8/3P4/R3K3 w - - 0 1"),
]

MAX_PLIES = 400


def truth(fen):
    """(expected outcome, dtz) from the tablebase, or (None, None)."""
    got = tb.probe(chess.Board(fen))
    if got is None:
        return None, None
    wdl, dtz = got
    return ("win" if wdl > 0 else "draw" if wdl == 0 else "loss"), abs(dtz)


def play_out(engine, fen, movetime):
    board = chess.Board(fen)
    strong = board.turn
    plies = 0
    while plies < MAX_PLIES and not board.is_game_over(claim_draw=True):
        res = engine.best_move(board, movetime=movetime)
        if res.move is None:
            break
        board.push(res.move)
        plies += 1
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return "unfinished", plies
    if outcome.winner == strong:
        return "win", plies
    if outcome.winner is None:
        return f"draw ({outcome.termination.name.lower()})", plies
    return "LOSS", plies


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--movetime", type=float, default=0.5)
    args = p.parse_args()

    for name, fen in SUITE:
        assert chess.Board(fen).is_valid(), f"illegal suite position: {name}"

    if not tb.available():
        print("NOTE: no tablebase found, so results are scored against nothing.")
        print("      set CC_SYZYGY_PATH or install to ~/syzygy345\n")

    engine = Engine(use_book=False)
    print(f"endgame conversion, {args.movetime}s/move, engine plays BOTH sides\n")
    print(f"{'position':<24} {'truth':<6} {'dtz':>4}  {'played':<26} {'plies':>6}  verdict")
    print("-" * 84)

    correct = 0
    for name, fen in SUITE:
        want, dtz = truth(fen)
        got, plies = play_out(engine, fen, args.movetime)
        got_kind = got.split()[0]
        ok = (want is None) or (got_kind == want)
        correct += ok
        verdict = "ok" if ok else ("FAILED TO CONVERT" if want == "win" else "WRONG")
        print(f"{name:<24} {str(want):<6} {str(dtz):>4}  {got:<26} {plies:>6}  {verdict}")
    print("-" * 84)
    print(f"{correct}/{len(SUITE)} positions reached their theoretical result")


if __name__ == "__main__":
    main()

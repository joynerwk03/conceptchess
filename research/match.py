"""UCI-vs-UCI match harness with Elo estimate.

The primary strength gate for the research loop: play the current engine
against Stockfish (strength-limited) or against a baseline version of itself
(checked out in a git worktree).

Usage:
  # vs strength-limited Stockfish (min Elo 1320)
  python -m research.match --games 20 --movetime 0.5 --opponent stockfish:1400

  # vs a baseline revision of this engine:
  #   git worktree add /tmp/ccbase <rev>
  python -m research.match --games 20 --movetime 0.5 \
      --opponent "cmd:python -m engine.uci" --opponent-cwd /tmp/ccbase
"""

import argparse
import math
import shutil
import sys
from pathlib import Path

import chess
import chess.engine

ROOT = Path(__file__).parent.parent

# Short, balanced opening lines for variety (UCI moves).
OPENINGS = [
    ["e2e4", "e7e5"],
    ["e2e4", "c7c5"],
    ["e2e4", "e7e6"],
    ["d2d4", "d7d5"],
    ["d2d4", "g8f6"],
    ["c2c4", "e7e5"],
    ["g1f3", "d7d5"],
    ["e2e4", "c7c6"],
    ["d2d4", "f7f5"],
    ["c2c4", "c7c5"],
]


def open_ours():
    return chess.engine.SimpleEngine.popen_uci(
        [sys.executable, "-m", "engine.uci"], cwd=ROOT)


def open_opponent(spec, cwd):
    if spec.startswith("stockfish:"):
        elo = int(spec.split(":")[1])
        sf_path = shutil.which("stockfish")
        if not sf_path:
            sys.exit("stockfish not found on PATH")
        sf = chess.engine.SimpleEngine.popen_uci(sf_path)
        sf.configure({"UCI_LimitStrength": True, "UCI_Elo": max(1320, elo)})
        return sf
    if spec.startswith("cmd:"):
        cmd = spec[4:].split()
        return chess.engine.SimpleEngine.popen_uci(cmd, cwd=cwd or ROOT)
    sys.exit(f"bad opponent spec: {spec}")


def play_game(white, black, opening, movetime, max_moves=250):
    if isinstance(opening, str):
        board = chess.Board(opening)      # EPD/FEN start (unbalanced book)
    else:
        board = chess.Board()
        for uci in opening:
            board.push(chess.Move.from_uci(uci))
    limit = chess.engine.Limit(time=movetime)
    while not board.is_game_over(claim_draw=True) and board.fullmove_number < max_moves:
        engine = white if board.turn == chess.WHITE else black
        result = engine.play(board, limit)
        if result.move is None:
            break
        board.push(result.move)
    outcome = board.outcome(claim_draw=True)
    if outcome is None or outcome.winner is None:
        return 0.5, board
    return (1.0 if outcome.winner == chess.WHITE else 0.0), board


def elo_estimate(score, n):
    """Elo difference and ~95% interval from match score."""
    if n == 0:
        return 0, 0
    p = min(max(score / n, 1e-3), 1 - 1e-3)
    elo = -400 * math.log10(1 / p - 1)
    # crude standard error on p -> elo interval
    se = math.sqrt(p * (1 - p) / n)
    lo = -400 * math.log10(1 / min(max(p - 1.96 * se, 1e-3), 1 - 1e-3) - 1)
    hi = -400 * math.log10(1 / min(max(p + 1.96 * se, 1e-3), 1 - 1e-3) - 1)
    return elo, (lo, hi)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--movetime", type=float, default=0.5)
    p.add_argument("--opponent", default="stockfish:1400")
    p.add_argument("--opponent-cwd", default=None)
    p.add_argument("--opening-offset", type=int, default=0,
                   help="start at this index in the opening list (for batched matches)")
    p.add_argument("--book", default=None,
                   help="EPD file of unbalanced opening positions (e.g. UHO): each "
                        "line's FEN is played twice, both colors, replacing the "
                        "built-in balanced opening list. Cuts the draw rate so "
                        "gates discriminate better at high strength.")
    p.add_argument("--pgn-out", default=None, help="optional PGN dump for analysis")
    p.add_argument("--sprt", action="store_true",
                   help="stop early via SPRT (H0 elo=0 vs H1 elo=+35)")
    p.add_argument("--sprt-elo1", type=float, default=35.0)
    args = p.parse_args()

    sprt = None
    if args.sprt:
        from research.sprt import SPRT
        sprt = SPRT(elo0=0, elo1=args.sprt_elo1)

    openings = OPENINGS
    if args.book:
        lines = [ln.strip() for ln in Path(args.book).read_text().splitlines() if ln.strip()]
        # EPD lines may carry opcodes after the 4 FEN fields; python-chess
        # Board() accepts 4-field FENs, so keep just those.
        openings = [" ".join(ln.split()[:4]) for ln in lines]
        print(f"book: {len(openings)} unbalanced openings from {args.book}")

    wins = draws = losses = 0
    pgns = []
    for g in range(args.games):
        ours = open_ours()
        opp = open_opponent(args.opponent, args.opponent_cwd)
        try:
            opening = openings[(args.opening_offset + g // 2) % len(openings)]
            we_are_white = g % 2 == 0
            white, black = (ours, opp) if we_are_white else (opp, ours)
            white_score, board = play_game(white, black, opening, args.movetime)
            our_score = white_score if we_are_white else 1 - white_score
            if our_score == 1:
                wins += 1
            elif our_score == 0:
                losses += 1
            else:
                draws += 1
            res = {1.0: "1-0", 0.0: "0-1", 0.5: "1/2-1/2"}[white_score]
            print(f"game {g + 1:2d}: {'W' if we_are_white else 'B'} "
                  f"{res:<7} (us: {'win' if our_score == 1 else 'loss' if our_score == 0 else 'draw'})"
                  f"  [{wins}+{draws}={losses}-]")
            if args.pgn_out:
                import chess.pgn
                game = chess.pgn.Game.from_board(board)
                game.headers["White"] = "ConceptChess" if we_are_white else args.opponent
                game.headers["Black"] = args.opponent if we_are_white else "ConceptChess"
                game.headers["Result"] = res
                pgns.append(str(game))
        finally:
            ours.quit()
            opp.quit()
        if sprt is not None:
            sprt.record(our_score)
            verdict = sprt.status()
            if verdict:
                print(f"SPRT stop after {g + 1} games: "
                      f"{'H1 (better)' if verdict == 'H1' else 'H0 (not better)'}")
                break

    n = wins + draws + losses
    score = wins + 0.5 * draws
    elo, ci = elo_estimate(score, n)
    print(f"\nresult vs {args.opponent}: +{wins} ={draws} -{losses}  "
          f"({100 * score / n:.0f}%)")
    print(f"elo diff: {elo:+.0f}  (95% ~ {ci[0]:+.0f}..{ci[1]:+.0f})")
    if args.pgn_out and pgns:
        Path(args.pgn_out).write_text("\n\n".join(pgns) + "\n")
        print(f"pgn written to {args.pgn_out}")


if __name__ == "__main__":
    main()

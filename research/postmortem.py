"""Where does the Elo actually leak? Phase-resolved post-mortem of real games.

Every strength idea for the last two sessions was a guess at a technique, and
seven straight came back neutral. This looks at the problem the other way round:
take games the engine actually played against Stockfish, have Stockfish score
every position, and ask which PHASE of the game we bleed centipawns in.

The essential trick is the CONTROL. "We lose 40cp/move in endgames" means
nothing on its own -- endgame positions are sharper, and the metric is noisier
there. What matters is our loss *minus the opponent's loss on the same games*.
Stockfish plays both sides of the same positions, so its per-phase profile is a
built-in baseline, and the phase where our EXCESS loss is largest is where the
strength is actually going.

Method: analyse every position of every game once at fixed depth, from White's
point of view. A player's centipawn loss on their move is then just the drop in
score across that move. One analysis per position rather than two per move.

Usage:
  # produce the games first
  python -m research.match --games 200 --movetime 0.3 --concurrency 8 \
      --opponent stockfish:2800 --book research/books/uho_1000.epd \
      --pgn-out research/data/vs2800.pgn
  python -m research.postmortem research/data/vs2800.pgn --depth 14 --workers 8
"""

import argparse
import concurrent.futures as cf
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import chess
import chess.engine
import chess.pgn

# Non-pawn material (both sides) below this = endgame; the opening is simply the
# first OPENING_MOVES full moves. Deliberately crude: the point is a stable
# 3-way split, not a phase model.
PIECE_VALUE = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
ENDGAME_MATERIAL = 13
OPENING_MOVES = 12
MATE_SCORE = 10000
CLIP = 1000          # ignore swings beyond this: already-decided positions add noise


def phase_of(board):
    material = sum(PIECE_VALUE[p] * len(board.pieces(p, c))
                   for p in PIECE_VALUE for c in (chess.WHITE, chess.BLACK))
    if material <= ENDGAME_MATERIAL:
        return "endgame"
    if board.fullmove_number <= OPENING_MOVES:
        return "opening"
    return "middlegame"


def analyse_game(args):
    """-> (per-move rows, game summary) for one game.

    rows: [(phase, mover_is_us, cp_loss), ...]
    summary: (our_result, worst_loss, worst_phase) -- the worst single move is
    what actually decides games, and mean cp/move dilutes it away.
    """
    sf_path, depth, us_is_white, moves, start_fen, result = args
    engine = chess.engine.SimpleEngine.popen_uci(sf_path)
    try:
        board = chess.Board(start_fen)
        scores, phases, movers = [], [], []
        positions = [board.copy()]
        for mv in moves:
            board.push(mv)
            positions.append(board.copy())
        for i, pos in enumerate(positions):
            # Append phase/mover FIRST so these stay index-aligned with `scores`
            # even when a position is terminal (a claimable threefold can show up
            # mid-list) and gets no score.
            if i < len(moves):
                phases.append(phase_of(pos))
                movers.append(pos.turn == chess.WHITE)
            if pos.is_game_over(claim_draw=True):
                scores.append(None)
                continue
            info = engine.analyse(pos, chess.engine.Limit(depth=depth))
            score = info.get("score")
            scores.append(None if score is None
                          else score.white().score(mate_score=MATE_SCORE))
        out = []
        for i in range(len(moves)):
            a, b = scores[i], scores[i + 1]
            if a is None or b is None:
                continue
            mover_white = movers[i]
            # Loss = drop in the mover's own favour across their move.
            loss = (a - b) if mover_white else (b - a)
            if loss < 0:
                loss = 0                       # SF at fixed depth is not perfect
            if loss > CLIP:
                continue
            out.append((phases[i], mover_white == us_is_white, loss))
        worst, worst_phase = 0, None
        for phase, is_us, loss in out:
            if is_us and loss > worst:
                worst, worst_phase = loss, phase
        if result == "1-0":
            our_result = "win" if us_is_white else "loss"
        elif result == "0-1":
            our_result = "loss" if us_is_white else "win"
        else:
            our_result = "draw"
        return out, (our_result, worst, worst_phase)
    finally:
        engine.quit()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("pgn")
    p.add_argument("--depth", type=int, default=14,
                   help="Stockfish depth per position (14 is a good speed/signal trade)")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--max-games", type=int, default=0, help="0 = all")
    p.add_argument("--us", default="ConceptChess",
                   help="substring identifying our engine in the PGN headers")
    args = p.parse_args()

    sf_path = shutil.which("stockfish")
    if not sf_path:
        sys.exit("stockfish not found on PATH")

    jobs = []
    with open(args.pgn) as fh:
        while True:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            white = game.headers.get("White", "")
            black = game.headers.get("Black", "")
            if args.us in white:
                us_is_white = True
            elif args.us in black:
                us_is_white = False
            else:
                continue
            moves = list(game.mainline_moves())
            if not moves:
                continue
            start_fen = game.headers.get("FEN", chess.STARTING_FEN)
            jobs.append((sf_path, args.depth, us_is_white, moves, start_fen,
                         game.headers.get("Result", "*")))
            if args.max_games and len(jobs) >= args.max_games:
                break

    if not jobs:
        sys.exit(f"no games in {args.pgn} with '{args.us}' as a player")
    print(f"{len(jobs)} games, Stockfish depth {args.depth}, {args.workers} workers",
          flush=True)

    # sums[phase][is_us] = [total_loss, move_count, blunders>=100, blunders>=300]
    sums = defaultdict(lambda: defaultdict(lambda: [0, 0, 0, 0]))
    # worst-move-in-a-lost-game: [count, total] per phase, by our result
    worst_by_result = defaultdict(lambda: defaultdict(int))
    worst_cp = defaultdict(list)
    done = 0
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for res, summary in ex.map(analyse_game, jobs):
            our_result, worst, worst_phase = summary
            if worst_phase:
                worst_by_result[our_result][worst_phase] += 1
                worst_cp[our_result].append(worst)
            for phase, is_us, loss in res:
                cell = sums[phase][is_us]
                cell[0] += loss
                cell[1] += 1
                cell[2] += loss >= 100
                cell[3] += loss >= 300
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{len(jobs)} games", flush=True)

    print("\n" + "=" * 78)
    print(f"{'phase':<12} {'side':<12} {'moves':>7} {'cp/move':>9} "
          f"{'>=100cp':>9} {'>=300cp':>9}")
    print("-" * 78)
    excess = {}
    for phase in ("opening", "middlegame", "endgame"):
        if phase not in sums:
            continue
        row = {}
        for is_us, label in ((True, "ConceptChess"), (False, "Stockfish")):
            total, n, b100, b300 = sums[phase][is_us]
            if not n:
                continue
            row[is_us] = total / n
            print(f"{phase:<12} {label:<12} {n:>7} {total / n:>9.1f} "
                  f"{100 * b100 / n:>8.1f}% {100 * b300 / n:>8.1f}%")
        if True in row and False in row:
            excess[phase] = row[True] - row[False]
        print("-" * 78)
    print("=" * 78)
    print("\nEXCESS centipawn loss vs the same opponent on the same games")
    print("(higher = more strength leaking in that phase):")
    for phase, val in sorted(excess.items(), key=lambda kv: -kv[1]):
        print(f"  {phase:<12} {val:+7.1f} cp/move")
    if excess:
        worst = max(excess, key=excess.get)
        print(f"\n-> most excess loss: {worst}")

    # Games are decided by the worst move, not the average one. If lost games
    # concentrate their worst move in one phase far more than drawn/won games
    # do, that phase is where the points are actually going.
    print("\n" + "=" * 78)
    print("WHERE OUR WORST MOVE OF THE GAME HAPPENS, by our result")
    print(f"{'result':<8} {'games':>6} {'mean worst':>11}   phase distribution")
    print("-" * 78)
    for res_name in ("loss", "draw", "win"):
        losses = worst_cp.get(res_name)
        if not losses:
            continue
        dist = worst_by_result[res_name]
        total = sum(dist.values())
        parts = "  ".join(
            f"{ph}: {100 * dist.get(ph, 0) / total:.0f}%"
            for ph in ("opening", "middlegame", "endgame") if dist.get(ph))
        print(f"{res_name:<8} {len(losses):>6} {sum(losses) / len(losses):>10.0f}cp"
              f"   {parts}")
    print("=" * 78)


if __name__ == "__main__":
    main()

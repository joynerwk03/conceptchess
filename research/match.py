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
import concurrent.futures as cf
import math
import os
import shutil
import sys
import threading
from pathlib import Path

# Keep strength gates clean single-thread by default: the UCI engine now plays at
# full-width SMP by default, but SMP-vs-SMP on one machine contends for cores and
# muddies version-vs-version comparisons. Both spawned engines inherit this env.
# Set CC_THREADS explicitly before invoking to measure at N threads on purpose.
os.environ.setdefault("CC_THREADS", "1")

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


def _start_board(opening):
    if isinstance(opening, str):
        return chess.Board(opening)       # EPD/FEN start (unbalanced book)
    board = chess.Board()
    for uci in opening:
        board.push(chess.Move.from_uci(uci))
    return board


def play_game(white, black, opening, white_time, black_time, max_moves=250):
    board = _start_board(opening)
    wl = chess.engine.Limit(time=white_time)
    bl = chess.engine.Limit(time=black_time)
    while not board.is_game_over(claim_draw=True) and board.fullmove_number < max_moves:
        engine, limit = (white, wl) if board.turn == chess.WHITE else (black, bl)
        result = engine.play(board, limit)
        if result.move is None:
            break
        board.push(result.move)
    outcome = board.outcome(claim_draw=True)
    if outcome is None or outcome.winner is None:
        return 0.5, board
    return (1.0 if outcome.winner == chess.WHITE else 0.0), board


def play_game_clock(white, black, opening, clock, inc, max_moves=250):
    """Game-clock play: each side gets `clock` seconds + `inc`/move. The harness
    tracks each clock, decrements by measured wall time, and flags loss on time.
    This is the only regime where adaptive time management can pay — saving
    time on easy moves to spend on hard ones."""
    import time as _time
    board = _start_board(opening)
    wc = bc = clock
    while not board.is_game_over(claim_draw=True) and board.fullmove_number < max_moves:
        white_to_move = board.turn == chess.WHITE
        engine = white if white_to_move else black
        limit = chess.engine.Limit(white_clock=wc, black_clock=bc,
                                   white_inc=inc, black_inc=inc)
        t0 = _time.perf_counter()
        try:
            result = engine.play(board, limit)
        except Exception:
            # engine crashed → loss for the side to move
            return (0.0 if white_to_move else 1.0), board
        elapsed = _time.perf_counter() - t0
        if white_to_move:
            wc = wc - elapsed + inc
            if wc < 0:
                return 0.0, board            # White flagged
        else:
            bc = bc - elapsed + inc
            if bc < 0:
                return 1.0, board            # Black flagged
        if result.move is None:
            break
        board.push(result.move)
    outcome = board.outcome(claim_draw=True)
    if outcome is None or outcome.winner is None:
        return 0.5, board
    return (1.0 if outcome.winner == chess.WHITE else 0.0), board


def _elo(p):
    """Score fraction -> Elo difference."""
    p = min(max(p, 1e-4), 1 - 1e-4)
    return -400 * math.log10(1 / p - 1)


def elo_estimate(score, n):
    """Elo + 95% CI from a win/draw/loss sample (TRINOMIAL).

    The old version used se = sqrt(p(1-p)/n), the standard error of a COIN FLIP.
    A chess game scores 0/0.5/1, and draws sit at the mean, so the true per-game
    variance is E[(x-p)^2] over the actual w/d/l counts -- always smaller than
    p(1-p) once there are draws (at a 40% draw rate it overstates the CI by
    ~25%). We compute the real thing. Prefer the pentanomial estimate below when
    the games come in colour-swapped pairs; this stays for unpaired samples.
    """
    if n == 0:
        return 0.0, (0.0, 0.0)
    p = score / n
    return _elo_ci_from_var(p, p * (1 - p), n)


def _elo_ci_from_var(p, var, n):
    se = math.sqrt(max(var, 0.0) / n) if n else 0.0
    return _elo(p), (_elo(p - 1.96 * se), _elo(p + 1.96 * se))


def trinomial_elo(w, d, l):
    """Elo + 95% CI using the true per-game score variance."""
    n = w + d + l
    if n == 0:
        return 0.0, (0.0, 0.0)
    p = (w + 0.5 * d) / n
    var = (w * (1 - p) ** 2 + d * (0.5 - p) ** 2 + l * (0 - p) ** 2) / n
    return _elo_ci_from_var(p, var, n)


def pentanomial_elo(pair_scores):
    """Elo + 95% CI from PAIRED games (the statistically correct estimator here).

    The harness plays every opening twice with colours swapped, so games are not
    independent: a lopsided opening tends to produce a win and a loss (or two
    draws) regardless of engine strength. Scoring the PAIR (0, 0.5, 1, 1.5, 2)
    cancels that shared opening bias, so the variance reflects only the strength
    difference. On an unbalanced book this typically shrinks the interval
    materially versus treating the games as independent -- which is exactly the
    resolution that was missing when +20-30 Elo effects kept coming back
    "inconclusive".
    """
    m = len(pair_scores)
    if m < 2:
        return None
    mean_pair = sum(pair_scores) / m
    p = mean_pair / 2.0
    var = sum((s - mean_pair) ** 2 for s in pair_scores) / (m - 1)
    se_p = math.sqrt(var / m) / 2.0
    return _elo(p), (_elo(p - 1.96 * se_p), _elo(p + 1.96 * se_p)), p, m


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--games", type=int, default=10)
    p.add_argument("--movetime", type=float, default=0.5)
    p.add_argument("--opp-movetime", type=float, default=None,
                   help="opponent's per-move seconds (default: same as --movetime). "
                        "Set different for time-odds / time-scaling tests.")
    p.add_argument("--opponent", default="stockfish:1400")
    p.add_argument("--opponent-cwd", default=None)
    p.add_argument("--concurrency", type=int, default=1,
                   help="play this many games at once (default 1 = old behaviour). "
                        "Each game is an independent pair of engine processes. Keep "
                        "at or below the number of PERFORMANCE cores: at fixed "
                        "movetime an engine on a slow core just searches fewer "
                        "nodes, so over-subscribing adds variance. Validate any "
                        "value with the A-vs-identical-A check (must score ~50%).")
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
    p.add_argument("--clock", type=float, default=None,
                   help="game-clock mode: seconds per side (e.g. 10). Enables "
                        "adaptive time management; overrides --movetime.")
    p.add_argument("--inc", type=float, default=0.1,
                   help="increment per move (seconds) in --clock mode")
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

    def play_one(g):
        """Play game #g start-to-finish with its own engine pair (thread-safe)."""
        opening = openings[(args.opening_offset + g // 2) % len(openings)]
        we_are_white = g % 2 == 0
        # Alternate which side is spawned first. Otherwise "ours" is always the
        # first process created, and if the OS were to favour first-spawned
        # processes for the fast (performance) cores, that would be a systematic
        # bias in our favour on a big.LITTLE machine. Alternating launders it.
        if g % 2 == 0:
            ours = open_ours()
            opp = open_opponent(args.opponent, args.opponent_cwd)
        else:
            opp = open_opponent(args.opponent, args.opponent_cwd)
            ours = open_ours()
        try:
            white, black = (ours, opp) if we_are_white else (opp, ours)
            if args.clock is not None:
                white_score, board = play_game_clock(white, black, opening,
                                                     args.clock, args.inc)
            else:
                our_t = args.movetime
                opp_t = args.opp_movetime if args.opp_movetime is not None else args.movetime
                white_time, black_time = (our_t, opp_t) if we_are_white else (opp_t, our_t)
                white_score, board = play_game(white, black, opening, white_time, black_time)
        finally:
            for e in (ours, opp):
                try:
                    e.quit()
                except Exception:
                    pass
        return g, white_score, board, we_are_white

    wins = draws = losses = 0
    pgns = []
    scores = {}                       # game index -> our score (for pair stats)
    lock = threading.Lock()
    stop = threading.Event()
    done = 0

    def record(res):
        nonlocal wins, draws, losses, done
        g, white_score, board, we_are_white = res
        our_score = white_score if we_are_white else 1 - white_score
        with lock:
            scores[g] = our_score
            if our_score == 1:
                wins += 1
            elif our_score == 0:
                losses += 1
            else:
                draws += 1
            done += 1
            res_s = {1.0: "1-0", 0.0: "0-1", 0.5: "1/2-1/2"}[white_score]
            outcome = "win" if our_score == 1 else "loss" if our_score == 0 else "draw"
            print(f"game {g + 1:3d}: {'W' if we_are_white else 'B'} {res_s:<7} "
                  f"(us: {outcome})  [{wins}+{draws}={losses}-]  ({done}/{args.games})",
                  flush=True)
            if args.pgn_out:
                import chess.pgn
                game = chess.pgn.Game.from_board(board)
                game.headers["White"] = "ConceptChess" if we_are_white else args.opponent
                game.headers["Black"] = args.opponent if we_are_white else "ConceptChess"
                game.headers["Result"] = res_s
                pgns.append(str(game))
            if sprt is not None:
                sprt.record(our_score)
                verdict = sprt.status()
                if verdict and not stop.is_set():
                    stop.set()
                    print(f"SPRT stop after {done} games: "
                          f"{'H1 (better)' if verdict == 'H1' else 'H0 (not better)'}",
                          flush=True)

    if args.concurrency <= 1:
        for g in range(args.games):
            if stop.is_set():
                break
            record(play_one(g))
    else:
        # Games are fully independent processes, so they parallelise cleanly.
        # Keep concurrency <= the performance-core count: at fixed MOVETIME an
        # engine squeezed onto a slow core simply searches fewer nodes, and if
        # the two sides of one game land on different core classes that game is
        # skewed. Colour/spawn alternation makes the effect zero-mean rather
        # than systematic, but over-subscribing still inflates variance.
        with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futures = {}
            pending = iter(range(args.games))
            for _ in range(min(args.concurrency, args.games)):
                g = next(pending, None)
                if g is not None:
                    futures[ex.submit(play_one, g)] = g
            while futures:
                for fut in cf.as_completed(list(futures)):
                    del futures[fut]
                    try:
                        record(fut.result())
                    except Exception as e:      # one bad game must not kill the match
                        print(f"  game failed: {type(e).__name__}: {e}", flush=True)
                    if not stop.is_set():
                        g = next(pending, None)
                        if g is not None:
                            futures[ex.submit(play_one, g)] = g
                    break                        # re-enter as_completed with the new set
            if stop.is_set():
                for fut in futures:
                    fut.cancel()

    n = wins + draws + losses
    if n == 0:
        print("no games completed")
        return
    score = wins + 0.5 * draws
    _tc = f"{args.movetime}s"
    if args.opp_movetime is not None and args.opp_movetime != args.movetime:
        _tc = f"us {args.movetime}s vs opp {args.opp_movetime}s"
    conc = f", concurrency {args.concurrency}" if args.concurrency > 1 else ""
    print(f"\nresult vs {args.opponent} [{_tc}{conc}]: +{wins} ={draws} -{losses}  "
          f"({100 * score / n:.1f}%)")

    elo, ci = trinomial_elo(wins, draws, losses)
    print(f"elo diff: {elo:+.0f}  (95% ~ {ci[0]:+.0f}..{ci[1]:+.0f})   [per-game]")

    # Pair the colour-swapped games (2k, 2k+1) that both finished.
    pairs = [scores[2 * k] + scores[2 * k + 1]
             for k in range(args.games // 2)
             if 2 * k in scores and 2 * k + 1 in scores]
    pent = pentanomial_elo(pairs)
    if pent:
        pelo, pci, pp, m = pent
        print(f"elo diff: {pelo:+.0f}  (95% ~ {pci[0]:+.0f}..{pci[1]:+.0f})   "
              f"[paired, {m} pairs, {100 * pp:.1f}%]  <-- use this one")
    if args.pgn_out and pgns:
        Path(args.pgn_out).write_text("\n\n".join(pgns) + "\n")
        print(f"pgn written to {args.pgn_out}")


if __name__ == "__main__":
    main()

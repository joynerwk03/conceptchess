"""Are our real mistakes SEARCH failures or EVAL failures?

The s26 post-mortem located where strength leaks (opening/middlegame, not
endgame) but not why. This settles that on the engine's own real mistakes rather
than on sampled positions: take the moves where it actually blundered against
Stockfish in played games, re-search each at the gate time control and at 10x
that time, and ask whether more thinking changes its mind.

  * the blunder goes away with more time  -> SEARCH-limited. We could see it, we
    just ran out of depth. The fix is speed/pruning, and eval work is wasted.
  * the blunder survives more time        -> EVAL-limited. We genuinely prefer
    the worse move. The fix is a concept, and for those the breakdown of our
    move vs Stockfish's names which concept is mis-scoring.

That second class is exactly the interpretable eval work this project exists
for, and this is the only honest way to find it -- guessing concepts has gone
0-for-4 (pawn storm, threat-by-push, bad bishop, pins).

Classification uses centipawn loss, not move equality: two different moves can
both be fine, and "changed its mind" is not the same as "fixed it".

It also keys off the LONG search only, and that is deliberate. The first version
of this tool compared a fresh SHORT search against the game move and put 65% of
blunders in a "not reproduced" bucket -- which turned out to measure nothing but
the engine's own instability: because the search stops on wall clock, two 0.3s
searches of the same position pick different moves 18% of the time, and a full
game replay reproduces only 71% of its own moves. A classifier resting on the
short search is therefore mostly reading timing jitter. Whether 10x thinking
time fixes the mistake is a stable, meaningful question; the short search is
reported alongside as context only.

Usage:
  python -m research.blunders --pgn research/data/vs2800.pgn \\
      --out research/suites/blunders_v1.epd --min-loss 150
  python -m research.blunders --epd research/suites/blunders_v1.epd   # reuse
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

from research.postmortem import CLIP, MATE_SCORE, phase_of

ROOT = Path(__file__).parent.parent


# --------------------------------------------------------------------------
# pass 1: mine real blunders out of played games
# --------------------------------------------------------------------------

def _scan_game(job):
    sf_path, depth, us_is_white, moves, start_fen, min_loss = job
    engine = chess.engine.SimpleEngine.popen_uci(sf_path)
    found = []
    try:
        board = chess.Board(start_fen)
        # One analysis per position (not two per move): a move's loss is just
        # the drop in score across it.
        rows = []
        for mv in moves:
            if board.is_game_over(claim_draw=True):
                break
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            score = info.get("score")
            pv = info.get("pv")
            rows.append((board.fen(), phase_of(board),
                         (board.turn == chess.WHITE) == us_is_white,
                         None if score is None else score.white().score(mate_score=MATE_SCORE),
                         pv[0] if pv else None, mv))
            board.push(mv)
        # final position's score closes the last move
        tail = None
        if not board.is_game_over(claim_draw=True):
            info = engine.analyse(board, chess.engine.Limit(depth=depth))
            s = info.get("score")
            tail = None if s is None else s.white().score(mate_score=MATE_SCORE)
        for i, (fen, phase, is_ours, sc, best, played) in enumerate(rows):
            nxt = rows[i + 1][3] if i + 1 < len(rows) else tail
            if not is_ours or sc is None or nxt is None or best is None:
                continue
            loss = (sc - nxt) if us_is_white else (nxt - sc)
            if min_loss <= loss <= CLIP and played != best:
                found.append({"fen": fen, "phase": phase, "loss": int(loss),
                              "played": played.uci(), "best": best.uci()})
        return found
    finally:
        engine.quit()


def mine(pgn_path, sf_path, depth, workers, min_loss, us_tag, max_games):
    jobs = []
    with open(pgn_path) as fh:
        while True:
            game = chess.pgn.read_game(fh)
            if game is None:
                break
            white, black = game.headers.get("White", ""), game.headers.get("Black", "")
            if us_tag in white:
                us_is_white = True
            elif us_tag in black:
                us_is_white = False
            else:
                continue
            moves = list(game.mainline_moves())
            if moves:
                jobs.append((sf_path, depth, us_is_white, moves,
                             game.headers.get("FEN", chess.STARTING_FEN), min_loss))
            if max_games and len(jobs) >= max_games:
                break
    print(f"scanning {len(jobs)} games at depth {depth} for losses >= {min_loss}cp",
          flush=True)
    out, done = [], 0
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for found in ex.map(_scan_game, jobs):
            out.extend(found)
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(jobs)} games, {len(out)} blunders", flush=True)
    return out


def write_epd(rows, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for r in rows:
        board = chess.Board(r["fen"])
        best = board.san(chess.Move.from_uci(r["best"]))
        played = board.san(chess.Move.from_uci(r["played"]))
        lines.append(f'{board.epd()} bm {best}; c0 "played {played} loss '
                     f'{r["loss"]}cp phase {r["phase"]}";')
    Path(path).write_text("\n".join(lines) + "\n")
    print(f"wrote {len(lines)} positions to {path}")


def read_epd(path):
    rows = []
    for ln in Path(path).read_text().splitlines():
        if not ln.strip():
            continue
        board, ops = chess.Board().from_epd(ln)
        bm = ops.get("bm")
        bm = bm[0] if isinstance(bm, list) else bm
        if bm is None:
            continue
        c0 = ops.get("c0", "")
        phase = "unknown"
        loss = 0
        parts = str(c0).split()
        if "phase" in parts:
            phase = parts[parts.index("phase") + 1]
        for p in parts:
            if p.endswith("cp"):
                try:
                    loss = int(p[:-2])
                except ValueError:
                    pass
        rows.append({"fen": board.fen(), "best": bm.uci(), "phase": phase,
                     "loss": loss, "played": None})
    return rows


# --------------------------------------------------------------------------
# pass 2: does more thinking fix it?
# --------------------------------------------------------------------------

def classify(rows, sf_path, depth, t_short, t_long, min_loss, max_positions):
    from engine.engine import Engine
    from engine.evaluation import evaluate_detailed

    engine = Engine(use_book=False)
    sf = chess.engine.SimpleEngine.popen_uci(sf_path)
    counts = defaultdict(int)
    by_phase = defaultdict(lambda: defaultdict(int))
    culprit_mass = defaultdict(float)
    culprit_count = defaultdict(int)
    examples = []

    def loss_of(board, move, base):
        """cp the side to move gives up by playing `move`, vs `base` (best score)."""
        b = board.copy()
        b.push(move)
        if b.is_game_over(claim_draw=True):
            out = b.outcome(claim_draw=True)
            if out is None or out.winner is None:
                after = 0
            else:
                after = MATE_SCORE if out.winner == board.turn else -MATE_SCORE
        else:
            info = sf.analyse(b, chess.engine.Limit(depth=depth))
            sc = info.get("score")
            if sc is None:
                return None
            after = sc.pov(board.turn).score(mate_score=MATE_SCORE)
        if after is None:
            return None
        return base - after

    try:
        for i, r in enumerate(rows[:max_positions]):
            board = chess.Board(r["fen"])
            info = sf.analyse(board, chess.engine.Limit(depth=depth))
            sc = info.get("score")
            if sc is None:
                continue
            base = sc.pov(board.turn).score(mate_score=MATE_SCORE)
            if base is None:
                continue
            # Short search FIRST: the long one may reuse its TT entries, which
            # only helps the long search and cannot manufacture a short-search win.
            m1 = engine.best_move(board, movetime=t_short).move
            m2 = engine.best_move(board, movetime=t_long).move
            if m1 is None or m2 is None:
                continue
            l1 = loss_of(board, m1, base)
            l2 = loss_of(board, m2, base)
            if l1 is None or l2 is None:
                continue
            # The LONG search is the classifier; the short one is context.
            verdict = "eval-limited" if l2 >= min_loss else "search-limited"
            counts[verdict] += 1
            if l1 < min_loss:
                counts["(short search also avoided it)"] += 1
            by_phase[r["phase"]][verdict] += 1

            if verdict == "eval-limited":
                # Which concept prefers our (worse) move? Static eval after each.
                sign = 1 if board.turn == chess.WHITE else -1
                bestmv = chess.Move.from_uci(r["best"])

                def concepts_after(mv):
                    b = board.copy()
                    b.push(mv)
                    bd = evaluate_detailed(b)
                    return {c.name: c.score for c in bd.concepts}

                try:
                    ours, theirs = concepts_after(m2), concepts_after(bestmv)
                except Exception:
                    ours = theirs = None
                if ours and theirs:
                    deltas = sorted(((sign * (ours[k] - theirs[k]), k) for k in ours),
                                    reverse=True)
                    if deltas and deltas[0][0] > 0:
                        culprit_mass[deltas[0][1]] += deltas[0][0]
                        culprit_count[deltas[0][1]] += 1
                    if len(examples) < 12:
                        top = ", ".join(f"{k} {d:+.0f}" for d, k in deltas[:3]
                                        if abs(d) >= 5)
                        examples.append(f"  {r['fen']}\n    ours {m2} (loss {l2:.0f}cp)"
                                        f" vs best {bestmv}: {top}")
            if (i + 1) % 25 == 0:
                print(f"  classified {i + 1}", flush=True)
    finally:
        sf.quit()

    total = counts["search-limited"] + counts["eval-limited"]
    print("\n" + "=" * 72)
    print(f"{total} real blunders re-examined at {t_long}s ({t_long / t_short:.0f}x "
          f"the {t_short}s they were played at)")
    print("-" * 72)
    for k in ("search-limited", "eval-limited"):
        if total:
            print(f"  {k:<16} {counts[k]:>5}  ({100 * counts[k] / total:.1f}%)")
    print(f"  [context] a fresh {t_short}s search also avoided the blunder in "
          f"{counts['(short search also avoided it)']} of them -- move choice at "
          f"this TC is unstable, which is why the short search cannot classify.")
    print("-" * 72)
    print("by phase (search-limited / eval-limited):")
    for ph in ("opening", "middlegame", "endgame"):
        if ph in by_phase:
            d = by_phase[ph]
            print(f"  {ph:<12} {d['search-limited']:>4} / {d['eval-limited']:<4}")
    print("=" * 72)
    if culprit_mass:
        print("\nEVAL-LIMITED: concepts most often favouring our WORSE move")
        print("(this is the targeted, interpretable eval work)")
        for k in sorted(culprit_mass, key=lambda x: -culprit_mass[x]):
            print(f"  {k:<18} {culprit_mass[k]:+8.0f}cp  ({culprit_count[k]} positions)")
    if examples:
        print("\nexamples:")
        print("\n".join(examples))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pgn", help="mine blunders from these games")
    p.add_argument("--epd", help="reuse a previously mined suite instead")
    p.add_argument("--out", default=None, help="write the mined suite here")
    p.add_argument("--depth", type=int, default=14, help="Stockfish verification depth")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--min-loss", type=int, default=150,
                   help="centipawns given up before a move counts as a blunder")
    p.add_argument("--short", type=float, default=0.3, help="the gate/game time control")
    p.add_argument("--long", type=float, default=3.0, help="10x thinking time")
    p.add_argument("--max-positions", type=int, default=150)
    p.add_argument("--max-games", type=int, default=0)
    p.add_argument("--us", default="ConceptChess")
    p.add_argument("--mine-only", action="store_true")
    args = p.parse_args()

    sf_path = shutil.which("stockfish")
    if not sf_path:
        sys.exit("stockfish not found on PATH")

    if args.pgn:
        rows = mine(args.pgn, sf_path, args.depth, args.workers, args.min_loss,
                    args.us, args.max_games)
        print(f"\nmined {len(rows)} blunders")
        byph = defaultdict(int)
        for r in rows:
            byph[r["phase"]] += 1
        for k, v in sorted(byph.items(), key=lambda kv: -kv[1]):
            print(f"  {k:<12} {v}")
        if args.out:
            write_epd(rows, args.out)
    elif args.epd:
        rows = read_epd(args.epd)
        print(f"loaded {len(rows)} positions from {args.epd}")
    else:
        sys.exit("need --pgn or --epd")

    if args.mine_only:
        return
    classify(rows, sf_path, args.depth, args.short, args.long, args.min_loss,
             args.max_positions)


if __name__ == "__main__":
    main()

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


def diagnose_vs_sf(fen_source, n, movetime, sf_depth, seed):
    """Realistic-position mode: sample FENs, compare the engine's move to
    Stockfish's, attribute clear disagreements to the responsible concept.
    No pre-verified suite needed — the target is move choice, not static-eval
    agreement (session 3-4 showed the latter is the wrong target)."""
    import json, random, shutil
    import chess.engine
    rng = random.Random(seed)
    rows = [json.loads(l) for l in Path(fen_source).read_text().splitlines()]
    rng.shuffle(rows)
    sf = chess.engine.SimpleEngine.popen_uci(shutil.which("stockfish"))
    engine = Engine(use_book=False)
    from collections import defaultdict
    culprit_mass = defaultdict(float); culprit_count = defaultdict(int)
    misses = solved = 0
    try:
        for r in rows:
            if solved + misses >= n:
                break
            board = chess.Board(r["fen"])
            if board.is_game_over():
                continue
            info = sf.analyse(board, chess.engine.Limit(depth=sf_depth))
            sfmove = info["pv"][0]
            em = engine.best_move(board, movetime=movetime).move
            if em == sfmove:
                solved += 1; continue
            # only count clear disagreements: SF move much better by SF eval
            gap = None
            i2 = sf.analyse(board, chess.engine.Limit(depth=sf_depth), multipv=2,
                            root_moves=[sfmove, em]) if em else None
            if i2 and len(i2) == 2:
                s_sf = i2[0]["score"].pov(board.turn).score(mate_score=10000)
                s_em = i2[1]["score"].pov(board.turn).score(mate_score=10000)
                if s_sf is None or s_em is None:
                    continue
                gap = s_sf - s_em
            if gap is None or gap < 60:
                continue
            misses += 1
            stm = board.turn; sign = 1 if stm == chess.WHITE else -1
            def after(mv):
                b = board.copy(); b.push(mv)
                return _concept_scores(b)
            e_sc, e_tot = after(em); b_sc, b_tot = after(sfmove)
            deltas = sorted(((sign*(e_sc[k]-b_sc[k]), k) for k in e_sc), reverse=True)
            if deltas and deltas[0][0] > 0:
                culprit_mass[deltas[0][1]] += deltas[0][0]
                culprit_count[deltas[0][1]] += 1
            top = ", ".join(f"{k} {d:+.0f}" for d,k in deltas[:3] if abs(d)>=5)
            print(f"{board.fen()}\n  eng {em} vs SF {sfmove} (SF gap {gap:+d}cp): {top}", flush=True)
    finally:
        sf.quit()
    tot = solved + misses
    print(f"\n=== {solved}/{tot} agreed with SF; {misses} clear disagreements ===")
    print("concepts most often favouring the engine's WORSE move:")
    for k in sorted(culprit_mass, key=lambda x:-culprit_mass[x]):
        print(f"  {k:16s} {culprit_mass[k]:+7.0f}cp ({culprit_count[k]} pos)")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("suite", nargs="?")
    p.add_argument("--movetime", type=float, default=0.3)
    p.add_argument("--vs-sf", metavar="FEN_JSONL",
                   help="realistic mode: sample FENs from this jsonl, compare to Stockfish")
    p.add_argument("--n", type=int, default=60)
    p.add_argument("--sf-depth", type=int, default=16)
    p.add_argument("--seed", type=int, default=20)
    a = p.parse_args()
    if a.vs_sf:
        diagnose_vs_sf(a.vs_sf, a.n, a.movetime, a.sf_depth, a.seed)
    else:
        diagnose(a.suite, a.movetime)


if __name__ == "__main__":
    main()

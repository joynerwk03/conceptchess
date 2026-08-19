"""Is this evaluation a worse BOUND than Stockfish 11's, even though it is an
equally good predictor?

Two results in this project contradict each other:

  * the evaluation matches SF11's classical eval on decisive-game outcome loss
    (-2.96%) and beats it at picking the move a deep search picks (20.0% vs
    13.2%);
  * eleven pruning configurations -- razoring, SEE pruning of losing captures,
    history pruning, and a TT-refined estimate -- all measured NEGATIVE, monotone
    in how hard they pruned, and the conclusion recorded was "the search prunes
    exactly as hard as its evaluation supports".

Both cannot be describing the same evaluation quality, and the resolution is
that they measure different properties. Outcome loss and move ranking are about
ACCURACY ON AVERAGE. Every pruning rule in a search asks a different question:

    the static eval is far below beta -- can I assume the search will not exceed
    beta if I look?

That is a question about the ERROR DISTRIBUTION, and specifically about its
TAIL. An evaluation that is usually within 40cp but is occasionally wrong by
400cp is excellent by outcome loss and useless for pruning, because every
pruning margin has to be set wide enough to cover the tail. Fat tails force wide
margins; wide margins prune little; pruning little means a fat tree; a fat tree
means less depth in the same second -- which is exactly the 5.3x node ratio and
the depth-14 collapse.

So measure the tail directly, for both evaluations, on the same positions:

    error = (search score at depth D) - (static eval)

and compare the spread and the tail quantiles. If this engine's tail is fatter,
that is the deficit, it is invisible to every eval metric used so far, and it
explains why no pruning technique has ever paid.

    PYTHONPATH=. .venv/bin/python research/eval_tails.py --n 400 --depth 10
"""
import argparse
import json
import multiprocessing as mp
import random
import re
import subprocess

import chess
import numpy as np

from research.texel import ROOT

FINAL = re.compile(r"(?:Final|Total) evaluation:?\s+([+-]?\d+\.\d+)")
SCORE = re.compile(r"score cp (-?\d+)")
# A mate score is not an evaluation error. Stockfish reports it as "score mate
# N", which the cp regex does not match -- so without this the last cp value
# from an earlier iteration is kept and reported as a ~10,000cp error. Our own
# side encodes mates as +/-(100000 - plies) and is filtered by magnitude.
MATE = re.compile(r"score mate -?\d+")


def sf_chunk(args):
    """(static eval, search score at depth D) from one Stockfish process."""
    fens, binary, depth = args
    p = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         text=True, bufsize=1)
    p.stdin.write("uci\n")
    p.stdin.flush()
    while "uciok" not in (p.stdout.readline() or "uciok"):
        pass
    p.stdin.write("setoption name Threads value 1\n")
    out = []
    for f in fens:
        p.stdin.write(f"position fen {f}\neval\nisready\n")
        p.stdin.flush()
        st = None
        while True:
            line = p.stdout.readline()
            if not line or line.startswith("readyok"):
                break
            if st is None:
                m = FINAL.search(line)
                if m:
                    st = float(m.group(1)) * 100.0
        p.stdin.write(f"go depth {depth}\n")
        p.stdin.flush()
        sc = None
        mated = False
        while True:
            line = p.stdout.readline()
            if not line:
                break
            if MATE.search(line):
                mated = True
            m = SCORE.search(line)
            if m:
                sc = int(m.group(1))
            if line.startswith("bestmove"):
                break
        if mated:
            sc = None
        # both are from the side to move; keep them in that frame
        out.append((st, sc))
    p.stdin.write("quit\n")
    p.stdin.flush()
    p.wait(timeout=10)
    return out


def mine_chunk(args):
    fens, depth = args
    import sys
    sys.path.insert(0, ".")
    from engine.engine import Engine
    from engine.evaluation import evaluate
    eng = Engine(use_book=False, use_tablebase=False)
    out = []
    for f in fens:
        b = chess.Board(f)
        st = evaluate(b)                       # White's frame
        if b.turn == chess.BLACK:
            st = -st                           # side-to-move frame
        r = eng.best_move(b, movetime=99.0, max_depth=depth)
        sc = getattr(r, "score", None)         # already side-to-move
        if sc is not None and abs(sc) >= 90000:
            sc = None                          # mate score, not an eval error
        out.append((st, sc))
    return out


def report(name, err):
    err = np.asarray(err, dtype=float)
    a = np.abs(err)
    print(f"  {name:<16}"
          f"{np.std(err):>9.0f}"
          f"{np.median(a):>9.0f}"
          f"{np.percentile(a, 90):>9.0f}"
          f"{np.percentile(a, 95):>9.0f}"
          f"{np.percentile(a, 99):>9.0f}"
          f"{100*np.mean(a > 200):>9.1f}%"
          f"{100*np.mean(a > 400):>9.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel4.jsonl"))
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--depth", type=int, default=10)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--sf11", default="/home/joynerwk03/bin/stockfish11")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.data)]
    random.Random(808).shuffle(rows)
    fens = [r["fen"] for r in rows[:a.n]]
    print(f"{len(fens)} positions, search depth {a.depth}\n")

    def par(fn, arg, tag):
        ch = [(fens[i::a.workers],) + arg for i in range(a.workers)]
        with mp.Pool(a.workers) as pool:
            parts = pool.map(fn, ch)
        out = [None] * len(fens)
        for i, part in enumerate(parts):
            out[i::a.workers] = part
        print(f"  {tag} done")
        return out

    mine = par(mine_chunk, (a.depth,), "this engine")
    sf = par(sf_chunk, (a.sf11, a.depth), "stockfish 11")

    em, es = [], []
    for (m_st, m_sc), (s_st, s_sc) in zip(mine, sf):
        if None not in (m_st, m_sc):
            em.append(m_sc - m_st)
        if None not in (s_st, s_sc):
            es.append(s_sc - s_st)

    print(f"\n  error = search(depth {a.depth}) - static eval, side-to-move frame")
    print(f"\n  {'':<16}{'stdev':>9}{'|med|':>9}{'p90':>9}{'p95':>9}{'p99':>9}"
          f"{'>200cp':>9}{'>400cp':>9}")
    print("  " + "-" * 79)
    report("this engine", em)
    report("stockfish 11", es)
    print("\n  Pruning margins must cover the TAIL, not the median. A fatter tail")
    print("  forces wider margins, which prunes less, which is a fatter tree and")
    print("  less depth per second -- the mechanism behind every negative pruning")
    print("  result in this project.")


if __name__ == "__main__":
    main()

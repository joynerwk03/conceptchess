"""Effective branching factor: how fast does each engine's tree grow per ply?

`research/speed_gap.py` found that Stockfish 11 is only 1.26x faster than this
engine in raw nodes per second, has an evaluation no better than this one at
predicting outcomes, and is still ~500 Elo stronger. The Elo is therefore in how
the nodes are SPENT, and EBF is the direct measurement of that.

Nominal depth is not comparable between engines -- reductions and extensions are
counted differently, so SF11's "depth 22" is not 22 full plies. The RATIO
between consecutive depths within one engine is comparable, though: it is that
engine's own tree-growth rate, and it is the number that decides how deep a
fixed time budget reaches.

    PYTHONPATH=. .venv/bin/python research/ebf.py --max-depth 16
"""
import argparse
import re
import statistics
import subprocess

FENS = [
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r2q1rk1/pb1nbppp/1p2pn2/2pp4/3P4/1PN1PN2/PBP1BPPP/R2Q1RK1 w - - 0 1",
    "4rrk1/pp1n1pp1/2pb3p/q2p4/3P1B2/2NB1Q1P/PPP2PP1/3RR1K1 w - - 0 1",
]
NODES = re.compile(r"\bnodes (\d+)\b")


def sf_nodes(binary, fen, depth):
    p = subprocess.Popen([binary], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, bufsize=1)
    p.stdin.write("uci\n")
    p.stdin.flush()
    while "uciok" not in (p.stdout.readline() or "uciok"):
        pass
    p.stdin.write(f"setoption name Threads value 1\nposition fen {fen}\n"
                  f"go depth {depth}\n")
    p.stdin.flush()
    n = 0
    while True:
        line = p.stdout.readline()
        if not line:
            break
        m = NODES.search(line)
        if m:
            n = int(m.group(1))
        if line.startswith("bestmove"):
            break
    p.stdin.write("quit\n")
    p.stdin.flush()
    p.wait(timeout=10)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-depth", type=int, default=16)
    ap.add_argument("--sf11", default="/home/joynerwk03/bin/stockfish11")
    a = ap.parse_args()

    import chess
    from engine.engine import Engine
    eng = Engine(use_book=False, use_tablebase=False)

    print(f"{'depth':>6}  {'this engine':>14} {'ebf':>6}   "
          f"{'stockfish 11':>14} {'ebf':>6}")
    prev_a = prev_b = None
    for d in range(6, a.max_depth + 1):
        na = statistics.median(
            eng.best_move(chess.Board(f), movetime=600.0, max_depth=d).nodes
            for f in FENS)
        nb = statistics.median(sf_nodes(a.sf11, f, d) for f in FENS)
        ea = f"{na/prev_a:6.2f}" if prev_a else "     -"
        eb = f"{nb/prev_b:6.2f}" if prev_b else "     -"
        print(f"{d:>6}  {na:>14,.0f} {ea}   {nb:>14,.0f} {eb}")
        prev_a, prev_b = na, nb


if __name__ == "__main__":
    main()

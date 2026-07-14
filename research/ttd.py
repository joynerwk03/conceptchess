"""Time/nodes to fixed depth — the deterministic speed metric for search work.

Node counts at fixed depth are exactly reproducible for a given search shape;
wall time adds machine noise, so both are reported. Used by exp5.

Usage: python -m research.ttd [depth]
"""

import sys
import time

import chess

from engine.engine import Engine

FENS = [
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5",
    "r4rk1/1bq1bppp/p2ppn2/1p6/3NPP2/2N1B3/PPP1B1PP/R2Q1RK1 w - - 0 12",
    "r2q1rk1/ppp2ppp/2n1bn2/2bpp3/8/2PP1NP1/PP2PPBP/RNBQ1RK1 w - - 0 8",
    "8/5pk1/6p1/8/8/6P1/5PK1/3r4 w - - 0 40",
]


def measure(depth=6, verbose=False):
    total_nodes, total_time = 0, 0.0
    for fen in FENS:
        engine = Engine()
        t = time.perf_counter()
        r = engine.best_move(chess.Board(fen), movetime=999, max_depth=depth)
        dt = time.perf_counter() - t
        total_nodes += r.nodes
        total_time += dt
        if verbose:
            print(f"  d{depth} nodes {r.nodes:>9,}  {dt:5.2f}s  {fen.split()[0][:24]}")
    return total_nodes, total_time


if __name__ == "__main__":
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    n, t = measure(d, verbose=True)
    print(f"TOTAL nodes {n:,}  time {t:.2f}s")

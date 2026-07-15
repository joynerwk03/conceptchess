"""Time/nodes to fixed depth for the COMPILED C engine — the session-10+ speed metric.

Deterministic node counts (search shape only) plus wall time. Same 4 positions
as research/ttd.py for continuity across the Python-era and compiled-era logs.

Usage: python -m research.cttd [depth]
"""

import sys
import time

import chess

from engine import core

FENS = [
    "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5",
    "r4rk1/1bq1bppp/p2ppn2/1p6/3NPP2/2N1B3/PPP1B1PP/R2Q1RK1 w - - 0 12",
    "r2q1rk1/ppp2ppp/2n1bn2/2bpp3/8/2PP1NP1/PP2PPBP/RNBQ1RK1 w - - 0 8",
    "8/5pk1/6p1/8/8/6P1/5PK1/3r4 w - - 0 40",
]


def measure(depth=10, verbose=False):
    total_nodes, total_time = 0, 0.0
    for fen in FENS:
        board = chess.Board(fen)
        t = time.perf_counter()
        _, _, d, nodes, _, _ = core.search(board, movetime=999, max_depth=depth)
        dt = time.perf_counter() - t
        total_nodes += nodes
        total_time += dt
        if verbose:
            print(f"  d{depth} nodes {nodes:>10,}  {dt:5.2f}s  {fen.split()[0][:24]}")
    return total_nodes, total_time


if __name__ == "__main__":
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    n, t = measure(d, verbose=True)
    print(f"TOTAL nodes {n:,}  time {t:.2f}s")

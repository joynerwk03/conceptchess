"""Speed benchmark: nodes/sec and depth reached in fixed time.

Usage:
  python -m research.benchmark            # 2s per position, prints table
  python -m research.benchmark --save     # also appends to research/baselines.json
"""

import argparse
import json
import statistics
import subprocess
import time
from datetime import date
from pathlib import Path

import chess

from engine.engine import Engine

BASELINES = Path(__file__).parent / "baselines.json"

POSITIONS = [
    ("startpos", chess.STARTING_FEN),
    ("italian_mg", "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5"),
    ("closed_mg", "r4rk1/1bq1bppp/p2ppn2/1p6/3NPP2/2N1B3/PPP1B1PP/R2Q1RK1 w - - 0 12"),
    ("open_tactics", "r2q1rk1/ppp2ppp/2n1bn2/2bpp3/8/2PP1NP1/PP2PPBP/RNBQ1RK1 w - - 0 8"),
    ("rook_endgame", "8/5pk1/6p1/8/8/6P1/5PK1/3r4 w - - 0 40"),
    ("pawn_endgame", "8/8/4k3/2p5/2P5/4K3/8/8 w - - 0 50"),
]


def run(movetime=2.0):
    rows = []
    for name, fen in POSITIONS:
        engine = Engine()
        r = engine.best_move(chess.Board(fen), movetime=movetime)
        rows.append({"name": name, "depth": r.depth, "nodes": r.nodes,
                     "nps": r.nps, "time": round(r.time, 2)})
    return rows


def git_rev():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True,
            cwd=Path(__file__).parent.parent).strip()
    except Exception:
        return "unknown"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--movetime", type=float, default=2.0)
    p.add_argument("--save", action="store_true")
    args = p.parse_args()

    rows = run(args.movetime)
    print(f"{'position':<14} {'depth':>5} {'nodes':>10} {'nps':>8} {'time':>6}")
    for r in rows:
        print(f"{r['name']:<14} {r['depth']:>5} {r['nodes']:>10,} {r['nps']:>8,} {r['time']:>6}")
    avg_depth = statistics.mean(r["depth"] for r in rows)
    avg_nps = int(statistics.mean(r["nps"] for r in rows))
    print(f"\navg depth {avg_depth:.2f}   avg nps {avg_nps:,}   ({args.movetime}s/pos)")

    if args.save:
        history = json.loads(BASELINES.read_text()) if BASELINES.exists() else []
        history.append({
            "date": date.today().isoformat(),
            "rev": git_rev(),
            "movetime": args.movetime,
            "avg_depth": round(avg_depth, 2),
            "avg_nps": avg_nps,
            "positions": rows,
        })
        BASELINES.write_text(json.dumps(history, indent=2) + "\n")
        print(f"saved to {BASELINES}")


if __name__ == "__main__":
    main()

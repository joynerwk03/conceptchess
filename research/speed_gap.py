"""Where does a classical engine's Elo advantage actually live?

`research/eval_room.py` established that this engine's evaluation predicts game
outcomes at least as well as Stockfish 11's classical evaluation, while a modern
NNUE beats both by ~17%. SF11 is a ~3300-Elo engine. So SF11's ~500 Elo over
this engine is NOT coming from chess knowledge in its evaluation -- it has to be
in the search and in raw speed.

This measures the raw-speed half, which is the unambiguous one: same positions,
same wall clock, one thread each, count nodes.

Nominal DEPTH is deliberately not compared. Depth means different things in
different engines -- reductions and extensions are counted differently -- so
"SF11 reaches depth 20 and we reach depth 13" is not a fact about search
efficiency. Nodes per second is a fact.

    PYTHONPATH=. .venv/bin/python research/speed_gap.py --movetime 3000
"""
import argparse
import re
import statistics
import subprocess
import time

FENS = [
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r2q1rk1/pb1nbppp/1p2pn2/2pp4/3P4/1PN1PN2/PBP1BPPP/R2Q1RK1 w - - 0 1",
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "4rrk1/pp1n1pp1/2pb3p/q2p4/3P1B2/2NB1Q1P/PPP2PP1/3RR1K1 w - - 0 1",
    "2rq1rk1/pb2bppp/1pn1pn2/8/2BP4/2N1PN2/PB3PPP/R2Q1RK1 w - - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
]
INFO = re.compile(r"\bnodes (\d+)\b")
DEPTH = re.compile(r"\bdepth (\d+)\b")


def run(cmd, cwd, fen, movetime, extra=()):
    p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, bufsize=1)
    p.stdin.write("uci\n")
    p.stdin.flush()
    while "uciok" not in (p.stdout.readline() or "uciok"):
        pass
    for line in extra:
        p.stdin.write(line + "\n")
    p.stdin.write("setoption name Threads value 1\nisready\n")
    p.stdin.flush()
    while "readyok" not in (p.stdout.readline() or "readyok"):
        pass
    p.stdin.write(f"position fen {fen}\ngo movetime {movetime}\n")
    p.stdin.flush()
    nodes = depth = 0
    t0 = time.time()
    while True:
        line = p.stdout.readline()
        if not line:
            break
        m = INFO.search(line)
        if m:
            nodes = int(m.group(1))
        d = DEPTH.search(line)
        if d and "currmove" not in line:
            depth = max(depth, int(d.group(1)))
        if line.startswith("bestmove"):
            break
    el = time.time() - t0
    p.stdin.write("quit\n")
    p.stdin.flush()
    p.wait(timeout=10)
    return nodes, depth, el


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--movetime", type=int, default=3000)
    ap.add_argument("--sf11", default="/home/joynerwk03/bin/stockfish11")
    ap.add_argument("--cc", default="/home/joynerwk03/mission-control/"
                                    "projects/conceptchess")
    a = ap.parse_args()

    res = {}

    # This engine's UCI emits no `info` lines, only `bestmove`, so nodes and
    # depth are taken from the Python API instead -- the same path the
    # node-count harness uses.
    import chess
    from engine.engine import Engine
    eng = Engine(use_book=False, use_tablebase=False)
    rows = []
    for fen in FENS:
        t0 = time.time()
        r = eng.best_move(chess.Board(fen), movetime=a.movetime / 1000.0)
        el = time.time() - t0
        rows.append((r.nodes / max(el, 1e-9), getattr(r, "depth", 0), r.nodes))
    res["this engine"] = rows
    print(f"{'this engine':<14} median NPS "
          f"{statistics.median(r[0] for r in rows):>12,.0f}   "
          f"depths {[r[1] for r in rows]}")

    rows = []
    for fen in FENS:
        n, d, el = run([a.sf11], None, fen, a.movetime)
        rows.append((n / max(el, 1e-9), d, n))
    res["stockfish 11"] = rows
    print(f"{'stockfish 11':<14} median NPS "
          f"{statistics.median(r[0] for r in rows):>12,.0f}   "
          f"depths {[r[1] for r in rows]}")

    a_nps = statistics.median(r[0] for r in res["this engine"])
    b_nps = statistics.median(r[0] for r in res["stockfish 11"])
    ratio = b_nps / a_nps
    import math
    print(f"\nraw speed ratio  {ratio:.2f}x  (stockfish 11 / this engine)")
    print(f"at ~50 Elo per doubling of speed, that accounts for "
          f"~{50*math.log2(ratio):+.0f} Elo of SF11's advantage")


if __name__ == "__main__":
    main()

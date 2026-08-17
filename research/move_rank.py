"""Can the evaluation RANK MOVES, as opposed to rank positions?

`research/eval_room.py` says this engine's evaluation predicts game outcomes as
well as Stockfish 11's classical evaluation. That result sits badly beside a
head-to-head of +0 =8 -192 (-676 Elo) at a similar NPS, so one of the two
measurements is answering the wrong question -- and it is probably the first one.

Outcome loss asks: given a position drawn from anywhere, how well does the
number predict the result? A search never asks that. A search asks: given these
thirty positions, all one move apart, which is best? Those are different skills.
An evaluation can be well calibrated across the whole space of positions and
still be unable to separate siblings, because siblings differ by one move and
almost all of the eval's terms are identical between them -- the discriminating
signal is a small difference between two large, nearly equal sums, which is
exactly where a concept sum's errors are worst relative to the quantity of
interest. And outcome loss cannot see it: shifting every sibling by the same
amount does not change the loss at all, but destroys the ranking.

So measure the thing the search actually needs. For each position, take the
static evaluation's preferred move -- argmax over children of the static score --
and ask how often it matches the move a deep search picks. Same positions, same
ground truth, for this engine and for Stockfish 11.

If the two evaluations rank moves about equally well, the evaluation really is
closed and the deficit is elsewhere. If Stockfish 11 ranks moves much better
despite the same outcome loss, then the evaluation is NOT closed -- it is
mis-measured, and every screen in this project has been optimising the wrong
objective.

    PYTHONPATH=. .venv/bin/python research/move_rank.py --n 1500
"""
import argparse
import json
import multiprocessing as mp
import random
import re
import subprocess

import chess

from research.texel import ROOT

BEST = re.compile(r"^bestmove (\S+)")
SCORE = re.compile(r"score cp (-?\d+)")


def truth_chunk(args):
    """Deep-search best move: the ground truth both evaluations are judged by."""
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
        p.stdin.write(f"position fen {f}\ngo depth {depth}\n")
        p.stdin.flush()
        bm = None
        while True:
            line = p.stdout.readline()
            if not line:
                break
            m = BEST.match(line)
            if m:
                bm = m.group(1)
                break
        out.append(bm)
    p.stdin.write("quit\n")
    p.stdin.flush()
    p.wait(timeout=10)
    return out


def sf_pick_chunk(args):
    """Stockfish 11's STATIC pick: argmax of its own eval over the children."""
    fens, binary = args
    p = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         text=True, bufsize=1)
    p.stdin.write("uci\n")
    p.stdin.flush()
    while "uciok" not in (p.stdout.readline() or "uciok"):
        pass
    FIN = re.compile(r"(?:Final|Total) evaluation:?\s+([+-]?\d+\.\d+)")
    out = []
    for f in fens:
        b = chess.Board(f)
        # The mover's colour must be read BEFORE the push. Reading b.turn after
        # the matching pop gives the mover again rather than the opponent, which
        # inverts the sign and makes the "best" move the worst one -- both
        # engines then score ~1.5%, which is how this was caught.
        mover = b.turn
        best, bestv = None, None
        for mv in b.legal_moves:
            b.push(mv)
            if b.is_checkmate():
                b.pop()
                best, bestv = mv, 1e9
                break
            fen2, in_chk = b.fen(), b.is_check()
            b.pop()
            if in_chk:                       # eval refuses; skip, as we must
                continue
            p.stdin.write(f"position fen {fen2}\neval\nisready\n")
            p.stdin.flush()
            v = None
            while True:
                line = p.stdout.readline()
                if not line or line.startswith("readyok"):
                    break
                if v is None:
                    m = FIN.search(line)
                    if m:
                        v = float(m.group(1)) * 100.0
            if v is None:
                continue
            # child eval is from White's perspective; the MOVER maximises it
            # when the mover is White and minimises it when Black.
            v = v if mover == chess.WHITE else -v
            if bestv is None or v > bestv:
                best, bestv = mv, v
        out.append(best.uci() if best else None)
    p.stdin.write("quit\n")
    p.stdin.flush()
    p.wait(timeout=10)
    return out


def mine_pick_chunk(fens):
    """This engine's STATIC pick, through the real evaluate()."""
    from engine.evaluation import evaluate
    out = []
    for f in fens:
        b = chess.Board(f)
        mover = b.turn                       # read before any push (see above)
        best, bestv = None, None
        for mv in b.legal_moves:
            b.push(mv)
            if b.is_checkmate():
                b.pop()
                best, bestv = mv, 1e9
                break
            v = evaluate(b)
            b.pop()
            v = v if mover == chess.WHITE else -v
            if bestv is None or v > bestv:
                best, bestv = mv, v
        out.append(best.uci() if best else None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel4.jsonl"))
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--depth", type=int, default=14)
    ap.add_argument("--sf11", default="/home/joynerwk03/bin/stockfish11")
    ap.add_argument("--truth", default="stockfish")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.data)]
    random.Random(4242).shuffle(rows)
    fens = [r["fen"] for r in rows[:a.n]]
    print(f"{len(fens):,} positions; ground truth = {a.truth} depth {a.depth}")

    def par(fn, arg, tag):
        ch = [fens[i::a.workers] for i in range(a.workers)]
        payload = ch if arg is None else [(c,) + arg for c in ch]
        with mp.Pool(a.workers) as pool:
            parts = pool.map(fn, payload)
        out = [None] * len(fens)
        for i, part in enumerate(parts):
            out[i::a.workers] = part
        print(f"  {tag} done")
        return out

    truth = par(truth_chunk, (a.truth, a.depth), "ground truth")
    mine = par(mine_pick_chunk, None, "this engine's static pick")
    sf11 = par(sf_pick_chunk, (a.sf11,), "stockfish 11's static pick")

    ok = [i for i in range(len(fens))
          if truth[i] and mine[i] and sf11[i]]
    hm = sum(1 for i in ok if mine[i] == truth[i])
    hs = sum(1 for i in ok if sf11[i] == truth[i])
    n = len(ok)
    print("\n" + "=" * 62)
    print(f"  positions compared: {n:,}")
    print(f"  this engine    static pick matches a depth-{a.depth} search: "
          f"{100*hm/n:5.2f}%")
    print(f"  stockfish 11   static pick matches a depth-{a.depth} search: "
          f"{100*hs/n:5.2f}%")
    print("=" * 62)
    print("  Outcome loss said these two evaluations were in the same class.\n"
          "  This asks the question a search actually asks.")


if __name__ == "__main__":
    main()

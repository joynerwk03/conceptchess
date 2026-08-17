"""Head-to-head at EQUAL NOMINAL DEPTH, to separate tree size from node quality.

A contradiction sits in this project's measurements. Against Stockfish 11 this
engine scores 2.0% (-676 Elo). Yet its evaluation matches SF11's at predicting
game outcomes (-2.96%) and beats it at ranking moves (20.0% vs 13.2%), its
ordering finds the best move first 88.3% of the time, its reduction schedule is
neutral-to-negative in both directions, and its NPS is within 1.26x. Equal
knowledge, equal speed, good ordering, and a 500-point gap cannot all be true --
one of those measurements is not measuring the operative variable.

Equal TIME confounds two things: how big a tree each engine builds, and how much
each node is worth. This removes the first by fixing nominal depth for both
sides. The result reads as follows:

  * if the score is close at equal depth, then the entire gap is tree size --
    SF11 simply reaches deeper in the same seconds -- and the reduction schedule
    is the lever after all, contradicting the local-optimum finding;
  * if SF11 still wins heavily at equal depth, its nodes are worth more than
    ours, and the eval/ordering measurements are missing what matters.

Nominal depth is NOT comparable between engines -- SF11 reduces harder, so its
depth 12 explores a narrower tree -- and that cuts in our favour here: it is
being asked to do the same nominal work with a thinner tree. A heavy loss under
that handicap is therefore strong evidence, while a close result is weak.

    PYTHONPATH=. .venv/bin/python research/depth_match.py --games 60 --depth 10
"""
import argparse
import random
import subprocess
import sys

import chess


class Uci:
    def __init__(self, cmd, cwd=None):
        self.p = subprocess.Popen(cmd, cwd=cwd, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, bufsize=1)
        self._send("uci")
        while "uciok" not in (self.p.stdout.readline() or "uciok"):
            pass
        self._send("setoption name Threads value 1")

    def _send(self, s):
        self.p.stdin.write(s + "\n")
        self.p.stdin.flush()

    def bestmove(self, fen, moves, depth):
        pos = f"position fen {fen}"
        if moves:
            pos += " moves " + " ".join(moves)
        self._send(pos)
        self._send(f"go depth {depth}")
        while True:
            line = self.p.stdout.readline()
            if not line:
                return None
            if line.startswith("bestmove"):
                mv = line.split()[1]
                return None if mv in ("(none)", "0000") else mv

    def close(self):
        try:
            self._send("quit")
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--depth", type=int, default=10)
    ap.add_argument("--sf11", default="/home/joynerwk03/bin/stockfish11")
    ap.add_argument("--cc", default="/home/joynerwk03/mission-control/"
                                    "projects/conceptchess")
    ap.add_argument("--book", default="")
    a = ap.parse_args()

    book = []
    if a.book:
        with open(a.book) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    book.append(" ".join(line.split()[:4]) + " 0 1")
    random.Random(11).shuffle(book)

    ours = Uci([f"{a.cc}/.venv/bin/python", "-m", "engine.uci"], cwd=a.cc)
    theirs = Uci([a.sf11])
    w = d = l = 0
    try:
        for g in range(a.games):
            fen = book[g % len(book)] if book else chess.STARTING_FEN
            board = chess.Board(fen)
            we_white = (g % 2 == 0)
            moves = []
            while not board.is_game_over(claim_draw=True) and len(moves) < 300:
                mine = (board.turn == chess.WHITE) == we_white
                eng = ours if mine else theirs
                uci = eng.bestmove(fen, moves, a.depth)
                if uci is None:
                    break
                try:
                    mv = chess.Move.from_uci(uci)
                except ValueError:
                    break
                if mv not in board.legal_moves:
                    print(f"  illegal move {uci} from "
                          f"{'ours' if mine else 'theirs'}; aborting game")
                    break
                board.push(mv)
                moves.append(uci)
            res = board.result(claim_draw=True)
            if res == "1/2-1/2" or res == "*":
                d += 1
            elif (res == "1-0") == we_white:
                w += 1
            else:
                l += 1
            sc = (w + 0.5 * d) / max(w + d + l, 1)
            print(f"game {g+1}/{a.games}: +{w} ={d} -{l}  ({100*sc:.1f}%)",
                  flush=True)
    finally:
        ours.close()
        theirs.close()

    n = w + d + l
    sc = (w + 0.5 * d) / max(n, 1)
    print(f"\nat equal nominal depth {a.depth}: +{w} ={d} -{l}  ({100*sc:.1f}%)")
    if 0 < sc < 1:
        import math
        print(f"  Elo diff {400*math.log10(sc/(1-sc)):+.0f}")
    print("\nSF11 reduces harder, so its nominal depth explores a THINNER tree:")
    print("a heavy loss here is strong evidence about node quality; a close")
    print("result is weak evidence, because the handicap runs our way.")


if __name__ == "__main__":
    main()

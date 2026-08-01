"""Cross-check: the compiled eval must equal the Python eval on every position.

This is the interpretability guarantee for the port — the fast C search
optimizes the same number the Python explanation layer reports. Run after any
eval change (regenerate eval_data.h + rebuild first).

Run: .venv/bin/python core/gen_eval_data.py && sh core/build.sh \
     && .venv/bin/python core/eval_check.py
"""

import ctypes
import json
import random
from pathlib import Path

import chess

from engine.evaluation import evaluate

import platform
LIB = Path(__file__).parent / ("libcengine.dylib" if platform.system() == "Darwin"
                              else "libcengine.so")
DATA = Path(__file__).parent.parent / "research" / "data"


def positions(n=4000):
    fens = []
    # the labeled eval set (realistic positions)
    for split in ("train", "val"):
        p = DATA / f"evalset_{split}.jsonl"
        if p.exists():
            fens += [json.loads(l)["fen"] for l in p.read_text().splitlines()]
    # random-walk positions for breadth (incl. endgames)
    rng = random.Random(1)
    for _ in range(n):
        b = chess.Board()
        for _ in range(rng.randrange(2, 80)):
            ms = list(b.legal_moves)
            if not ms:
                break
            b.push(rng.choice(ms))
        fens.append(b.fen())
    return fens


def main():
    lib = ctypes.CDLL(str(LIB))
    lib.c_eval.restype = ctypes.c_double
    lib.c_eval.argtypes = [ctypes.c_char_p]

    worst = 0.0
    worst_fen = None
    mismatches = 0
    fens = positions()
    for fen in fens:
        board = chess.Board(fen)
        py = float(evaluate(board))
        c = lib.c_eval(fen.encode())
        d = abs(py - c)
        if d > worst:
            worst, worst_fen = d, fen
        if d > 0.05:
            mismatches += 1
            if mismatches <= 8:
                print(f"  MISMATCH py={py:.3f} c={c:.3f} d={d:.3f}  {fen}")
    print(f"\nchecked {len(fens)} positions")
    print(f"max |C - Python| = {worst:.6f}  ({worst_fen})")
    print(f"mismatches (>0.05cp): {mismatches}")
    return 0 if mismatches == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Relabel the Texel positions with an EXTERNAL reference instead of our own game results.

The tapering fit was clean -- 382K positions, exact linearity, +0.339% HELD OUT
against +0.198% in sample -- and screened worse anyway. A holdout fixes
overfitting; it cannot fix a biased TARGET, and the target here is
self-play-generated (`texel.py gen --games 400`). CLAUDE.md already rules
self-play out as a gate because it pits a change against an opponent sharing its
exact blind spots; fitting the EVALUATION to self-play results inherits that
defect, which is the common cause behind every non-transferring Texel gain in
this project.

So: label each position with Stockfish 11 instead. Two things improve at once.

  * The target stops being our own opinion. SF11 is the same MODEL CLASS
    (hand-crafted classical), which is what makes it the right reference --
    `eval_room.py` measures us at -2.96% against it and +16.94% against an NNUE,
    and an NNUE target would be asking this eval to represent something its
    model class cannot.
  * The target stops being a coin flip. A game result is 0/0.5/1 -- one bit of
    heavily-confounded signal per position. A centipawn score is an informative
    label, so the same number of positions resolves far smaller effects.

Use ~/bin/stockfish11 explicitly. `shutil.which("stockfish")` on this box is
Stockfish 18, and measuring against it once produced a bogus 40x node ratio.

Scores are stored WHITE-RELATIVE, matching `res` in the source data (texel.py
compares `evaluate(b)` directly against a white-relative result). Mates are
clamped: they are not centipawns and would dominate any fit.

Usage: relabel.py <in.jsonl> <n> <out.jsonl> <depth> [nproc]
"""
import json
import multiprocessing as mp
import pathlib
import sys

import chess
import chess.engine

SF11 = pathlib.Path.home() / "bin" / "stockfish11"
MATE_CP = 2000


def work(args):
    lines, depth = args
    out = []
    eng = chess.engine.SimpleEngine.popen_uci(str(SF11))
    try:
        eng.configure({"Threads": 1, "Hash": 32})
        for ln in lines:
            d = json.loads(ln)
            b = chess.Board(d["fen"])
            try:
                info = eng.analyse(b, chess.engine.Limit(depth=depth))
                sc = info["score"].white()
                cp = sc.score(mate_score=MATE_CP)
            except Exception:
                continue
            if cp is None:
                continue
            cp = max(-MATE_CP, min(MATE_CP, cp))
            out.append({"fen": d["fen"], "res": d["res"], "sf": cp})
    finally:
        eng.quit()
    return out


def main():
    src, n, dst, depth = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
    nproc = int(sys.argv[5]) if len(sys.argv) > 5 else min(12, mp.cpu_count())
    assert SF11.exists(), f"REFUSING TO LABEL: {SF11} missing"

    lines = []
    with open(src) as fh:
        for i, ln in enumerate(fh):
            if i >= n:
                break
            lines.append(ln)

    # contiguous chunks, concatenated in order: the holdout is a trailing block
    # and adjacent lines are the same game
    sz = (len(lines) + nproc - 1) // nproc
    chunks = [(lines[i * sz:(i + 1) * sz], depth) for i in range(nproc)]
    with mp.Pool(nproc) as pool:
        parts = pool.map(work, chunks)

    with open(dst, "w") as fh:
        for p in parts:
            for r in p:
                fh.write(json.dumps(r) + "\n")
    print(f"labelled {sum(len(p) for p in parts)} positions at depth {depth} -> {dst}",
          flush=True)


if __name__ == "__main__":
    main()

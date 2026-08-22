"""Build a CACHED referee table: the one thing that makes fidelity screening work.

Measured facts that motivate it. Centipawn loss at 200 positions cannot tell a
0-Elo configuration from a -33-Elo one (14.1 / 13.9 / 14.2), because 33 Elo is
under 1cp of mean move quality while the per-position standard deviation is
~40cp. Resolving 1cp needs on the order of 10,000 positions.

That sounds prohibitive, but the expensive half does not depend on the engine
being tested: the referee's opinion of a position is a property of the POSITION.
Compute it once, cache it, and every later candidate costs only its own
fixed-depth search plus a dictionary lookup. A ~10k table gives roughly +/-0.4cp
on the mean, enough to resolve perhaps 10-15 Elo -- better than the +/-25 the
game gate manages, at a small fraction of the cost per candidate.

Positions come from texel6.jsonl, sampled with a stride across the file rather
than as a block. That matters: this data is self-play sampled every few plies,
so neighbouring lines are the SAME GAME -- the repo already learned that a
position-level split leaves one game on both sides and turned a -0.9% result
into a +1.2% one. Striding maximises the number of distinct games and therefore
the effective sample size.

Writes JSONL: {"fen":..., "best":uci, "moves":{uci:cp,...}} with scores from the
side to move on ONE MultiPV search, so every move sits on a single scale --
the flaw that invalidated the first attempt.

Usage: reftable.py <out.jsonl> <n-positions> [sf-depth] [multipv]
Resumable: an existing output file is read first and its positions skipped.
"""
import json
import os
import sys
import time
from pathlib import Path

import chess
import chess.engine

CC = Path("/home/joynerwk03/mission-control/projects/conceptchess")
SF11 = str(Path.home() / "bin/stockfish11")
SRC = CC / "research/data/texel6.jsonl"

out_path = Path(sys.argv[1])
n_want = int(sys.argv[2])
depth = int(sys.argv[3]) if len(sys.argv) > 3 else 12
multipv = int(sys.argv[4]) if len(sys.argv) > 4 else 12

lines = SRC.read_text().splitlines()
stride = max(1, len(lines) // n_want)
fens, seen = [], set()
for ln in lines[::stride]:
    try:
        f = json.loads(ln)["fen"]
    except Exception:
        continue
    key = " ".join(f.split()[:4])
    if key in seen:
        continue
    seen.add(key)
    fens.append(f)
    if len(fens) >= n_want:
        break

done = set()
if out_path.exists():
    for ln in out_path.read_text().splitlines():
        try:
            done.add(json.loads(ln)["fen"])
        except Exception:
            pass
    print(f"resuming: {len(done)} already done", flush=True)

todo = [f for f in fens if f not in done]
print(f"{len(fens)} positions from {len(lines)} lines (stride {stride}), "
      f"{len(todo)} to do, SF11 depth {depth} MultiPV {multipv}", flush=True)

t0 = time.time()
with out_path.open("a") as fh:
    eng = None
    for i, fen in enumerate(todo):
        if eng is None:
            eng = chess.engine.SimpleEngine.popen_uci(SF11)
            try:
                eng.configure({"Threads": 1, "Hash": 128})
            except Exception:
                pass
        board = chess.Board(fen)
        try:
            infos = eng.analyse(board, chess.engine.Limit(depth=depth),
                                multipv=multipv, game=object())
        except Exception:
            try:
                eng.quit()
            except Exception:
                pass
            eng = None
            continue
        table = {}
        for info in infos:
            pv = info.get("pv") or []
            if pv:
                table[str(pv[0])] = info["score"].pov(board.turn).score(
                    mate_score=100000)
        if not table:
            continue
        best = max(table, key=table.get)
        fh.write(json.dumps({"fen": fen, "best": best, "moves": table}) + "\n")
        if (i + 1) % 250 == 0:
            fh.flush()
            el = time.time() - t0
            rate = (i + 1) / el
            print(f"  {i + 1}/{len(todo)}  {rate:.1f} pos/s  "
                  f"eta {(len(todo) - i - 1) / rate / 60:.0f} min", flush=True)
    if eng is not None:
        eng.quit()
print(f"done in {(time.time() - t0) / 60:.1f} min -> {out_path}", flush=True)

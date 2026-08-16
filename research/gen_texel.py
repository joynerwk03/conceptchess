"""Generate fresh Texel training positions by self-play with the CURRENT engine.

Every fit in this project draws on `texel5.jsonl`: 98k positions, ~70k of them
decisive, generated on 1 August by an engine that measured 2743. The engine now
measures 2811 and has a materially different evaluation -- per-square piece
tables, a refitted weight set, a fitted king-danger curve. Two things follow:

  * the positions in that file are the ones the OLD engine steered into, and a
    training set should look like the positions the current one actually
    reaches;
  * the fits that paid most are the high-capacity ones -- 512 piece-square
    entries (+9.3 Elo), 90 weights (+6.4) -- and those are exactly the fits that
    a larger sample helps, because capacity is what a small sample cannot
    support.

Method, mirroring how the existing file was built and fixing one thing:

  * starts come from the UHO book, so games are varied and unbalanced rather
    than 5000 repetitions of the same opening;
  * both sides are this engine, at a short fixed movetime;
  * positions are sampled every few plies from ply 8 on, skipping any position
    where the side to move is in check -- an in-check position has no meaningful
    static evaluation, and the search never evaluates one either;
  * each sample is labelled with the eventual RESULT of its own game.

Games are played in parallel worker processes; each writes its own shard, which
the caller concatenates. Deterministic per shard given the seed, so an
interrupted run can be topped up rather than restarted.

    PYTHONPATH=. .venv/bin/python research/gen_texel.py --games 8000 --workers 18
"""
import argparse
import json
import multiprocessing as mp
import os
import random

import chess

from research.texel import ROOT

_ENG = None


def _engine():
    global _ENG
    if _ENG is None:
        from engine.engine import Engine
        os.environ["CC_THREADS"] = "1"
        _ENG = Engine(use_book=False, use_tablebase=False)
    return _ENG


def _play(job):
    """One game from `fen`; returns the sampled positions with the result."""
    fen, seed, movetime, every, max_plies = job
    eng = _engine()
    rng = random.Random(seed)
    board = chess.Board(fen)
    sampled = []
    plies = 0
    while plies < max_plies:
        if board.is_game_over(claim_draw=True):
            break
        r = eng.best_move(board, movetime=movetime)
        if r.move is None:
            break
        # Sample before making the move, from ply 8 on, skipping checks: an
        # in-check position has no meaningful static evaluation and the search
        # never asks for one.
        if plies >= 8 and plies % every == rng.randrange(every) % every \
                and not board.is_check():
            sampled.append(board.fen())
        board.push(r.move)
        plies += 1

    out = board.result(claim_draw=True)
    res = {"1-0": 1.0, "0-1": 0.0, "1/2-1/2": 0.5}.get(out)
    if res is None:                      # hit the ply cap: unresolved, unusable
        return []
    return [{"fen": f, "res": res} for f in sampled]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=8000)
    ap.add_argument("--workers", type=int, default=18)
    ap.add_argument("--movetime", type=float, default=0.05)
    ap.add_argument("--every", type=int, default=6, help="sample every N plies")
    ap.add_argument("--max-plies", type=int, default=300)
    ap.add_argument("--book", default=str(ROOT / "research/books/uho_1000.epd"))
    ap.add_argument("--seed", type=int, default=20260816)
    ap.add_argument("--out", default=str(ROOT / "research/data/texel6.jsonl"))
    a = ap.parse_args()

    starts = []
    with open(a.book) as fh:
        for line in fh:
            line = line.strip()
            if line:
                starts.append(" ".join(line.split()[:4]) + " 0 1")
    print(f"{len(starts)} book starts")

    rng = random.Random(a.seed)
    jobs = [(starts[i % len(starts)], rng.randrange(1 << 30),
             a.movetime, a.every, a.max_plies) for i in range(a.games)]

    n_pos = n_dec = done = 0
    with open(a.out, "w") as fh, mp.Pool(a.workers) as pool:
        for rows in pool.imap_unordered(_play, jobs, chunksize=4):
            done += 1
            for r in rows:
                fh.write(json.dumps(r) + "\n")
                n_pos += 1
                n_dec += (r["res"] != 0.5)
            if done % 200 == 0:
                print(f"  [{done}/{a.games}] games, {n_pos} positions "
                      f"({n_dec} from decisive games)", flush=True)
    print(f"wrote {n_pos} positions ({n_dec} decisive) to {a.out}")


if __name__ == "__main__":
    main()

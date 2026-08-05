"""A cheap screen for SEARCH changes: does it find the deep answer sooner?

**The gap this fills.** Evaluation changes have had a minutes-long screen since
the decisive-game loss work. Search changes have had nothing, so every one of
them costs an hour of games -- and the last three came back neutral, which is an
expensive way to learn nothing.

**Why not nodes-to-depth.** Because it is a cost measure, not a quality measure,
and this project has already been burned by it: LOG 2692 records a variant at
**-7% nodes to depth 7** that gated at **46%, -26 Elo**. A change can reach depth
N cheaply precisely by pruning away the lines that mattered. Time-to-depth has
the same defect (s26: it flatters Lazy SMP and picks the wrong thread count).

**What this measures instead.** Ground truth is *our own engine, given real
time*: for each position, the baseline's best move at a long think. A variant is
then scored on how often it finds that move at a short one. A pruning or
reduction change that is genuinely better arrives at the deep answer sooner; one
that merely prunes harder finds a different, worse move and is caught here for
seconds instead of an hour.

Deliberately self-referential. Agreement with *Stockfish* would import another
engine's preferences, and s2 established that optimising agreement with another
engine is anti-correlated with strength here.

**What it cannot see:** anything that improves the deep answer itself -- most
evaluation changes, and search changes whose benefit only appears beyond the
reference depth. Use the decisive-game loss screen for those. A search change
that passes this still earns a real gate; this only kills.

Usage:
  # one-off, ~20 min: build ground truth with the current engine
  PYTHONPATH=. .venv/bin/python research/search_screen.py build --positions 400
  # per variant, ~1 min:
  PYTHONPATH=. .venv/bin/python research/search_screen.py score <worktree>
"""
import argparse
import json
import os
import pathlib
import random
import subprocess
import sys

import chess

ROOT = pathlib.Path(__file__).parent.parent
TRUTH = ROOT / "research" / "data" / "search_truth.json"


def _positions(n, seed=5):
    rows = [json.loads(l) for l in open(ROOT / "research/data/texel5.jsonl")]
    random.Random(seed).shuffle(rows)
    out, seen = [], set()
    for r in rows:
        fen = r["fen"]
        if fen in seen:
            continue
        b = chess.Board(fen)
        if b.is_game_over() or len(list(b.legal_moves)) < 4:
            continue     # nothing to choose between
        seen.add(fen)
        out.append(fen)
        if len(out) >= n:
            break
    return out


def build(n, deep):
    os.environ["CC_THREADS"] = "1"
    sys.path.insert(0, str(ROOT))
    from engine.engine import Engine
    eng = Engine(use_book=False, use_tablebase=False)
    fens = _positions(n)
    truth = []
    for i, fen in enumerate(fens):
        r = eng.best_move(chess.Board(fen), movetime=deep)
        if r.move is None:
            continue
        truth.append({"fen": fen, "move": r.move.uci(), "score": r.score,
                      "depth": r.depth})
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(fens)}]", flush=True)
    TRUTH.write_text(json.dumps({"deep_movetime": deep, "n": len(truth),
                                 "items": truth}, indent=1))
    md = sum(t["depth"] for t in truth) / len(truth)
    print(f"wrote {TRUTH}: {len(truth)} positions, mean reference depth {md:.1f}")


def score(worktree, fast):
    truth = json.loads(TRUTH.read_text())
    code = f"""
import os, json, sys
os.environ["CC_THREADS"] = "1"
sys.path.insert(0, {worktree!r})
import chess
from engine.engine import Engine
eng = Engine(use_book=False, use_tablebase=False)
truth = json.load(open({str(TRUTH)!r}))
out = []
for t in truth["items"]:
    r = eng.best_move(chess.Board(t["fen"]), movetime={fast})
    out.append([r.move.uci() if r.move else "", r.score, r.depth])
print(json.dumps(out))
"""
    res = subprocess.run([str(ROOT / ".venv/bin/python"), "-c", code],
                         capture_output=True, text=True)
    if res.returncode:
        raise SystemExit(res.stderr[-2000:])
    got = json.loads(res.stdout)

    agree = 0
    lost = 0.0
    depth = 0.0
    for t, (mv, sc, d) in zip(truth["items"], got):
        if mv == t["move"]:
            agree += 1
        # how much the shallow choice gives up, in the DEEP search's own terms,
        # is not knowable without re-searching; report score drift as a proxy
        lost += abs(sc - t["score"])
        depth += d
    n = len(got)
    print(f"reference: {truth['n']} positions at {truth['deep_movetime']}s")
    print(f"agreement with the deep best move: {100*agree/n:.1f}%  ({agree}/{n})")
    print(f"mean |score - deep score|:         {lost/n:.1f}cp")
    print(f"mean depth reached at {fast}s:        {depth/n:.1f}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--positions", type=int, default=400)
    b.add_argument("--deep", type=float, default=3.0)
    s = sub.add_parser("score")
    s.add_argument("worktree")
    s.add_argument("--fast", type=float, default=0.1)
    a = p.parse_args()
    if a.cmd == "build":
        build(a.positions, a.deep)
    else:
        score(a.worktree, a.fast)


if __name__ == "__main__":
    main()

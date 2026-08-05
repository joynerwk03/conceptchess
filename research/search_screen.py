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

**Measured noise floor (2026-08-05).** Identical code, three runs at 400
positions: 2 and 6 discordant positions, paired difference +0.00 with intervals
of +-0.7 and +-1.2 points. Fixed-TIME search is not deterministic even
single-threaded, so this floor is real and had to be measured -- an instrument
whose noise is unknown is a random number generator with a confident voice. For
scale, the history-scaled LMR variant produced **77 discordant positions**,
twenty times the floor, so its reading was genuine behaviour rather than jitter.

**Resolution.** The interval scales as sqrt(discordant)/n. At ~19% discordance
400 positions give about +-4.3 points and 1800 give about +-2.

**VALIDATED, with known-stronger and known-weaker controls.** The obvious worry
about a self-referential reference is that the baseline is advantaged by
construction, so any variant that perturbs the search drifts from it regardless
of quality -- and the first batch of seven variants all reading -2.3 to -2.8
looked exactly like that. It is not what is happening. Running the baseline
itself at other time limits, which perturbs the search heavily while changing
strength in a known direction:

    baseline at 0.2s  (2x time, stronger)   11.2% discordant   +4.56 [+3.01, +6.10]
    baseline at 0.1s  (the reference point)      --                 0
    baseline at 0.05s (half time, weaker)   12.3% discordant   -5.06 [-6.67, -3.44]

Stronger reads positive, weaker reads negative, at discordance comparable to the
variants. The screen measures quality, not distance from the baseline.

**Rough calibration: ~12-13 Elo per agreement point.** Doubling or halving
thinking time at this speed is worth roughly +-60 Elo, against +4.56 and -5.06
points. Treat that as an order of magnitude, not a constant: a time change
perturbs every position uniformly, while a structural change hits particular
kinds of position, so the conversion need not be the same for both.

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


def score(worktree, fast, save="/tmp/search_screen_last.json"):
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

    MATE = 20000
    agree = 0
    drifts = []
    depth = 0.0
    matches = []
    for t, (mv, sc, d) in zip(truth["items"], got):
        hit = (mv == t["move"])
        matches.append(hit)
        agree += hit
        # Mate scores are on a different scale entirely -- one position where the
        # deep search saw mate and the shallow one did not contributes ~30000 and
        # swamps everything. The first version of this reported 3758cp mean drift
        # for exactly that reason, which is a number about nothing.
        if abs(sc) < MATE and abs(t["score"]) < MATE:
            drifts.append(abs(sc - t["score"]))
        depth += d
    n = len(got)
    drifts.sort()
    print(f"reference: {truth['n']} positions at {truth['deep_movetime']}s")
    print(f"agreement with the deep best move: {100*agree/n:.1f}%  ({agree}/{n})"
          f"   +-{196*(agree/n*(1-agree/n)/n)**0.5:.1f} (95%, unpaired)")
    if drifts:
        print(f"median |score - deep score|:       {drifts[len(drifts)//2]:.0f}cp"
              f"   ({len(drifts)} of {n} non-mate)")
    print(f"mean depth reached at {fast}s:        {depth/n:.1f}")

    out = pathlib.Path(save)
    out.write_text(json.dumps(matches))
    print(f"\nper-position hits written to {out} -- diff two runs with `compare`")
    print("for the PAIRED number, which is the only one that can resolve a")
    print("small change (positions both runs get right carry no information).")


def compare(a_path, b_path):
    """McNemar on two per-position hit vectors.

    Positions both builds get right, or both get wrong, carry no information
    about which is better -- only the DISCORDANT ones do. Comparing raw
    percentages throws that away and is why a 1.2-point gap looked like a
    reading when it was five positions of noise.
    """
    import math
    a = json.loads(pathlib.Path(a_path).read_text())
    b = json.loads(pathlib.Path(b_path).read_text())
    if len(a) != len(b):
        raise SystemExit("hit vectors are different lengths")
    b_only = sum(1 for x, y in zip(a, b) if not x and y)   # B fixed it
    a_only = sum(1 for x, y in zip(a, b) if x and not y)   # B broke it
    disc = a_only + b_only
    n = len(a)
    print(f"{n} positions, {disc} discordant "
          f"({100*disc/n:.1f}%) -- the rest carry no information")
    print(f"  B finds the deep move where A did not: {b_only}")
    print(f"  A finds it where B does not:           {a_only}")
    if disc == 0:
        print("\nidentical decisions: this change does not alter move choice here")
        return
    diff = (b_only - a_only) / n
    se = math.sqrt(disc) / n          # McNemar standard error of the difference
    lo, hi = 100 * (diff - 1.96 * se), 100 * (diff + 1.96 * se)
    print(f"\npaired difference: {100*diff:+.2f} points  95% [{lo:+.2f}, {hi:+.2f}]")
    if lo > 0:
        print("VERDICT: finds the deep move more often. Earns a real gate.")
    elif hi < 0:
        print("VERDICT: finds it LESS often. Kill without spending games.")
    else:
        print("VERDICT: not resolved here. This screen cannot see it; either")
        print("         enlarge the position set or spend the games.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--positions", type=int, default=400)
    b.add_argument("--deep", type=float, default=3.0)
    s = sub.add_parser("score")
    s.add_argument("worktree")
    s.add_argument("--fast", type=float, default=0.1)
    s.add_argument("--save", default="/tmp/search_screen_last.json")
    c = sub.add_parser("compare")
    c.add_argument("baseline_hits")
    c.add_argument("variant_hits")
    a = p.parse_args()
    if a.cmd == "build":
        build(a.positions, a.deep)
    elif a.cmd == "compare":
        compare(a.baseline_hits, a.variant_hits)
    else:
        score(a.worktree, a.fast, a.save)


if __name__ == "__main__":
    main()

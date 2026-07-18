"""Texel-style weight tuning: fit eval weights to game OUTCOMES.

Session 2's tuning failed because its target was eval-MSE vs Stockfish on
quiet positions — optimizing agreement with another engine's numbers, which
proved anti-correlated with playing strength. The Texel method fits the
logistic win probability of OUR OWN game results instead:

    L = mean over positions of (sigmoid(eval/K) - result)^2

where result is 1/0.5/0 from the game the position came from. That target is
grounded in what eval is FOR (predicting outcomes), and it historically works
where eval-matching fails.

Guardrails from the s2 lesson:
  * every weight is bounded to a chess-prior interval (default ±25% of the
    hand-set value) — unbounded tuning drifted into chess nonsense and lost
    matches despite better loss;
  * the tuned result must still win a UHO match gate before adoption.

Usage:
  # 1. generate self-play data (fast games from UHO openings)
  python -m research.texel gen --games 400 --movetime 0.04 --out research/data/texel.jsonl
  # 2. tune (writes proposed weights to research/data/texel_weights.json)
  python -m research.texel tune --data research/data/texel.jsonl --passes 6
"""

import argparse
import json
import math
import random
import sys
from pathlib import Path

import chess

ROOT = Path(__file__).parent.parent
BOOK = ROOT / "research" / "books" / "uho_1000.epd"


# ------------------------------------------------------------------ gen
def _balanced_starts(count, seed=7):
    """Random 6-ply walks screened by Stockfish to |eval| < 50cp: balanced,
    diverse starts. The v1 data used UHO (+1.0 for White) starts, which
    CONTAMINATED the outcome labels — White won because of the opening, and
    the tuner attributed that to whatever features correlated."""
    import shutil
    import chess.engine
    sf = chess.engine.SimpleEngine.popen_uci(shutil.which("stockfish"))
    rng = random.Random(seed)
    starts, seen = [], set()
    try:
        while len(starts) < count:
            b = chess.Board()
            for _ in range(6):
                ms = list(b.legal_moves)
                if not ms:      # random walk stumbled into mate/stalemate
                    break
                b.push(rng.choice(ms))
            if b.is_game_over() or b.fen() in seen:
                continue
            seen.add(b.fen())
            info = sf.analyse(b, chess.engine.Limit(depth=12))
            cp = info["score"].white().score(mate_score=10000)
            if cp is not None and abs(cp) < 50:
                starts.append(b.fen())
    finally:
        sf.quit()
    return starts


def gen(games, movetime, out):
    from engine.engine import Engine
    print("screening balanced starts with Stockfish...", flush=True)
    starts = _balanced_starts(max(200, games // 3))
    print(f"{len(starts)} balanced starts ready", flush=True)
    samples = 0
    with open(out, "w") as f:
        for g in range(games):
            board = chess.Board(starts[g % len(starts)])
            positions = []
            while not board.is_game_over(claim_draw=True) and len(board.move_stack) < 300:
                r = Engine(use_book=False).best_move(board, movetime=movetime)
                if r.move is None:
                    break
                board.push(r.move)
                # quiet filter: not in check AND the last two plies were
                # reversible (halfmove clock >= 2 means no capture/pawn move
                # just happened — cheap stand-in for qsearch-stability)
                if (len(board.move_stack) >= 8 and not board.is_check()
                        and board.halfmove_clock >= 2):
                    positions.append(board.fen())
            o = board.outcome(claim_draw=True)
            res = 0.5 if (o is None or o.winner is None) else (1.0 if o.winner else 0.0)
            # subsample: at most 20 positions per game to limit correlation
            random.Random(g).shuffle(positions)
            for fen in positions[:20]:
                f.write(json.dumps({"fen": fen, "res": res}) + "\n")
                samples += 1
            if (g + 1) % 20 == 0:
                print(f"[{g+1}/{games}] games, {samples} samples", flush=True)
    print(f"wrote {samples} samples to {out}")


# ------------------------------------------------------------------ tune
# Weights included in tuning, with prior bounds as (lo, hi) multipliers of
# the current value. Material stays FIXED (it anchors the scale); tempo and
# mate_drive stay fixed (special-purpose). Everything else gets ±25% unless
# chess sense says tighter.
TUNABLE = {
    "pst.pawn": (0.75, 1.25), "pst.knight": (0.75, 1.25), "pst.bishop": (0.75, 1.25),
    "pst.rook": (0.75, 1.25), "pst.queen": (0.75, 1.25), "pst.king": (0.75, 1.25),
    "pawn.doubled": (0.75, 1.25), "pawn.isolated": (0.75, 1.25),
    "pawn.passed_scale": (0.75, 1.25), "pawn.passed_eg_scale": (0.8, 1.2),
    "pawn.passer_king_dist": (0.75, 1.5), "pawn.connected_passer": (0.75, 1.25),
    "king.shield_gap": (0.75, 1.25), "king.open_file": (0.75, 1.25),
    "kattack.scale": (0.75, 1.25),
    "mob.knight": (0.75, 1.25), "mob.bishop": (0.75, 1.25),
    "mob.rook": (0.75, 1.25), "mob.queen": (0.75, 1.25),
    "act.bishop_pair": (0.75, 1.25), "act.rook_open": (0.75, 1.25),
    "act.rook_semi": (0.75, 1.25), "act.rook_seventh": (0.75, 1.25),
    "threat.hanging": (0.75, 1.5),
    "pawn.blocked_passer": (0.8, 1.2),
}


def _loss(evals, results, k):
    s = 0.0
    for e, r in zip(evals, results):
        p = 1.0 / (1.0 + 10.0 ** (-e / (k * 400.0)))
        s += (p - r) * (p - r)
    return s / len(evals)


def _eval_all(boards):
    from engine.evaluation import evaluate, clear_caches
    clear_caches()   # pawn/king caches bake weights in; W just changed
    return [evaluate(b) for b in boards]


# Original hand-set priors (frozen 2026-07-18): iterated flywheel spins use
# bounds relative to THESE, not to the current (already-tuned) values --
# otherwise +-25%-of-current compounds geometrically per spin and weights
# escape chess sense the way s2's unbounded tuning did.
ORIGINAL_PRIORS = {
    "pst.pawn": 1, "pst.knight": 1, "pst.bishop": 1, "pst.rook": 1,
    "pst.queen": 1, "pst.king": 1,
    "pawn.doubled": 15, "pawn.isolated": 12, "pawn.passed_scale": 1,
    "pawn.passed_eg_scale": 1.5, "pawn.passer_king_dist": 4,
    "pawn.connected_passer": 15, "pawn.blocked_passer": 0.5,
    "king.shield_gap": 12, "king.open_file": 15, "kattack.scale": 2.5,
    "mob.knight": 3.394, "mob.bishop": 3.507, "mob.rook": 2.338,
    "mob.queen": 1.169,
    "act.bishop_pair": 30, "act.rook_open": 20, "act.rook_semi": 10,
    "act.rook_seventh": 20, "threat.hanging": 0.1,
}
# widened once-and-for-all envelope vs the ORIGINAL priors
PRIOR_ENVELOPE = (0.5, 1.6)


def tune(data_path, passes):
    from engine import weights as wmod
    W = wmod.W
    rows = [json.loads(l) for l in open(data_path)]
    boards = [chess.Board(r["fen"]) for r in rows]
    results = [r["res"] for r in rows]
    print(f"{len(rows)} samples")

    evals = _eval_all(boards)
    # fit K (scale) first on the current eval
    best_k, best_kl = None, 1e9
    for k in [0.6, 0.8, 1.0, 1.2, 1.5, 2.0]:
        l = _loss(evals, results, k)
        if l < best_kl:
            best_k, best_kl = k, l
    print(f"K={best_k}  baseline loss {best_kl:.6f}")

    base = {k: W[k] for k in TUNABLE if k in W}
    current = dict(base)
    loss0 = best_kl
    for p in range(passes):
        improved = False
        for key in base:
            lo = base[key] * TUNABLE[key][0]
            hi = base[key] * TUNABLE[key][1]
            if key in ORIGINAL_PRIORS:   # hard envelope vs the hand priors
                lo = max(lo, ORIGINAL_PRIORS[key] * PRIOR_ENVELOPE[0])
                hi = min(hi, ORIGINAL_PRIORS[key] * PRIOR_ENVELOPE[1])
            step = max(abs(base[key]) * 0.05, 0.05)
            for cand in (current[key] + step, current[key] - step):
                cand = min(max(cand, lo), hi)
                if cand == current[key]:
                    continue
                W[key] = cand
                l = _loss(_eval_all(boards), results, best_k)
                if l < loss0 - 1e-7:
                    loss0 = l
                    current[key] = cand
                    improved = True
                    print(f"  pass {p+1}: {key} -> {cand:.3f}  loss {l:.6f}", flush=True)
                else:
                    W[key] = current[key]
        if not improved:
            break
    out = ROOT / "research" / "data" / "texel_weights.json"
    json.dump({"k": best_k, "baseline_loss": best_kl, "tuned_loss": loss0,
               "weights": current, "base": base}, open(out, "w"), indent=1)
    print(f"final loss {loss0:.6f} (baseline {best_kl:.6f}); wrote {out}")
    for k in current:
        if current[k] != base[k]:
            print(f"  {k}: {base[k]} -> {round(current[k],3)}")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen")
    g.add_argument("--games", type=int, default=400)
    g.add_argument("--movetime", type=float, default=0.04)
    g.add_argument("--out", default="research/data/texel.jsonl")
    t = sub.add_parser("tune")
    t.add_argument("--data", default="research/data/texel.jsonl")
    t.add_argument("--passes", type=int, default=6)
    a = p.parse_args()
    if a.cmd == "gen":
        gen(a.games, a.movetime, a.out)
    else:
        tune(a.data, a.passes)


if __name__ == "__main__":
    main()

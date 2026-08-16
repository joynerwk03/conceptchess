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
    # s22 threat terms + s23 endgame terms (untuned first guesses — widest bounds)
    "threat.pawn": (0.6, 1.5), "threat.minor": (0.6, 1.5), "threat.rook": (0.6, 1.5),
    "threat.initiative": (0.5, 1.6),
    "pawn.rook_behind_passer": (0.4, 1.6), "pawn.rook_behind_enemy_passer": (0.4, 1.6),
    # Phase 3 bundles A and D. LIVE in the engine but never in this table,
    # so the decisive-loss retune skipped them and they still carry values
    # fitted against the all-games objective.
    "minor.outpost_knight": (0.7, 1.4), "minor.behind_pawn": (0.5, 1.6),
    "minor.bishop_pawns": (0.7, 1.4), "minor.long_diagonal": (0.5, 1.6),
    "imbalance.rook_flat": (0.6, 1.5), "imbalance.knight_pawns": (0.0, 2.0),
    "imbalance.rook_pawns": (0.7, 1.4), "imbalance.rook_pair": (0.7, 1.4),
    "imbalance.knight_pair": (0.0, 2.0), "space.scale": (0.3, 2.0),
    "kattack.check_knight": (0.5, 1.8), "kattack.check_bishop": (0.0, 2.0),
    "kattack.check_rook": (0.5, 1.8), "kattack.check_queen": (0.5, 1.8),
    "kattack.queenless_discount": (0.0, 1.7),
    "kattack.weak_zone": (0.0, 4.0),
    "pawn.path_clear": (0.0, 4.0), "pawn.path_defended": (0.0, 4.0),
    "pawn.path_attacked": (0.0, 4.0),
    "scale.no_pawns": (0.0, 1.3), "scale.wrong_bishop": (0.0, 1.1),
    # Correctness fixed by chess, not by outcome prediction. A draw scale
    # above 1.0 would AMPLIFY a drawish ending, and the mate-drive terms fire
    # only in already-won positions where the label is 1.0 whatever happens,
    # so the loss cannot constrain them and a free fit inverts the gradient.
    "ocb.draw_scale": (0.4, 1.15),
    "mate_drive.corner": (0.6, 1.4), "mate_drive.king_prox": (0.6, 1.4),
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


# How far an ENDGAME value may sit from its middlegame partner. Deliberately
# wide: the entire point of tapering is that some terms are worth very different
# amounts in the two phases (Stockfish 11 rates a pawn 128 in the middlegame and
# 213 in the endgame, a factor of 1.7), and a narrow bound would only rediscover
# the single averaged value the tuner has been stuck on for three sessions.
EG_ENVELOPE = (0.4, 2.0)


def tune(data_path, passes, sample=0, seed=11, tune_eg=True, only=None):
    from engine import weights as wmod
    W = wmod.W
    rows = [json.loads(l) for l in open(data_path)]
    if sample and sample < len(rows):
        random.Random(seed).shuffle(rows)
        rows = rows[:sample]
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
    if only:
        # Isolate a new bundle: hold the settled eval fixed and ask what the new
        # terms are worth GIVEN it. Tuning everything at once answers a
        # different question, because the old weights absorb the new terms'
        # signal and the result no longer says whether the new terms earn their
        # place. s27 used this to find that bundle A's Stockfish-scaled priors
        # were ~2x too large and that one of them was worth exactly zero.
        base = {k: v for k, v in base.items() if any(k.startswith(p) for p in only)}
        if not base:
            raise SystemExit(f"--only {only} matched no tunable weight")
    current = dict(base)
    # Endgame partners. They start EQUAL to the middlegame value, which is what
    # W_EG being empty already means, so the first loss evaluation is unchanged.
    eg_current = {k: base[k] for k in base} if tune_eg else {}

    # One flat parameter list: ("mg", key) and ("eg", key).
    params = [("mg", k) for k in base] + [("eg", k) for k in eg_current]
    print(f"tuning {len(params)} parameters "
          f"({len(base)} middlegame + {len(eg_current)} endgame)")

    def apply(kind, key, value):
        if kind == "mg":
            W[key] = value
        else:
            wmod.W_EG[key] = value

    loss0 = best_kl
    for p in range(passes):
        improved = False
        for kind, key in params:
            cur = current[key] if kind == "mg" else eg_current[key]
            if kind == "mg":
                lo = base[key] * TUNABLE[key][0]
                hi = base[key] * TUNABLE[key][1]
                if key in ORIGINAL_PRIORS:   # hard envelope vs the hand priors
                    lo = max(lo, ORIGINAL_PRIORS[key] * PRIOR_ENVELOPE[0])
                    hi = min(hi, ORIGINAL_PRIORS[key] * PRIOR_ENVELOPE[1])
            else:
                lo = base[key] * EG_ENVELOPE[0]
                hi = base[key] * EG_ENVELOPE[1]
            if lo > hi:
                lo, hi = hi, lo
            step = max(abs(base[key]) * 0.05, 0.05)
            for cand in (cur + step, cur - step):
                cand = min(max(cand, lo), hi)
                if cand == cur:
                    continue
                apply(kind, key, cand)
                l = _loss(_eval_all(boards), results, best_k)
                if l < loss0 - 1e-7:
                    loss0 = l
                    if kind == "mg":
                        current[key] = cand
                    else:
                        eg_current[key] = cand
                    cur = cand
                    improved = True
                    print(f"  pass {p+1}: {key}[{kind}] -> {cand:.3f}  loss {l:.6f}",
                          flush=True)
                else:
                    apply(kind, key, cur)
        if not improved:
            break

    # Only keep endgame values that actually moved away from their partner:
    # an entry equal to the middlegame value is what "absent" already means, and
    # writing it would add cost for nothing.
    eg_out = {k: v for k, v in eg_current.items() if v != current[k]}
    out = ROOT / "research" / "data" / "texel_weights.json"
    json.dump({"k": best_k, "baseline_loss": best_kl, "tuned_loss": loss0,
               "weights": current, "weights_eg": eg_out, "base": base},
              open(out, "w"), indent=1)
    print(f"final loss {loss0:.6f} (baseline {best_kl:.6f}); wrote {out}")
    for k in current:
        if current[k] != base[k]:
            print(f"  {k}: {base[k]} -> {round(current[k],3)}")
    for k, v in eg_out.items():
        print(f"  {k}[eg]: {round(current[k],3)} (mg) -> {round(v,3)} (eg)  "
              f"ratio {v / current[k]:.2f}" if current[k] else f"  {k}[eg] -> {v}")


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
    t.add_argument("--sample", type=int, default=0,
                   help="use at most this many positions (0 = all)")
    t.add_argument("--only", default="",
                   help="tune only weights whose key starts with one of "
                        "these comma-separated prefixes; isolates a new "
                        "bundle against a frozen eval")
    t.add_argument("--no-eg", action="store_true",
                   help="tune middlegame values only (the pre-tapering behaviour)")
    a = p.parse_args()
    if a.cmd == "gen":
        gen(a.games, a.movetime, a.out)
    else:
        tune(a.data, a.passes, sample=a.sample, tune_eg=not a.no_eg,
             only=[x for x in a.only.split(",") if x])


if __name__ == "__main__":
    main()

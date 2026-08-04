"""Screen a bundle on outcome loss alone: minutes instead of an hour of games.

From the 2026-08-04 calibration: ~8-9 Elo per 1% of outcome-loss reduction, and
an 800-game gate resolves +-19 Elo. So games cannot see anything under ~2.5%,
and every bundle measured so far is worth 0.1-0.8%. Loss is the instrument that
can actually resolve them.

Two rules this encodes, both learned the expensive way:
  * measure against the bundle switched OFF, not against its own priors -- a
    tune started from bad guesses mostly measures the guesses (bundle C);
  * run enough passes that the weights stop moving, and say so when they
    have not (bundle A's first tune reported a step limit as an optimum).

Usage:  screen_loss.py <worktree> <weight-prefix>[,<prefix>...]
"""
import json
import random
import sys

import chess

WT = sys.argv[1]
PREFIXES = sys.argv[2].split(",")
SAMPLE = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
PASSES = int(sys.argv[4]) if len(sys.argv) > 4 else 40

sys.path.insert(0, WT)

from engine import weights as wmod  # noqa: E402
from engine.evaluation import evaluate, clear_caches  # noqa: E402
from research.texel import TUNABLE  # noqa: E402

rows = [json.loads(l) for l in open(WT + "/research/data/texel5.jsonl")]
random.Random(11).shuffle(rows)
rows = rows[:SAMPLE]
boards = [chess.Board(r["fen"]) for r in rows]
results = [r["res"] for r in rows]

keys = [k for k in wmod.W if any(k.startswith(p) for p in PREFIXES)]
if not keys:
    raise SystemExit(f"no weights match {PREFIXES}")
priors = {k: wmod.W[k] for k in keys}


def loss(k):
    clear_caches()
    evs = [evaluate(b) for b in boards]
    s = 0.0
    for e, r in zip(evs, results):
        p = 1.0 / (1.0 + 10.0 ** (-e / (k * 400.0)))
        s += (p - r) * (p - r)
    return s / len(evs)


# K is fitted with the bundle OFF and then held, so every number below is on one
# scale and "loss went down" cannot be an artefact of refitting the scale.
for k in keys:
    wmod.W[k] = 0.0
best_k, off = None, 1e9
for k in (0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
    l = loss(k)
    if l < off:
        best_k, off = k, l
print(f"{len(rows)} samples, K={best_k}")
print(f"bundle OFF        {off:.6f}")

for k, v in priors.items():
    wmod.W[k] = v
print(f"at priors         {loss(best_k):.6f}")

# Coordinate descent on the bundle's weights only, everything else frozen.
cur = dict(priors)
best = loss(best_k)
moved_last_pass = {}
for p in range(PASSES):
    improved = False
    for k in keys:
        # Default bounds are wide AND SYMMETRIC about zero, because for a new
        # term the sign is exactly what is unknown -- a "penalty" prior that is
        # really a bonus cannot be discovered from a one-sided interval, and a
        # weight pinned at its bound is as uninformative as one pinned by the
        # step size. Anything that runs to a large value still has to survive a
        # chess-sense read before it is believed: s2's unbounded tune drifted
        # into nonsense with a better loss.
        if k in TUNABLE:
            lo, hi = priors[k] * TUNABLE[k][0], priors[k] * TUNABLE[k][1]
        else:
            hi = 8.0 * abs(priors[k])
            lo = -hi
        if lo > hi:
            lo, hi = hi, lo
        step = max(abs(priors[k]) * 0.05, 0.05)
        for cand in (cur[k] + step, cur[k] - step):
            cand = min(max(cand, lo), hi)
            if cand == cur[k]:
                continue
            wmod.W[k] = cand
            l = loss(best_k)
            if l < best - 1e-9:
                best, cur[k], improved = l, cand, True
                moved_last_pass[k] = p
            else:
                wmod.W[k] = cur[k]
    if not improved:
        print(f"converged after {p+1} passes")
        break
else:
    still = [k for k, p in moved_last_pass.items() if p >= PASSES - 2]
    if still:
        print(f"!! NOT CONVERGED -- still moving at the last pass: {still}")
        print("!! This is a step limit, not an optimum. Re-run with more passes.")

print(f"tuned             {best:.6f}   ({100*(off-best)/off:+.3f}% vs OFF)")
print()
for k in keys:
    print(f"  {k:32s} {priors[k]:8.3f} -> {cur[k]:8.3f}")
print()
gain = 100 * (off - best) / off
print(f"VERDICT: {gain:+.3f}% loss. At ~8-9 Elo per 1%, about {8.5*gain:+.1f} Elo.")
print("An 800-game gate resolves +-19 Elo, so this is "
      + ("worth stacking onto phase3." if gain >= 0.3 else
         "below what games can see -- stack only if it is free."))

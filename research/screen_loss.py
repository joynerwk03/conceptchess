"""Screen a bundle on DECISIVE-GAME outcome loss: minutes instead of an hour of games.

**Read this before trusting a number out of here.** Loss over *all* games is a
forecasting metric and it does not predict Elo. Measured on two changes with real
external gates:

    phase3 stack   all-games +2.472%   decisive +2.737%   ->  +12.8 Elo
    phase4         all-games +2.376%   decisive -0.615%   ->   +1.1 Elo

The all-games column is inconsistent by a factor of ten and predicted +11 for a
change worth +1. Positions from **drawn** games carry no information about
whether a change helps you win: scoring a dead-drawn ending as 0.00 instead of
+170 is a huge improvement in prediction and no improvement in result. So this
screens on decisive games only, where **~4.7 Elo per 1%** predicted the phase3
stack to within 0.1 Elo.

An 800-game gate resolves +-19 Elo, so games cannot see anything under ~4% of
decisive loss, and every bundle measured so far is worth a fraction of that.
Loss is the instrument that can actually resolve them; games are for
accumulations.

Three rules this encodes, all learned the expensive way:
  * measure against the bundle switched OFF, not against its own priors -- a
    tune started from bad guesses mostly measures the guesses (bundle C);
  * run enough passes that the weights stop moving, and say so when they
    have not (bundle A's first tune reported a step limit as an optimum);
  * judge on decisive games, or a term that merely predicts draws better will
    look like the best result you have ever had (phase4).

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
# Decisive games only. A drawn game's positions cannot tell you whether a change
# helps you win, and including them is what made phase4 look like +11 Elo when
# it was worth +1. See the module docstring.
_all = len(rows)
rows = [r for r in rows if r["res"] != 0.5]
print(f"{len(rows)} of {_all} sampled positions come from DECISIVE games "
      f"(draws carry no decision information)")
boards = [chess.Board(r["fen"]) for r in rows]
results = [r["res"] for r in rows]

keys = [k for k in wmod.W if any(k.startswith(p) for p in PREFIXES)]
if not keys:
    raise SystemExit(f"no weights match {PREFIXES}")
priors = {k: wmod.W[k] for k in keys}


def _evals():
    clear_caches()
    return [evaluate(b) for b in boards]


def _loss_of(evs, k):
    s = 0.0
    for e, r in zip(evs, results):
        p = 1.0 / (1.0 + 10.0 ** (-e / (k * 400.0)))
        s += (p - r) * (p - r)
    return s / len(evs)


def loss_at(k):
    return _loss_of(_evals(), k)


# K is REFITTED for every candidate, which is the only way these numbers mean
# anything. The previous version fitted K once with the bundle off and held it,
# on the reasoning that one fixed scale keeps the comparison honest. That is
# backwards: with K held, multiplying the whole evaluation by a constant lowers
# the loss while changing no move the search would ever make -- at K=0.6 a
# factor of 1.2 is worth +0.751% of nothing. A bundle of pure bonuses inflates
# the eval by construction, so the old harness paid it for that alone.
# Refitting K makes a pure rescale worth exactly zero.
#
# The grid also had to be extended DOWNWARD: it started at 0.6 and 0.6 was
# chosen every time, i.e. the answer was pinned to the edge of the search. The
# real optimum on this data is nearer 0.46.
KGRID = (0.30, 0.34, 0.38, 0.42, 0.46, 0.50, 0.54, 0.60, 0.70, 0.80, 1.0, 1.2)


def loss():
    """Loss at the best K for THIS evaluation -- scale-invariant by construction.

    Evaluates the positions ONCE and reuses that vector across the grid; the
    naive version re-ran the whole evaluation per K and made the screen twelve
    times slower for no extra information.
    """
    evs = _evals()
    return min(_loss_of(evs, k) for k in KGRID)


for k in keys:
    wmod.W[k] = 0.0
off = loss()
best_k = min(KGRID, key=loss_at)
print(f"{len(rows)} samples, K refitted per candidate (K={best_k} with bundle off)")
print(f"bundle OFF        {off:.6f}")

for k, v in priors.items():
    wmod.W[k] = v
print(f"at priors         {loss():.6f}")

# Coordinate descent on the bundle's weights only, everything else frozen.
cur = dict(priors)
best = loss()
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
            l = loss()
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
print(f"VERDICT: {gain:+.3f}% loss. At ~4.7 Elo per 1% of DECISIVE loss, about {4.7*gain:+.1f} Elo.")
print("An 800-game gate resolves +-19 Elo, so this is "
      + ("worth stacking; games are for the accumulation." if gain >= 0.3 else
         "below what games can see -- stack only if it is free."))

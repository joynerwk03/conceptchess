"""Does bundle C add anything, once its weights are honest?

The tune reported a 0.325% loss improvement, but its baseline was the eval with
my *guessed* priors already active and making things worse -- so most of that
figure is the tuner undoing my guesses, not the terms earning their place. The
question that matters is the one comparison the tune never made:

    all four weights at ZERO  (exactly the pre-bundle engine)
        versus
    all four at their tuned values

on the same positions and the same K.
"""
import json
import random
import sys

import chess

WT = ("/home/joynerwk03/mission-control/projects/conceptchess"
      "/research/worktrees/dev_bundleC")
sys.path.insert(0, WT)

from engine import weights as wmod  # noqa: E402
from engine.evaluation import evaluate, clear_caches  # noqa: E402

DATA = WT + "/research/data/texel5.jsonl"
rows = [json.loads(l) for l in open(DATA)]
random.Random(11).shuffle(rows)
rows = rows[:20000]
boards = [chess.Board(r["fen"]) for r in rows]
results = [r["res"] for r in rows]


def loss(k):
    clear_caches()
    evs = [evaluate(b) for b in boards]
    s = 0.0
    for e, r in zip(evs, results):
        p = 1.0 / (1.0 + 10.0 ** (-e / (k * 400.0)))
        s += (p - r) * (p - r)
    return s / len(evs)


SETTINGS = {
    "bundle C OFF (the pre-bundle engine)":
        {"kattack.safe_check": 0.0, "kattack.weak_ring": 0.0,
         "kattack.pawnless_flank": 0.0, "kattack.eg_linear": 0.0},
    "bundle C at my guessed priors":
        {"kattack.safe_check": 3.0, "kattack.weak_ring": 2.0,
         "kattack.pawnless_flank": 6.0, "kattack.eg_linear": 1.0},
    "bundle C TUNED":
        {"kattack.safe_check": 3.0, "kattack.weak_ring": 0.4,
         "kattack.pawnless_flank": 0.0, "kattack.eg_linear": 0.0},
    "safe_check alone":
        {"kattack.safe_check": 3.0, "kattack.weak_ring": 0.0,
         "kattack.pawnless_flank": 0.0, "kattack.eg_linear": 0.0},
}

# Fit K once on the OFF setting so every row is scored on the same scale.
for k_, v in SETTINGS["bundle C OFF (the pre-bundle engine)"].items():
    wmod.W[k_] = v
best_k, best_l = None, 1e9
for k in (0.6, 0.8, 1.0, 1.2, 1.5, 2.0):
    l = loss(k)
    if l < best_l:
        best_k, best_l = k, l
print(f"{len(rows)} samples, K={best_k}\n")

print(f"{'setting':44s} {'loss':>10s} {'vs OFF':>10s}")
print("-" * 66)
off = None
for name, vals in SETTINGS.items():
    for k_, v in vals.items():
        wmod.W[k_] = v
    l = loss(best_k)
    if off is None:
        off = l
    print(f"{name:44s} {l:10.6f} {100*(off-l)/off:+9.3f}%")

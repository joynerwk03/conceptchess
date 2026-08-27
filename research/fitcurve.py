"""Fit the mobility curves from cached features: gradient descent, held out, regularised.

With (R, scale, f, phase) cached per position the evaluation is LINEAR in the
weights:

    eval = scale*R + SUM_k ( mg_k * scale*phase*f_k + eg_k * scale*(1-phase)*f_k )

so the Texel loss has a closed-form gradient and the whole fit is a few matrix
products instead of 2*N*passes sweeps of the dataset.

Two guards against the failure this is meant to fix. The first mobility fit
gained +1.566% loss on 10K positions and screened WORSE, which is overfitting:

  * **HELD-OUT SPLIT.** Reported loss is on positions the fit never saw. An
    in-sample number cannot detect overfitting and is the number that misled the
    first attempt. The split is by stride rather than by game -- this data has no
    game ids, and the LOG is explicit that position-level splits leave the same
    game on both sides -- so treat the holdout as optimistic, not clean.

  * **L2 TOWARD THE LINEAR SEED.** The prior is the current linear curve, so the
    fit must pay to bend and bends only where the data insists. That is the same
    discipline as the tuner's chess-prior envelopes, which exist because
    unbounded tuning "drifted into chess nonsense and lost matches despite
    better loss".

K is refit on the holdout after the weights settle, because CLAUDE.md records a
boundary-solution K that overstated every bundle before it by ~25%.
"""
import json
import math
import pathlib
import sys

import numpy as np

FEAT = pathlib.Path("/home/joynerwk03/ccruns/mobfeat.json")
LAM = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
ITERS = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

blob = json.loads(FEAT.read_text())
keys = blob["keys"]
S = blob["samples"]
n, m = len(S), len(keys)

F = np.array([s[0] for s in S], dtype=np.float64)          # (n, m) counts
ph = np.array([s[1] for s in S], dtype=np.float64)[:, None]
sc = np.array([s[2] for s in S], dtype=np.float64)[:, None]
R = np.array([s[3] for s in S], dtype=np.float64)
res = np.array([s[4] for s in S], dtype=np.float64)

Gmg = sc * ph * F                 # d eval / d mg_k
Geg = sc * (1.0 - ph) * F         # d eval / d eg_k
base = sc[:, 0] * R               # the part the mobility weights do not touch

sys.path.insert(0, "/home/joynerwk03/mission-control/projects/conceptchess")
from engine.weights import W, W_EG                                  # noqa: E402
w0 = np.array([float(W[k]) for k in keys])
e0 = np.array([float(W_EG.get(k, W[k])) for k in keys])

hold = np.zeros(n, dtype=bool)
hold[::5] = True                  # 20% held out
tr = ~hold


def loss(mg, eg, K, mask):
    ev = base[mask] + Gmg[mask] @ mg + Geg[mask] @ eg
    sig = 1.0 / (1.0 + np.exp(-ev / (K * 400.0)))
    return float(np.mean((sig - res[mask]) ** 2))


def fit_K(mg, eg, mask):
    best, bk = 1e9, 1.0
    for K in np.arange(0.30, 1.60, 0.02):
        l = loss(mg, eg, K, mask)
        if l < best:
            best, bk = l, float(K)
    return bk, best


K, _ = fit_K(w0, e0, tr)
print(f"{n} samples ({int(tr.sum())} train / {int(hold.sum())} holdout), "
      f"{m} curve entries, K={K:.2f}, lambda={LAM}")
print(f"  seed   train {loss(w0,e0,K,tr):.8f}   HOLDOUT {loss(w0,e0,K,hold):.8f}")

mg, eg = w0.copy(), e0.copy()
# Backtracking line search. The first attempt used a fixed step scaled by a
# hand-picked 1e4 and diverged to NaN within a thousand iterations; the loss is
# nearly linear here, so the right step size is not guessable and must be found.
step = 1.0
cur = loss(mg, eg, K, tr)
for it in range(ITERS):
    ev = base[tr] + Gmg[tr] @ mg + Geg[tr] @ eg
    sig = 1.0 / (1.0 + np.exp(-ev / (K * 400.0)))
    d = 2.0 * (sig - res[tr]) * sig * (1.0 - sig) / (K * 400.0)
    gmg = Gmg[tr].T @ d / tr.sum() + 2.0 * LAM * (mg - w0) / m
    geg = Geg[tr].T @ d / tr.sum() + 2.0 * LAM * (eg - e0) / m
    gn = math.sqrt(float(gmg @ gmg + geg @ geg))
    if not math.isfinite(gn) or gn < 1e-15:
        break
    gmg, geg = gmg / gn, geg / gn          # unit direction; step carries the scale
    while step > 1e-6:
        cand_mg, cand_eg = mg - step * gmg, eg - step * geg
        l = loss(cand_mg, cand_eg, K, tr)
        if math.isfinite(l) and l < cur:
            mg, eg, cur = cand_mg, cand_eg, l
            step *= 1.3
            break
        step *= 0.5
    else:
        break
    if (it + 1) % 500 == 0:
        K, _ = fit_K(mg, eg, tr)
        cur = loss(mg, eg, K, tr)
        print(f"  iter {it+1:5d}  train {cur:.8f}   "
              f"HOLDOUT {loss(mg,eg,K,hold):.8f}   K={K:.2f}  step={step:.4g}", flush=True)

K, _ = fit_K(mg, eg, tr)
base_h = loss(w0, e0, K, hold)
new_h = loss(mg, eg, K, hold)
print(f"\nHOLDOUT: {base_h:.8f} -> {new_h:.8f}  ({100*(base_h-new_h)/base_h:+.3f}%)")
if not (math.isfinite(new_h) and math.isfinite(base_h)) or new_h >= base_h:
    print("  no holdout gain -- the curve is not learnable from this data; NOT writing")
    raise SystemExit(0)

out = {"weights": {k: float(v) for k, v in zip(keys, mg)},
       "weights_eg": {k: float(v) for k, v in zip(keys, eg)},
       "k": K, "baseline_loss": base_h, "tuned_loss": new_h}
p = pathlib.Path("/home/joynerwk03/ccruns/mobcurve_fit.json")
p.write_text(json.dumps(out, indent=1))
print(f"  wrote {p}")
for pc, mx in (("knight", 8), ("bishop", 13), ("rook", 14), ("queen", 27)):
    row = [round(out["weights"][f"mob.{pc}.{i}"], 1) for i in range(mx + 1)]
    print(f"  {pc:<7} {row}")

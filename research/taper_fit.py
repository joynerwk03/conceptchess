"""Fit the 17 untapered weights as (MG, EG) pairs, and report HELD-OUT loss.

Model, exact (linearity verified at 0.000000 cp over 4000 positions):

    eval = base - SUM_k c_k + SUM_k ( c_k*p * m_k  +  c_k*(1-p) * e_k )

with p the phase (1.0 = opening) and m_k = e_k = 1 reproducing today's eval
exactly, so the fit starts at the baseline and any gain is measured from zero.
Recovered weights are mg_k = W[k]*m_k, eg_k = W[k]*e_k.

Three rules from this project, all of which have burned a previous fit:

  * HOLD OUT. Every eval fit in this project's history reports in-sample loss.
    Mobility gained +1.566% in-sample and +0.008% held out. The holdout is a
    trailing BLOCK, not a stride: this data is self-play sampled every few
    plies, so adjacent lines are the same game and a stride would put one game
    on both sides.
  * REFIT K for every candidate. The loss is sigmoid(eval/(K*400)), so with K
    fixed, scaling the whole eval lowers the loss while changing no move.
  * L2 toward the seed, as the mobility refit needed, so the fit prefers the
    straight line unless the data pays for the bend.
"""
import math
import sys

import numpy as np

LN10 = math.log(10.0)


def loss(ev, res, k):
    p = 1.0 / (1.0 + np.power(10.0, -ev / (k * 400.0)))
    d = p - res
    return float(np.mean(d * d))


def best_k(ev, res):
    grid = [0.4, 0.5, 0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0]
    ls = [loss(ev, res, k) for k in grid]
    i = int(np.argmin(ls))
    if i in (0, len(grid) - 1):
        print(f"  WARNING: K={grid[i]} is on the edge of the grid", flush=True)
    return grid[i], ls[i]


def main():
    d = np.load(sys.argv[1], allow_pickle=True)
    keys = [str(x) for x in d["keys"]]
    base, ph, res, c = d["base"], d["phase"], d["res"], d["c"]
    n, nk = c.shape
    print(f"{n:,} positions, {nk} keys", flush=True)

    # X = [c*p | c*(1-p)], theta = [m | e], offset = base - sum(c)
    X = np.hstack([c * ph[:, None], c * (1.0 - ph)[:, None]])
    off = base - c.sum(axis=1)

    cut = int(n * 0.8)
    Xtr, otr, rtr = X[:cut], off[:cut], res[:cut]
    Xho, oho, rho = X[cut:], off[cut:], res[cut:]
    print(f"train {cut:,}   holdout {n - cut:,} (trailing block)", flush=True)

    th = np.ones(2 * nk)
    k0, ltr0 = best_k(otr + Xtr @ th, rtr)
    kh0, lho0 = best_k(oho + Xho @ th, rho)
    print(f"baseline: K={k0} train {ltr0:.6f} | K={kh0} holdout {lho0:.6f}", flush=True)

    LAM = 1e-4          # L2 toward the seed (m = e = 1)
    step = 1e-3
    k = k0
    for it in range(60):
        ev = otr + Xtr @ th
        p = 1.0 / (1.0 + np.power(10.0, -ev / (k * 400.0)))
        g = Xtr.T @ (2.0 * (p - rtr) * p * (1.0 - p) * LN10 / (k * 400.0)) / len(rtr)
        g += 2.0 * LAM * (th - 1.0)
        gn = float(np.linalg.norm(g))
        if not math.isfinite(gn) or gn == 0.0:
            print(f"  stop at iter {it}: gradient not finite/zero")
            break
        cur = loss(ev, rtr, k) + LAM * float(np.sum((th - 1.0) ** 2))
        # backtracking line search; a hand-picked step diverged to NaN once and
        # the guard `new <= cur` passed silently for NaN, so test isfinite too.
        s = step
        for _ in range(40):
            cand = th - s * g
            nl = loss(otr + Xtr @ cand, rtr, k) + LAM * float(np.sum((cand - 1.0) ** 2))
            if math.isfinite(nl) and nl < cur:
                th = cand
                step = s * 2.0
                break
            s *= 0.5
        else:
            print(f"  converged at iter {it}")
            break
        k, _ = best_k(otr + Xtr @ th, rtr)

    ktr, ltr = best_k(otr + Xtr @ th, rtr)
    kho, lho = best_k(oho + Xho @ th, rho)
    gtr = 100.0 * (ltr0 - ltr) / ltr0
    gho = 100.0 * (lho0 - lho) / lho0
    print(f"\nfitted:   K={ktr} train {ltr:.6f} ({gtr:+.3f}%) | "
          f"K={kho} holdout {lho:.6f} ({gho:+.3f}%)", flush=True)
    print(f"\n>>> HELD-OUT GAIN: {gho:+.3f}%   (in-sample {gtr:+.3f}%)\n")

    print(f"{'key':32s}{'seed':>10}{'MG':>10}{'EG':>10}")
    seedv = {}
    for i, kk in enumerate(keys):
        m, e = th[i], th[nk + i]
        seedv[kk] = (m, e)
        print(f"{kk:32s}{1.0:>10.3f}{m:>10.3f}{e:>10.3f}")
    np.savez(sys.argv[2], keys=np.array(keys), m=th[:nk], e=th[nk:])


if __name__ == "__main__":
    main()

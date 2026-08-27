"""Refit the taper against SF11 labels instead of our own game results.

Same exact linear model as taper_fit.py; only the TARGET changes. Two properties
of an external target that the self-play one lacked:

  * It is not our own opinion, so a fit cannot win by reproducing our blind
    spots. This is the whole point -- see the LOG entry.
  * K stops being a free lunch. With game-result labels, scaling the whole eval
    lowers the loss while changing no move, so K had to be refitted for every
    candidate. Against a FIXED external target, scaling our eval moves the
    prediction away from the target, so that pathology disappears. K is
    therefore fixed at the value fitted for the BASELINE on this data.

Loss, in the same probability space the Texel loss uses so numbers stay
comparable:

    L = mean ( sigmoid(eval/(K*400)) - sigmoid(sf11/(K*400)) )^2

Alignment: features and labels are both produced by reading the same file in
order with contiguous chunks concatenated in order, and neither dropped a row
(382,339 in, 382,339 out both times). Asserted, not assumed.
"""
import json
import math
import sys

import numpy as np

LN10 = math.log(10.0)
K = 0.8          # baseline's fitted K on this data


def sig(x):
    return 1.0 / (1.0 + np.power(10.0, -x / (K * 400.0)))


def main():
    d = np.load(sys.argv[1], allow_pickle=True)
    keys = [str(x) for x in d["keys"]]
    base, ph, c = d["base"], d["phase"], d["c"]
    n, nk = c.shape

    sf, res = [], []
    with open(sys.argv[2]) as fh:
        for ln in fh:
            r = json.loads(ln)
            sf.append(r["sf"])
            res.append(r["res"])
    sf = np.array(sf, dtype=np.float64)
    assert len(sf) == n, f"MISALIGNED: {len(sf)} labels vs {n} feature rows"
    # the labels must be the same positions, in order: res came along for the
    # ride in both files, so it is a free consistency check
    assert np.allclose(np.array(res), d["res"]), "MISALIGNED: res mismatch"
    print(f"{n:,} positions, {nk} keys, aligned", flush=True)

    tgt = sig(sf)
    X = np.hstack([c * ph[:, None], c * (1.0 - ph)[:, None]])
    off = base - c.sum(axis=1)

    cut = int(n * 0.8)
    Xtr, otr, ttr = X[:cut], off[:cut], tgt[:cut]
    Xho, oho, tho = X[cut:], off[cut:], tgt[cut:]

    def loss(Xm, o, t, th):
        dv = sig(o + Xm @ th) - t
        return float(np.mean(dv * dv))

    th = np.ones(2 * nk)
    ltr0, lho0 = loss(Xtr, otr, ttr, th), loss(Xho, oho, tho, th)
    print(f"baseline vs SF11: train {ltr0:.6f}  holdout {lho0:.6f}", flush=True)

    LAM = 1e-4
    step = 1e-3
    for it in range(80):
        ev = otr + Xtr @ th
        p = sig(ev)
        g = Xtr.T @ (2.0 * (p - ttr) * p * (1.0 - p) * LN10 / (K * 400.0)) / len(ttr)
        g += 2.0 * LAM * (th - 1.0)
        gn = float(np.linalg.norm(g))
        if not math.isfinite(gn) or gn == 0.0:
            print(f"  stop at iter {it}: gradient not finite/zero")
            break
        cur = loss(Xtr, otr, ttr, th) + LAM * float(np.sum((th - 1.0) ** 2))
        s = step
        for _ in range(40):
            cand = th - s * g
            nl = loss(Xtr, otr, ttr, cand) + LAM * float(np.sum((cand - 1.0) ** 2))
            if math.isfinite(nl) and nl < cur:
                th = cand
                step = s * 2.0
                break
            s *= 0.5
        else:
            print(f"  converged at iter {it}")
            break

    ltr, lho = loss(Xtr, otr, ttr, th), loss(Xho, oho, tho, th)
    gtr = 100.0 * (ltr0 - ltr) / ltr0
    gho = 100.0 * (lho0 - lho) / lho0
    print(f"fitted   vs SF11: train {ltr:.6f} ({gtr:+.3f}%)  "
          f"holdout {lho:.6f} ({gho:+.3f}%)")
    print(f"\n>>> HELD-OUT GAIN vs SF11 LABELS: {gho:+.3f}%\n")
    print(f"{'key':32s}{'MG':>10}{'EG':>10}")
    for i, kk in enumerate(keys):
        print(f"{kk:32s}{th[i]:>10.3f}{th[nk + i]:>10.3f}")
    np.savez(sys.argv[3], keys=np.array(keys), m=th[:nk], e=th[nk:])


if __name__ == "__main__":
    main()

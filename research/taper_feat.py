"""Cache the linear structure of TAPERING, so it can be fitted on real data with a holdout.

`CLAUDE.md` names tapering as the remaining interpretable eval capacity: 28 keys
carry one value for both phases, including the whole `kattack.*` group,
`space.scale`, `minor.outpost_knight`, the passer path terms and `tempo`. It was
tried once, converged at +0.134% loss, and screened slightly WORSE
(d_mean +0.445). But that fit has both defects this project keeps catching:
`texel.py` defaults to the 10K dataset with 382K available, and every eval fit
in this project's history reports IN-SAMPLE loss. When mobility finally got a
held-out split, +1.566% became +0.008%. So tapering has not had a fair test.

It is cheap to give it one, because tapering is LINEAR IN THE WEIGHTS. `wt()` is

    w_k(p) = p*mg_k + (1-p)*eg_k          (phase 1.0 = opening)

so parametrising mg_k = W[k]*m_k and eg_k = W[k]*e_k, where m_k = e_k = 1 is
exactly today's evaluation,

    eval = E_base + SUM_k c_k * (p*m_k + (1-p)*e_k - 1)

with c_k the position's contribution from weight k. Measure c_k THROUGH the real
`evaluate()` -- zero the weight, re-evaluate, difference -- rather than deriving
it, because `evaluate` multiplies the concept sum by the opposite-bishop
modifier and a derived coefficient was wrong by 7.9cp once already. That also
carries `scale` for free.

Extract (E_base, phase, c[28]) once per position and every later candidate is a
dot product, so the fit runs against a holdout in seconds instead of hours
against itself.

Keys seeded at 0.0 are dropped: c_k is identically zero for them, so the
multiplicative parametrisation cannot move them (the same trap `TUNABLE`'s
multiplicative bounds set for the tuner).
"""
import json
import multiprocessing as mp
import pathlib
import sys

import chess

CC = pathlib.Path("/home/joynerwk03/mission-control/projects/conceptchess")
sys.path.insert(0, str(CC))

from engine.evaluation import evaluate          # noqa: E402
from engine.context import EvalContext          # noqa: E402
from engine.weights import W, W_EG              # noqa: E402

# The untapered keys. material.* is excluded by design -- SEE reads those values
# statically, so a phase-dependent material weight would desynchronise it.
# The three global endgame SCALINGS are excluded: they multiply the whole
# concept sum, so the eval is not linear in them jointly with everything else.
# A 40-position linearity check passed at 0.000000 and was a FALSE PASS -- they
# fire on under 1% of positions. At 2500 positions the joint error is 53cp, with
# ocb.draw_scale carrying the blame on 0.7% activity. Without them: 17 keys,
# 0.000000 cp over 4000 positions, zero nonlinear cases.
DROP = {"ocb.draw_scale", "scale.no_pawns", "scale.wrong_bishop"}
KEYS = sorted(k for k in W
              if k not in W_EG
              and not k.startswith("material.")
              and abs(W[k]) > 1e-9
              and k not in DROP)


def extract(lines):
    out = []
    for ln in lines:
        d = json.loads(ln)
        b = chess.Board(d["fen"])
        try:
            base = evaluate(b)
            ph = EvalContext(b).phase
        except Exception:
            continue
        c = []
        ok = True
        for k in KEYS:
            keep = W[k]
            W[k] = 0.0
            try:
                c.append(base - evaluate(b))
            except Exception:
                ok = False
            finally:
                W[k] = keep
            if not ok:
                break
        if ok:
            out.append((base, ph, d["res"], c))
    return out


def main():
    data = pathlib.Path(sys.argv[1])
    n = int(sys.argv[2])
    out_path = pathlib.Path(sys.argv[3])

    lines = []
    with data.open() as fh:
        for i, ln in enumerate(fh):
            if i >= n:
                break
            lines.append(ln)
    print(f"{len(lines)} positions, {len(KEYS)} untapered keys", flush=True)

    # CONTIGUOUS chunks, concatenated in order: the holdout is a trailing block
    # and this data is self-play sampled every few plies, so adjacent lines are
    # the same game. A strided split would put the same game on both sides.
    nproc = min(12, mp.cpu_count())
    sz = (len(lines) + nproc - 1) // nproc
    chunks = [lines[i * sz:(i + 1) * sz] for i in range(nproc)]
    with mp.Pool(nproc) as pool:
        parts = pool.map(extract, chunks)

    import numpy as np
    rows = [r for p in parts for r in p]
    np.savez_compressed(
        out_path,
        keys=np.array(KEYS),
        base=np.array([r[0] for r in rows], dtype=np.float64),
        phase=np.array([r[1] for r in rows], dtype=np.float64),
        res=np.array([r[2] for r in rows], dtype=np.float64),
        c=np.array([r[3] for r in rows], dtype=np.float64))
    print(f"wrote {len(rows)} rows x {len(KEYS)} keys -> {out_path}", flush=True)


if __name__ == "__main__":
    main()

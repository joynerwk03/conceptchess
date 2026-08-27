"""Fit the mobility curves on the FULL dataset by caching the linear structure.

The tuner is slow for a structural reason, not an implementation one: it
re-evaluates every position through the Python evaluation on every candidate
step, so coordinate descent over N weights costs ~2*N*passes full sweeps. At 66
parameters that is hours on 80K positions and days on 382K -- which is why the
only fit that finished used 10K positions and overfitted (+1.566% loss, and a
WORSE independent screen).

But mobility enters the evaluation LINEARLY. For each position

    eval(w) = scale * ( R + SUM_k w_k * f_k )

where f_k is a pure count -- how many of our pieces have exactly k safe squares,
minus how many of theirs -- and R is everything the mobility weights do not
touch. `scale` is the multiplicative endgame factor (opposite bishops, both
sides pawnless, wrong rook pawn) that the evaluation applies at the very end;
it multiplies the mobility contribution too, so it has to be carried.

Extract (R, scale, f) ONCE per position and every later candidate is a dot
product. That turns days into seconds and lets the fit use all 382K positions.

Recovering R and scale exactly, with two evaluations per position:

    E0 = eval with every mobility weight set to 0   = scale * R
    E1 = eval with the seeded weights               = scale * (R + M0)
    M0 = SUM_k w_seed_k * f_k                        (computed from the features)
    => scale = (E1 - E0) / M0     when M0 != 0
       R     = E0 / scale

Positions where M0 == 0 carry no mobility signal at all and are dropped; they
cannot inform these weights either way.

The result is checked the only way that counts: rebuild, confirm eval_check is
still 0.000000, then run the independent referee screen. A Texel gain that does
not survive that screen is not a gain -- this session has two of them.
"""
import json
import math
import pathlib
import sys

import chess

CC = pathlib.Path("/home/joynerwk03/mission-control/projects/conceptchess")
sys.path.insert(0, str(CC))

from engine.context import EvalContext          # noqa: E402
from engine.evaluation import evaluate          # noqa: E402
from engine.weights import W                    # noqa: E402

MAXN = {chess.KNIGHT: ("knight", 8), chess.BISHOP: ("bishop", 13),
        chess.ROOK: ("rook", 14), chess.QUEEN: ("queen", 27)}
KEYS = [f"mob.{nm}.{n}" for _, (nm, mx) in MAXN.items() for n in range(mx + 1)]
KIDX = {k: i for i, k in enumerate(KEYS)}


def features(board):
    """f[k] = (our pieces with k safe squares) - (theirs), White-relative."""
    ctx = EvalContext(board)
    f = [0.0] * len(KEYS)
    for color, sign in ((chess.WHITE, 1.0), (chess.BLACK, -1.0)):
        own = ctx.occupied_co[color]
        unsafe = ctx.pawn_attacks[not color]
        for pt, (nm, mx) in MAXN.items():
            for sq in ctx.pieces[color][pt]:
                n = chess.popcount(ctx.attacks[sq] & ~own & ~unsafe)
                if n > mx:
                    n = mx
                f[KIDX[f"mob.{nm}.{n}"]] += sign
    return f, ctx.phase


def main():
    data = pathlib.Path(sys.argv[1])
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    rows = [json.loads(l) for l in data.read_text().splitlines()]
    if limit:
        step = max(1, len(rows) // limit)
        rows = rows[::step][:limit]
    print(f"{len(rows)} positions from {data.name}", flush=True)

    seed = {k: float(W[k]) for k in KEYS}
    samples = []
    for i, r in enumerate(rows):
        b = chess.Board(r["fen"])
        f, phase = features(b)
        M0 = sum(seed[k] * f[KIDX[k]] for k in KEYS)
        if abs(M0) < 1e-9:
            continue
        e1 = evaluate(b)
        for k in KEYS:
            W[k] = 0.0
        e0 = evaluate(b)
        for k in KEYS:
            W[k] = seed[k]
        scale = (e1 - e0) / M0
        if not math.isfinite(scale) or abs(scale) < 1e-9:
            continue
        samples.append((f, phase, scale, e0 / scale, float(r["res"])))
        if (i + 1) % 20000 == 0:
            print(f"  extracted {i+1}/{len(rows)}", flush=True)
    print(f"usable samples: {len(samples)}", flush=True)
    out = pathlib.Path("/home/joynerwk03/ccruns/mobfeat.json")
    out.write_text(json.dumps({"keys": KEYS, "samples": samples}))
    print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()

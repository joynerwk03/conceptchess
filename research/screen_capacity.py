"""Is the evaluation limited by MISSING KNOWLEDGE or by CAPACITY?

`research/eval_room.py` found a ~16.5% relative outcome-loss gap to a far
stronger static evaluator, and -- the informative part -- found it spread almost
evenly across every interpretable bucket: phase, material, pawn count, queens,
passers, king exposure, piece mix all sit within a few points of 17%. A missing
TERM does not look like that; it looks like a large gap in the one bucket where
it fires and nothing anywhere else. A uniform deficit is the signature of a
model that cannot track the target anywhere, which is a statement about
CAPACITY, and it would explain nine hand-picked bundles measuring zero.

This screens that hypothesis before any engine code is written. The cheapest
large block of genuinely new capacity is the one thing NNUE has that a classical
piece-square table does not: **piece placement conditioned on a king**. HalfKP
indexes every piece by (piece, square, own-king-square). Here that interaction is
kept interpretable and made data-efficient by using the RELATIVE offset from the
king rather than the full 64x64 cross:

    column = (piece type, |file - king file|, rank - king rank)

8 x 15 = 120 offsets per piece type, folded left-right because a relative offset
has no absolute file to break the symmetry, and tapered mg/eg like the rest of
the evaluation. 960 parameters for one king, and every one of them reads as a
sentence: "knight two files and one rank in front of the enemy king: +14".

Fitted as a block on top of the FROZEN current evaluation, so what is measured
is the marginal value of the capacity, not a re-tune. The honest comparison is
`--mode pst`, which fits the EXISTING piece-square tables the same way, through
the same optimiser, on the same split. That control is what makes the number
mean something: re-fitting the current tables is worth a known ~+4.8 Elo, so if
king-relative capacity is not clearly larger than that, it is not the answer.

Scale-invariance is enforced where it matters: the block is fitted at a fixed K,
but every reported loss refits K over a grid, so a block that merely rescales the
evaluation scores as the nothing it is.

    PYTHONPATH=. .venv/bin/python research/screen_capacity.py --mode enemy
"""
import argparse
import json
import multiprocessing as mp
import random

import chess
import numpy as np

from research.texel import ROOT

KGRID = [0.28, 0.32, 0.36, 0.40, 0.44, 0.48, 0.52, 0.56, 0.60, 0.70]
PTS = (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
NOFF = 120                      # 8 folded files x 15 rank offsets
NBAND = 24                      # 8 king-distance rings x 3 rank relations
MODES = ("enemy", "own", "both", "pst", "band")


def sig(e, k):
    return 1.0 / (1.0 + np.exp(-(np.log(10.0) / (k * 400.0)) * e))


def best_loss(e, res):
    return min(float(np.mean((sig(e, k) - res) ** 2)) for k in KGRID)


def ncols(mode):
    if mode == "pst":
        return 6 * 64 * 2
    if mode == "band":
        return len(PTS) * NBAND * 2 * 2      # both kings, mg/eg
    n = {"enemy": 1, "own": 1, "both": 2}[mode]
    return len(PTS) * NOFF * n * 2


def _rel(sq, ksq, white):
    """Offset from a king, folded left-right and oriented for the piece's side."""
    df = abs(chess.square_file(sq) - chess.square_file(ksq))
    dr = chess.square_rank(sq) - chess.square_rank(ksq)
    if not white:
        dr = -dr
    return df * 15 + (dr + 7)


def _band(sq, ksq, white):
    """Coarse version: king-distance ring x whether the piece is in front of,
    level with, or behind the king.

    The full 8x15 offset grid has 120 cells per piece per king, and fitting it
    produced tables that swing +34 / -24 between ADJACENT offsets -- positions
    that are nearly the same chess fact. That is fitted noise, and it is not
    something a reader could ever be shown as an explanation. Chess knowledge in
    this space is smooth and mostly radial, which is why classical engines use
    king rings and king distance rather than offset grids. 24 cells cannot
    encode the oscillation, so if the gain survives here it is structural.
    """
    df = abs(chess.square_file(sq) - chess.square_file(ksq))
    dr = chess.square_rank(sq) - chess.square_rank(ksq)
    if not white:
        dr = -dr
    ring = max(df, abs(dr))                  # Chebyshev distance, 0..7
    rel = 0 if dr > 0 else (1 if dr == 0 else 2)
    return ring * 3 + rel


def chunk(args):
    """Base eval, modifier product, and the feature block for each position.

    The base evaluation is reproduced here rather than calling evaluate() so the
    SAME EvalContext yields the phase and the modifier product. That product is
    the coefficient a new concept enters with: the concept sum is formed first
    and the modifiers multiply it, so a block added inside the sum is worth
    modprod x (X @ theta) in the final number. Deriving that instead of measuring
    it is what made the first linear PST model wrong by 7.9cp.
    """
    fens, mode = args
    from engine.concepts import ALL_CONCEPTS, ALL_MODIFIERS
    from engine.context import EvalContext

    base = np.zeros(len(fens))
    mods = np.zeros(len(fens))
    rows, cols, vals = [], [], []
    half = len(PTS) * NOFF                     # width of one king's block, per phase
    for i, f in enumerate(fens):
        b = chess.Board(f)
        ctx = EvalContext(b)
        tot = sum(c.score(ctx) for c in ALL_CONCEPTS)
        mp_ = 1.0
        for m in ALL_MODIFIERS:
            mp_ *= m.factor(ctx)
        base[i] = tot * mp_
        mods[i] = mp_
        ph = ctx.phase
        wk, bk = ctx.king_sq[chess.WHITE], ctx.king_sq[chess.BLACK]
        if wk is None or bk is None:
            continue
        acc = {}
        if mode == "pst":
            for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
                flip = 0 if color == chess.WHITE else 56
                for pi, pt in enumerate(chess.PIECE_TYPES):
                    for sq in ctx.pieces[color][pt]:
                        c = pi * 64 + (sq ^ flip)
                        acc[c] = acc.get(c, 0) + sign
        elif mode == "band":
            stride = len(PTS) * NBAND
            for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
                white = color == chess.WHITE
                for kind, off in (("enemy", 0), ("own", stride)):
                    ksq = ((bk if white else wk) if kind == "enemy"
                           else (wk if white else bk))
                    for pi, pt in enumerate(PTS):
                        for sq in ctx.pieces[color][pt]:
                            c = off + pi * NBAND + _band(sq, ksq, white)
                            acc[c] = acc.get(c, 0) + sign
        else:
            want = []
            if mode in ("enemy", "both"):
                want.append(("enemy", 0))
            if mode in ("own", "both"):
                want.append(("own", half if mode == "both" else 0))
            for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
                white = color == chess.WHITE
                for kind, off in want:
                    if kind == "enemy":
                        ksq = bk if white else wk
                    else:
                        ksq = wk if white else bk
                    for pi, pt in enumerate(PTS):
                        for sq in ctx.pieces[color][pt]:
                            c = off + pi * NOFF + _rel(sq, ksq, white)
                            acc[c] = acc.get(c, 0) + sign
        w = ncols(mode) // 2
        for c, v in acc.items():
            if not v:
                continue
            rows.append(i)
            cols.append(c)
            vals.append(v * ph * mp_)          # middlegame half
            rows.append(i)
            cols.append(c + w)
            vals.append(v * (1.0 - ph) * mp_)  # endgame half
    return (base, mods, np.asarray(rows, dtype=np.int64),
            np.asarray(cols, dtype=np.int32), np.asarray(vals, dtype=np.float64))


def build(fens, mode, workers):
    parts = [fens[i::workers] for i in range(workers)]
    with mp.Pool(workers) as pool:
        res = pool.map(chunk, [(p, mode) for p in parts])
    n = len(fens)
    base = np.zeros(n)
    R, C, V = [], [], []
    for i, (b, _m, r, c, v) in enumerate(res):
        idx = np.arange(i, n, workers)
        base[idx] = b
        if len(r):
            R.append(idx[r])
            C.append(c)
            V.append(v)
    return base, np.concatenate(R), np.concatenate(C), np.concatenate(V)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel_all.jsonl"))
    ap.add_argument("--mode", default="enemy", choices=MODES)
    ap.add_argument("--n", type=int, default=0, help="0 = all")
    ap.add_argument("--test-data", default=str(ROOT / "research/data/texel4.jsonl"),
                    help="independent test file; '' to split by position instead")
    ap.add_argument("--test-n", type=int, default=90000)
    # What the fit is pulled TOWARDS. The reported number is the same either
    # way -- decisive-game outcome loss on the independent test set -- so the
    # two targets are directly comparable, and "outcome" is the control.
    ap.add_argument("--target", default="outcome", choices=("outcome", "teacher"),
                    help="'teacher' fits towards an outside evaluator's static "
                         "score (field 'sv'), 'outcome' towards the game result")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--holdout", type=float, default=0.35)
    ap.add_argument("--steps", type=int, default=3000)
    ap.add_argument("--lr", type=float, default=0.03)
    ap.add_argument("--patience", type=int, default=600)
    ap.add_argument("--k", type=float, default=0.44)
    # No L2. The data gradient here is ~1e-9 because it is averaged over n and
    # the +1/-1 signs cancel between colours; any L2 large enough to notice
    # swamps it and Adam quietly optimises the regulariser instead. The repo's
    # working fitters regularise by CLIPPING and by rounding to integers, which
    # is scale-free and cannot outvote the data.
    ap.add_argument("--clip", type=float, default=60.0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    rows_ = [json.loads(l) for l in open(a.data)]
    random.Random(20260816).shuffle(rows_)
    if a.n:
        rows_ = rows_[:a.n]
    # THREE-way split. With ~1000 free parameters, early stopping on the same
    # set the result is quoted from would leak: the stopping step is itself a
    # fitted parameter. So the val split chooses when to stop and the test split
    # -- untouched until the end -- is the number reported.
    #
    # And by default the test split comes from a DIFFERENT FILE, because a
    # random position-level split is not independent: this data is sampled every
    # few plies from self-play games, so splitting by position puts positions
    # from the SAME GAME on both sides, sharing an opening, a structure and one
    # correlated result. That inflates any held-out number, and it inflates it
    # most for a model with enough parameters to notice. texel4 was generated in
    # a different run and overlaps texel_all by 0.1%, so it is genuinely
    # independent games.
    if a.test_data:
        te = [json.loads(l) for l in open(a.test_data)]
        random.Random(20260816).shuffle(te)
        te = te[:a.test_n]
        n1 = int(len(rows_) * 0.75)
        tr, va = rows_[:n1], rows_[n1:]
        print(f"test set: {a.test_data} (independent games)")
    else:
        n1 = int(len(rows_) * 0.60)
        n2 = int(len(rows_) * 0.80)
        tr, va, te = rows_[:n1], rows_[n1:n2], rows_[n2:]
    print(f"mode={a.mode}  {len(tr):,} fit / {len(va):,} val (early stop) / "
          f"{len(te):,} test  ({ncols(a.mode)} parameters)")

    print("building features...")
    fb, fr, fc, fv = build([r["fen"] for r in tr], a.mode, a.workers)
    vb, vr, vc, vv = build([r["fen"] for r in va], a.mode, a.workers)
    hb, hr, hc, hv = build([r["fen"] for r in te], a.mode, a.workers)
    if a.target == "teacher":
        # Fitted in WIN-PROBABILITY space, not centipawns: a hundred centipawns
        # of error matters enormously at level material and almost not at all at
        # +800, and squared centipawn error would spend its effort in exactly
        # the wrong place. sig() puts the teacher's score on the same scale the
        # outcome labels live on, so the two targets are interchangeable here
        # and the comparison between them is clean.
        missing = [r for r in tr if "sv" not in r]
        assert not missing, f"{len(missing)} training rows have no teacher label"
        ftr = sig(np.asarray([r["sv"] for r in tr], dtype=float), a.k)
    else:
        ftr = np.asarray([r["res"] for r in tr], dtype=float)
    vres = np.asarray([r["res"] for r in va], dtype=float)
    hres = np.asarray([r["res"] for r in te], dtype=float)
    vdec, hdec = vres != 0.5, hres != 0.5
    npar = ncols(a.mode)

    def ev(theta, base, r, c, v):
        return base + np.bincount(r, weights=v * theta[c], minlength=len(base))

    th = np.zeros(npar)
    l0 = best_loss(ev(th, hb, hr, hc, hv)[hdec], hres[hdec])
    v0 = best_loss(ev(th, vb, vr, vc, vv)[vdec], vres[vdec])
    print(f"before: test decisive outcome loss {l0:.6f}  (val {v0:.6f})")

    cst = np.log(10.0) / (a.k * 400.0)
    m = np.zeros(npar)
    v_ = np.zeros(npar)
    b1, b2, eps = 0.9, 0.999, 1e-12
    n = len(fb)
    best_v, best_th, best_t = v0, th.copy(), 0
    for t in range(1, a.steps + 1):
        e = ev(th, fb, fr, fc, fv)
        p = sig(e, a.k)
        g_e = (2.0 * (p - ftr) * p * (1.0 - p) * cst) / n
        g = np.bincount(fc, weights=fv * g_e[fr], minlength=npar)
        m = b1 * m + (1 - b1) * g
        v_ = b2 * v_ + (1 - b2) * g * g
        th -= a.lr * (m / (1 - b1 ** t)) / (np.sqrt(v_ / (1 - b2 ** t)) + eps)
        np.clip(th, -a.clip, a.clip, out=th)
        if t % 25 == 0:
            lv = best_loss(ev(th, vb, vr, vc, vv)[vdec], vres[vdec])
            if lv < best_v:
                best_v, best_th, best_t = lv, th.copy(), t
            if t % 250 == 0:
                print(f"  step {t:5d}   val {lv:.6f} ({100*(v0-lv)/v0:+.3f}%)"
                      f"   best@{best_t}   |theta| rms "
                      f"{np.sqrt((th**2).mean()):6.2f}")
            if t - best_t > a.patience:
                print(f"  early stop at {t}, best was step {best_t}")
                break

    th = best_th
    thr = np.round(th)
    l1 = best_loss(ev(thr, hb, hr, hc, hv)[hdec], hres[hdec])
    rel = 100 * (l0 - l1) / l0
    print(f"\nafter (integers): {l1:.6f}")
    print(f"HELD-OUT OUTCOME LOSS  {rel:+.3f}%    ~{4.7*rel:+.1f} Elo")
    print(f"nonzero parameters: {int((thr != 0).sum())} / {npar}   "
          f"max |value| {np.abs(thr).max():.0f}")
    if a.out:
        json.dump({"mode": a.mode, "theta": list(thr), "rel": rel},
                  open(a.out, "w"))
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

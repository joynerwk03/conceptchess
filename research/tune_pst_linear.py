"""Tune the piece-square tables per SQUARE, by exploiting that they are linear.

`research/tune_pst.py` moved whole ranks by coordinate descent, re-running the
Python evaluation for every trial step. That costs a full pass over the data per
parameter per direction, which is why it could only afford 48 parameters (6
ranks x 8 tables) and a 24k sample -- a rank is a coarse approximation of what a
piece-square table actually encodes.

But look at what `piece_placement.score` does with a table: it adds
`sign * wt(scale, phase) * T[i]`, and for the tapered tables
`sign * wt(scale, phase) * phase * T_MG[i]` plus the endgame mirror. Every table
entry enters the evaluation MULTIPLIED BY A CONSTANT that does not depend on the
table. So for a fixed position the evaluation is exactly

    eval(T) = eval(T0) + sum_f coef_f * (T_f - T0_f)

with `coef_f` computable once. After one pass over the data to collect the
coefficients, scoring a candidate set of tables is a dot product -- no chess, no
evaluation. Fitting all 512 entries becomes cheaper than fitting 48 ranks was.

That buys three things the rank tuner could not have:

  * every square moves independently, which is the thing a piece-square table is;
  * the whole 98k-row dataset instead of a 24k window;
  * true gradient descent rather than a fixed-span coordinate probe.

Guards, because 512 free parameters on game outcomes will happily overfit:

  * mirror-image squares are TIED for pawns and pieces -- chess is left-right
    symmetric, an asymmetric knight table is overfitting and unreadable. The
    two KING tables are left free, because castling really is asymmetric;
  * an L2 pull toward the current tables, so squares the data says nothing
    about stay where a human put them;
  * every entry clipped to +-30% of its current value (plus a small floor), so
    no square can run away;
  * a HELD-OUT split scored at the end -- and scored with the REAL evaluator
    after rounding to integers, not with the linear model that did the fitting.
    The linear model is exact in the table values, but the values that ship are
    rounded, and a gain that does not survive rounding is not a gain.

    PYTHONPATH=. .venv/bin/python research/tune_pst_linear.py
"""
import argparse
import json
import random

import chess
import numpy as np

from research.texel import ROOT

# feature block order; each block is 64 squares, White's point of view
BLOCKS = ["PAWN_MG", "PAWN_EG", "KNIGHT", "BISHOP", "ROOK", "QUEEN",
          "KING_MG", "KING_EG"]
BLOCK_OF = {n: i for i, n in enumerate(BLOCKS)}
NF = len(BLOCKS) * 64

# tables whose left-right mirror squares are tied to a single parameter
SYMMETRIC = {"PAWN_MG", "PAWN_EG", "KNIGHT", "BISHOP", "ROOK", "QUEEN"}


def param_map():
    """feature index -> parameter index, tying mirror squares where wanted."""
    fmap = np.zeros(NF, dtype=np.int32)
    nxt = 0
    seen = {}
    for bi, name in enumerate(BLOCKS):
        for sq in range(64):
            r, f = divmod(sq, 8)
            key = (bi, r, min(f, 7 - f)) if name in SYMMETRIC else (bi, r, f)
            if key not in seen:
                seen[key] = nxt
                nxt += 1
            fmap[bi * 64 + sq] = seen[key]
    return fmap, nxt


def collect(boards, tables):
    """One pass over the data: base eval + the coefficient of every table entry.

    Returns CSR-ish triples (row, feature, coefficient) plus the base evals.
    """
    from engine.context import EvalContext
    from engine.evaluation import MODIFIERS, evaluate, clear_caches
    from engine.weights import wt

    rows, cols, vals = [], [], []
    base = np.empty(len(boards))
    clear_caches()
    for i, b in enumerate(boards):
        base[i] = evaluate(b)
        ctx = EvalContext(b)
        ph = ctx.phase
        # evaluate() is the concept SUM times the multiplicative modifiers
        # (opposite-bishop drawishness), so a table entry reaches the final
        # score scaled by their product. Leaving this out makes the model
        # wrong by several centipawns in exactly the positions where the
        # modifiers bite -- and invisibly so, because a perturbation applied
        # evenly to a whole table cancels between the two colours.
        mod = 1.0
        for m in MODIFIERS:
            mod *= m.factor(ctx)
        w_pawn = wt("pst.pawn", ph) * mod
        w_king = wt("pst.king", ph) * mod
        flat = {chess.KNIGHT: ("KNIGHT", wt("pst.knight", ph) * mod),
                chess.BISHOP: ("BISHOP", wt("pst.bishop", ph) * mod),
                chess.ROOK: ("ROOK", wt("pst.rook", ph) * mod),
                chess.QUEEN: ("QUEEN", wt("pst.queen", ph) * mod)}
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            flip = 0 if color == chess.WHITE else 56
            for pt, (name, w) in flat.items():
                blk = BLOCK_OF[name] * 64
                for sq in ctx.pieces[color][pt]:
                    rows.append(i); cols.append(blk + (sq ^ flip)); vals.append(sign * w)
            bmg, beg = BLOCK_OF["PAWN_MG"] * 64, BLOCK_OF["PAWN_EG"] * 64
            for sq in ctx.pieces[color][chess.PAWN]:
                j = sq ^ flip
                rows.append(i); cols.append(bmg + j); vals.append(sign * w_pawn * ph)
                rows.append(i); cols.append(beg + j); vals.append(sign * w_pawn * (1 - ph))
            ksq = ctx.king_sq[color]
            if ksq is not None:
                j = ksq ^ flip
                kmg, keg = BLOCK_OF["KING_MG"] * 64, BLOCK_OF["KING_EG"] * 64
                rows.append(i); cols.append(kmg + j); vals.append(sign * w_king * ph)
                rows.append(i); cols.append(keg + j); vals.append(sign * w_king * (1 - ph))
        if (i + 1) % 10000 == 0:
            print(f"  features {i+1}/{len(boards)}", flush=True)
    return (np.asarray(rows, dtype=np.int32), np.asarray(cols, dtype=np.int32),
            np.asarray(vals), base)


class Model:
    """eval = base + sum_f coef_f * delta_f, with features folded onto params."""

    def __init__(self, rows, cols, vals, base, fmap, npar):
        self.rows, self.vals, self.base = rows, vals, base
        self.par = fmap[cols]          # feature -> parameter
        self.n = len(base)
        self.npar = npar

    def evals(self, delta):
        return self.base + np.bincount(self.rows, weights=self.vals * delta[self.par],
                                       minlength=self.n)

    def loss_and_grad(self, delta, res, k):
        e = self.evals(delta)
        c = np.log(10.0) / (k * 400.0)
        s = 1.0 / (1.0 + np.exp(-c * e))          # same curve as 10**(-e/(k*400))
        d = s - res
        g_e = (2.0 * d * s * (1.0 - s) * c) / self.n
        grad = np.bincount(self.par, weights=self.vals * g_e[self.rows],
                           minlength=self.npar)
        return float(np.mean(d * d)), grad

    def loss(self, delta, res, k):
        e = self.evals(delta)
        s = 1.0 / (1.0 + np.exp(-(np.log(10.0) / (k * 400.0)) * e))
        return float(np.mean((s - res) ** 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel5.jsonl"))
    ap.add_argument("--holdout", type=float, default=0.35)
    ap.add_argument("--steps", type=int, default=4000)
    ap.add_argument("--lr", type=float, default=0.5)
    ap.add_argument("--l2", type=float, default=2e-8)
    ap.add_argument("--out", default=str(ROOT / "research/data/pst_linear.json"))
    a = ap.parse_args()

    from engine.concepts import piece_placement as pp

    rowsj = [json.loads(l) for l in open(a.data)]
    rowsj = [r for r in rowsj if r["res"] != 0.5]      # decisive games only
    random.Random(20260813).shuffle(rowsj)
    cut = int(len(rowsj) * (1 - a.holdout))
    fit_j, hold_j = rowsj[:cut], rowsj[cut:]
    print(f"{len(fit_j)} decisive fitting positions, {len(hold_j)} held out")

    tables = {n: list(getattr(pp, n)) for n in BLOCKS}
    T0 = np.concatenate([np.asarray(tables[n], dtype=float) for n in BLOCKS])

    fmap, npar = param_map()
    print(f"{NF} table entries -> {npar} free parameters "
          f"(mirror squares tied except for the king)")

    print("collecting fit features...")
    fit = Model(*collect([chess.Board(r["fen"]) for r in fit_j], tables), fmap, npar)
    fit_res = np.asarray([r["res"] for r in fit_j], dtype=float)
    print("collecting held-out features...")
    hold = Model(*collect([chess.Board(r["fen"]) for r in hold_j], tables), fmap, npar)
    hold_res = np.asarray([r["res"] for r in hold_j], dtype=float)

    zero = np.zeros(npar)
    best_k, base = None, 1e9
    for k in (0.6, 0.8, 1.0, 1.2):
        l = fit.loss(zero, fit_res, k)
        if l < base:
            best_k, base = k, l
    hold_base = hold.loss(zero, hold_res, best_k)
    print(f"K={best_k}  fit {base:.6f}  held-out {hold_base:.6f}")

    # per-parameter clip: +-30% of the current value (plus a floor, so squares
    # that currently sit near zero can still move a little)
    lim = np.zeros(npar)
    np.maximum.at(lim, fmap, np.abs(T0) * 0.30 + 10.0)

    delta = np.zeros(npar)
    m = np.zeros(npar)
    v = np.zeros(npar)
    b1, b2, eps = 0.9, 0.999, 1e-8
    for t in range(1, a.steps + 1):
        l, g = fit.loss_and_grad(delta, fit_res, best_k)
        g = g + 2.0 * a.l2 * delta          # pull toward the current tables
        m = b1 * m + (1 - b1) * g
        v = b2 * v + (1 - b2) * g * g
        mh = m / (1 - b1 ** t)
        vh = v / (1 - b2 ** t)
        delta -= a.lr * mh / (np.sqrt(vh) + eps)
        np.clip(delta, -lim, lim, out=delta)
        if t % 500 == 0:
            print(f"  step {t:5d}  fit {l:.6f}  held-out "
                  f"{hold.loss(delta, hold_res, best_k):.6f}", flush=True)

    fit_end = fit.loss(delta, fit_res, best_k)
    hold_end = hold.loss(delta, hold_res, best_k)

    # What ships is INTEGERS, so score what ships.
    dint = np.round(delta[fmap])
    tuned = T0 + dint
    par_int = np.zeros(npar)
    par_int[fmap] = dint          # any tied feature carries the same value
    hold_int = hold.loss(par_int, hold_res, best_k)

    out = {n: list(tuned[i * 64:(i + 1) * 64]) for i, n in enumerate(BLOCKS)}
    json.dump({"k": best_k, "tables": out}, open(a.out, "w"), indent=1)

    gf = 100 * (base - fit_end) / base
    gh = 100 * (hold_base - hold_end) / hold_base
    gi = 100 * (hold_base - hold_int) / hold_base
    print(f"\nfit          {base:.6f} -> {fit_end:.6f}   {gf:+.3f}%")
    print(f"held-out     {hold_base:.6f} -> {hold_end:.6f}   {gh:+.3f}%")
    print(f"HELD-OUT int {hold_base:.6f} -> {hold_int:.6f}   {gi:+.3f}%"
          f"   ~{4.7*gi:+.1f} Elo   <- the number that ships")
    print(f"largest single-square move: {np.abs(dint).max():.0f}cp")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()

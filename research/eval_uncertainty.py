"""Does CONCEPT DISAGREEMENT predict where our evaluation is wrong?

The load-bearing conclusion of this project is that pruning accuracy is bounded
by evaluation accuracy. But that bound is applied as a GLOBAL CONSTANT --
RFP_MARGIN is 90 for every position on the board -- which implicitly asserts the
evaluation is equally trustworthy everywhere. It obviously is not.

An eval of +150 that is all material is nearly certain. An eval of +150 built
from kattack +420 and mobility -270 is a coin flip. This engine is the only one
that can tell those apart for free, because its evaluation is a NAMED SUM. An
NNUE cannot produce this signal at all. So the interpretability constraint,
which has cost strength everywhere else in this project, is an asset here.

If disagreement predicts error, then pruning margins can be modulated per
position: prune hard where the concepts agree, gently where large terms cancel.
That does not make the evaluation more accurate -- it makes the SEARCH aware of
where the evaluation is weak, which is a different and untried lever.

This script is the decisive cheap test, run BEFORE any implementation. It uses
the cached SF11 referee table, so it costs no games:

  our_stm   our static eval, from the side to move
  sf_stm    SF11's depth-13 score for its best move, side to move -- i.e. what a
            deep search says the position is really worth
  error     |our_stm - sf_stm|, how badly our static eval misjudges the position
  spread    sum of |concept score| over non-material concepts: how much large
            opposing terms are cancelling

Reported as error bucketed by spread, not as a bare correlation, because the
shape matters: a monotone rise is actionable, a flat line kills the idea in
twenty minutes for zero games.

Also reports the halfmove-clock distribution, because the second candidate
(50-move discounting) can only be screened on positions where the clock is
actually high -- the same "can the rule fire here" check that invalidated the
lmrdeep and cap6 screens.
"""
import json
import sys
from pathlib import Path

import chess

ROOT = Path("/home/joynerwk03/mission-control/projects/conceptchess")
sys.path.insert(0, str(ROOT))

from engine.evaluation import evaluate, evaluate_detailed   # noqa: E402

CLAMP = 1500


def main():
    ref_path = sys.argv[1]
    rows = []
    for ln in open(ref_path):
        if ln.strip():
            rows.append(json.loads(ln))
    print(f"{len(rows)} referee positions\n")

    recs = []
    hm_hist = {}
    for r in rows:
        b = chess.Board(r["fen"])
        hm = b.halfmove_clock
        hm_hist[hm // 10] = hm_hist.get(hm // 10, 0) + 1
        sf = r["moves"][r["best"]]
        if abs(sf) > CLAMP:
            continue
        ours = evaluate(b)
        ours_stm = ours if b.turn == chess.WHITE else -ours
        err = abs(ours_stm - sf)
        det = evaluate_detailed(b)
        spread = 0.0
        per = {}
        for c in det.concepts:
            name = getattr(c, "name", "?")
            v = float(getattr(c, "score", 0.0))
            if name.startswith("material"):
                continue
            spread += abs(v)
            per[name] = abs(v)
        recs.append((spread, err, per))

    recs.sort(key=lambda x: x[0])
    n = len(recs)
    print(f"{n} usable (|SF11| <= {CLAMP}cp)\n")
    print(f"{'spread bucket':>16}{'n':>7}{'mean |error|':>14}{'median':>9}")
    NB = 6
    for i in range(NB):
        seg = recs[i * n // NB:(i + 1) * n // NB]
        errs = sorted(x[1] for x in seg)
        lo, hi = seg[0][0], seg[-1][0]
        print(f"{lo:7.0f}-{hi:<8.0f}{len(seg):>7}{sum(errs)/len(errs):>14.1f}"
              f"{errs[len(errs)//2]:>9.1f}")

    lo_seg = recs[:n // 3]
    hi_seg = recs[-(n // 3):]
    lo_e = sum(x[1] for x in lo_seg) / len(lo_seg)
    hi_e = sum(x[1] for x in hi_seg) / len(hi_seg)
    print(f"\nbottom third spread: mean error {lo_e:.1f}cp")
    print(f"top    third spread: mean error {hi_e:.1f}cp")
    print(f"ratio: {hi_e/lo_e:.2f}x"
          + ("   <-- SIGNAL" if hi_e / lo_e > 1.25 else "   <-- flat, idea dies here"))

    # which individual concepts predict error, by comparing mean error in the
    # top decile of each concept's magnitude against the overall mean
    names = set()
    for _s, _e, per in recs:
        names |= set(per)
    overall = sum(x[1] for x in recs) / n
    print(f"\noverall mean error {overall:.1f}cp. Concepts whose large values "
          f"coincide with error:")
    out = []
    for nm in sorted(names):
        vals = sorted(recs, key=lambda x: -x[2].get(nm, 0.0))[:max(30, n // 10)]
        m = sum(x[1] for x in vals) / len(vals)
        out.append((m / overall, nm, m))
    for ratio, nm, m in sorted(out, reverse=True)[:8]:
        print(f"  {nm:28s} top-decile mean error {m:6.1f}cp  ({ratio:.2f}x)")

    print("\nhalfmove-clock distribution (for the 50-move candidate):")
    for k in sorted(hm_hist):
        print(f"  hm {k*10:3d}-{k*10+9:<3d} {hm_hist[k]:6d}"
              f"  {100*hm_hist[k]/len(rows):5.1f}%")


if __name__ == "__main__":
    main()

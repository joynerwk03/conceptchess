"""Correction history, take two: only learn from scores that actually inform.

The first version measured -3.83 and the fault was mine, not the idea's. It
updated the table with `best` at every node -- but `best` is usually a BOUND, not
a score. A fail-high says "at least this much" and a fail-low says "at most this
much", and feeding either in as though it were the truth teaches the table
numbers that are wrong in a known direction.

The standard guard, and the reasoning behind each clause:

  * a fail-high whose value sits BELOW the static eval tells us nothing we did
    not already believe -- the search stopped early precisely because it had
    enough, so the true value is somewhere above, not at the bound;
  * likewise a fail-low whose value sits ABOVE the static eval;
  * and skip nodes whose best move is a capture, where the search result
    reflects a tactic rather than any systematic bias in positional judgement,
    which is the only thing this table is trying to learn.
"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1]) / "core/csearch.c"
s = p.read_text()

a = """    if(!excl && !checked && best>-S_MATE_TH && best<S_MATE_TH){
        /* This node just learned what a real search returns here versus what
         * the static eval guessed. Skipped in check, where the static eval is
         * not meaningful, and for mate scores, which are on another scale. */
        corr_update(b, eval_stm(b), best);
    }"""
b = """    if(!excl && !checked && best>-S_MATE_TH && best<S_MATE_TH
       && (!bestm || !is_capture(b,bestm))){
        /* Learn only from scores that inform. `best` is usually a BOUND: a
         * fail-high means "at least this", a fail-low "at most this". A
         * fail-high landing BELOW the static eval, or a fail-low landing above
         * it, tells us nothing we did not already believe -- the search
         * stopped early because it had enough, so the truth lies past the
         * bound, not at it. Feeding those in teaches the table numbers that are
         * wrong in a known direction, which is what the first version did.
         * Captures are skipped too: their score reflects a tactic, not the
         * systematic positional bias this table exists to learn. */
        int st0 = eval_stm(b);
        int fail_high = (best >= beta), fail_low = (best <= orig_alpha);
        if(!(fail_high && best <= st0) && !(fail_low && best >= st0))
            corr_update(b, st0, best);
    }"""
assert a in s, "corr_update block not found (run patch_corrhist.py first)"
s = s.replace(a, b, 1)

p.write_text(s)
print("correction history update rule fixed")

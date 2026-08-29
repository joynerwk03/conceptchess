"""Uncertainty-aware reverse futility: prune hard where the eval is trustworthy.

RFP_MARGIN is 90 for every position on the board, which asserts the evaluation is
equally reliable everywhere. Measured against the SF11 referee table, it is not:
sorting positions by |eval - material|, i.e. how much of the score is
non-material judgement, the top third has 1.71x the static-eval error of the
bottom third (211.2cp against 123.5cp), monotone across buckets.

So modulate the margin by that quantity. Tercile boundaries from the same
measurement are 43cp and 94cp:

    |eval - material| < 43   -> margin 67  (confident: prune HARDER)
    43 .. 94                 -> margin 90  (unchanged)
    > 94                     -> margin 135 (uncertain: prune LESS)

This does not make the evaluation more accurate, which is closed. It makes the
SEARCH aware of where the evaluation is weak, which is untried and is only
possible because this engine's eval is a named sum -- an NNUE has no terms to
disagree, so it cannot produce this signal at all. The interpretability
constraint is an asset here rather than a cost.

Cost: the loosest margin is tested first, so the extra work (five popcounts)
happens only at nodes that were going to be pruned under the most aggressive
setting. Everything else short-circuits exactly as before.

Interpretability: untouched. This is a SEARCH margin, not an eval term. No
concept, weight or PST changes, so eval_check must stay 0.000000.

Modes:
  uncert   the measured tercile thresholds above
  uncert2  a stronger version (55/110 margins) to see if the effect scales

Usage: uncert.py <worktree> <uncert|uncert2>
"""
import pathlib
import sys

WT = pathlib.Path(sys.argv[1])
MODE = sys.argv[2] if len(sys.argv) > 2 else "uncert"
p = WT / "core/csearch.c"
s = p.read_text()


def sub(old, new, what):
    global s
    assert s.count(old) == 1, f"{what}: anchor not unique ({s.count(old)})"
    s = s.replace(old, new, 1)


LO, HI = (67, 135) if MODE == "uncert" else (55, 160)

sub("static int eval_stm(Board *b){",
    """/* How much of this evaluation is NON-MATERIAL judgement, from the side to
 * move. Measured against SF11 on the referee table: the top third of positions
 * by this quantity carry 1.71x the static-eval error of the bottom third. Used
 * to decide how far the search should trust the eval when forward-pruning. */
static int eval_nonmat(const Board *b, int st){
    int m = 0;
    for(int p=PAWN;p<=QUEEN;p++)
        m += SEEV[p]*(__builtin_popcountll(b->bb[b->side][p])
                    - __builtin_popcountll(b->bb[!b->side][p]));
    int d = st - m;
    return d < 0 ? -d : d;
}

static int eval_stm(Board *b){""",
    "helper")

sub("""        int st=eval_stm(b);
        if(st - RFP_MARGIN*depth >= beta){ SS.path_len--; return st; }""",
    f"""        int st=eval_stm(b);
        /* Loosest margin first, so the extra work happens only at nodes that
         * were going to be pruned under the most aggressive setting. */
        if(st - {LO}*depth >= beta){{
            int u = eval_nonmat(b, st);
            int mg = (u > 94) ? {HI} : ((u < 43) ? {LO} : RFP_MARGIN);
            if(st - mg*depth >= beta){{ SS.path_len--; return st; }}
        }}""",
    "rfp")

p.write_text(s)
print(f"patched {p} (uncertainty-aware RFP, {MODE}: {LO}/90/{HI})")

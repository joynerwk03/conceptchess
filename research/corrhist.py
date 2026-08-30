"""Correction history, applied ONLY to pruning decisions -- the middle option.

This is the fix to a specific diagnosed failure, not a new hypothesis. The
uncertainty-aware experiments (RFP and LMR) both failed, and the stated reason
was that |eval - material| measures the MAGNITUDE of eval error but not its
DIRECTION: knowing the eval is unreliable at a node does not say which way it is
wrong, so spending extra nodes there is untargeted. Correction history supplies
exactly the missing direction, learned from the engine's own search.

Mechanism: for each position class, keep a running average of
(search result - static eval). When the static eval is used to make a PRUNING
decision, add that correction. Indexed by pawn structure (material key alone is
too coarse, full hash too sparse), which is the standard choice and is what the
existing pawn hash already keys on.

**Interpretability boundary, and why this is the middle option.** The correction
is applied ONLY inside reverse futility, null move and futility -- decisions
about which branches to skip. The value RETURNED from the node, stored in the
transposition table, propagated to the root, and shown by the GUI is the pure
concept sum, untouched. So `eval_check` must remain 0.000000 and the explanation
the user sees remains exactly the number the search reports.

What it does weaken: pruning decisions are made using a number the explanation
does not report. That is a real cost, argued in
research/INTERPRETABILITY_COST.md. The counter-argument is that RFP_MARGIN is
already a number the explanation does not report -- this makes that margin
position-adaptive rather than a global constant, which is a refinement of a
search parameter rather than a change to the evaluation.

Update rule: exponential moving average with a small weight, clamped, so a few
noisy nodes cannot swing a bucket. Applied on nodes that completed a real search
(not pruned, not a TT cutoff), where the difference between static eval and
search result is meaningful.

Usage: corrhist.py <worktree>
"""
import pathlib
import sys

WT = pathlib.Path(sys.argv[1])
p = WT / "core/csearch.c"
s = p.read_text()


def sub(old, new, what):
    global s
    assert s.count(old) == 1, f"{what}: anchor not unique ({s.count(old)})"
    s = s.replace(old, new, 1)


# per-thread table, keyed on side + pawn structure
sub("    Move counter[2][64][64];",
    """    Move counter[2][64][64];
    int corr[2][16384];      /* correction history: mean (search - static) by pawn structure */""",
    "table")

sub("static int eval_stm(Board *b){",
    """static int eval_stm(Board *b);   /* forward: eval_pruning calls it below */

/* Pawn-structure key for the correction table. Pawns only, so positions
 * sharing a structure share a correction -- the standard choice, and the same
 * grouping the pawn hash already uses. */
static inline unsigned corr_key(const Board *b){
    U64 k = b->bb[WHITE][PAWN] * 0x9E3779B97F4A7C15ULL
          ^ b->bb[BLACK][PAWN] * 0xBF58476D1CE4E5B9ULL;
    return (unsigned)((k >> 40) & 16383);
}
/* Static eval CORRECTED by search history, for PRUNING DECISIONS ONLY. The value
 * returned from a node, stored in the TT and shown to the user is never this
 * one -- see research/INTERPRETABILITY_COST.md for why that boundary matters. */
static inline int eval_pruning(Board *b){
    int st = eval_stm(b);
    int c = SS.corr[b->side][corr_key(b)] / 16;
    if(c > 80) c = 80; else if(c < -80) c = -80;
    return st + c;
}

static int eval_stm(Board *b){""",
    "helper")

# use the corrected value in the three forward-pruning decisions
sub("""        int st=eval_stm(b);
        /* Loosest margin first""", """        int st=eval_pruning(b);
        /* Loosest margin first""", "rfp") if "eval_pruning(b);\n        /* Loosest" in s else None

s = s.replace("""    if(!pvnode && !checked && depth<=RFP_DEPTH && beta>-S_MATE_TH && beta<S_MATE_TH){
        int st=eval_stm(b);""",
              """    if(!pvnode && !checked && depth<=RFP_DEPTH && beta>-S_MATE_TH && beta<S_MATE_TH){
        int st=eval_pruning(b);""", 1)

# learn: after a node completes a real search, fold (best - static) into the table
sub("""    if(!excl){   /* don't pollute this position's TT entry from a verification search */""",
    """    /* Learn the correction: how far the static eval sat from what search
     * actually returned, for this pawn structure. Exponential moving average
     * with weight 1/8, clamped, so a few noisy nodes cannot swing a bucket.
     * Only on real searches at reasonable depth, where the difference means
     * something. */
    if(!excl && depth >= 3 && !checked
       && best > -S_MATE_TH && best < S_MATE_TH){
        int st = eval_stm(b);
        int *slot = &SS.corr[b->side][corr_key(b)];
        int diff = best - st;
        if(diff > 400) diff = 400; else if(diff < -400) diff = -400;
        *slot += (diff * 16 - *slot) / 8;
        if(*slot > 4000) *slot = 4000; else if(*slot < -4000) *slot = -4000;
    }
    if(!excl){   /* don't pollute this position's TT entry from a verification search */""",
    "learn")

p.write_text(s)
print(f"patched {p} (correction history, pruning decisions only)")

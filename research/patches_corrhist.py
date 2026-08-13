"""Correction history: learn where the static eval is systematically wrong, and
use the corrected number for PRUNING DECISIONS ONLY.

Why this and not more pruning. Eleven pruning variants all measured <= 0, and
the one that gave the decisions strictly better information (the TT score) was
WORSE, because refining upward simply made reverse futility fire more often.
The conclusion was that effective branching factor is eval-limited: the search
already prunes as hard as its evaluation supports. So the lever is not pruning
harder, it is making the number the pruning decisions rest on more accurate.

Reverse futility, razoring and the null-move guard all ask the same question --
"will a search confirm this static eval?" -- and answer it with the raw static
eval. That number has a systematic component: for a given pawn structure, the
evaluation is reliably optimistic or reliably pessimistic relative to what a
search returns. That component is learnable during the search itself.

Unlike the TT refinement, this correction is SYMMETRIC. It lowers the estimate
where the evaluation is habitually optimistic -- which is precisely where
over-pruning costs material -- as readily as it raises it.

INTERPRETABILITY IS UNTOUCHED, and deliberately so. The correction is used only
to decide whether to prune; it never changes a returned score, never reaches
qsearch stand-pat, and never reaches the evaluation the breakdown displays. The
search still optimises exactly the number the user is shown. It just makes
better guesses about which branches are not worth looking at.
"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1]) / "core/csearch.c"
s = p.read_text()

# --- the table -------------------------------------------------------------
a = "static double now_sec(void)"
b = """/* Correction history: the running gap between static eval and search result,
 * indexed by side and pawn structure. Pawn structure is the right key -- it is
 * what makes an evaluation habitually optimistic or pessimistic, and it changes
 * rarely, so entries accumulate real evidence. Per-thread: it is learned
 * experience, not shared state, and racing on it would only add noise. */
#define CORR_BITS 14
#define CORR_SIZE (1<<CORR_BITS)
#define CORR_MASK (CORR_SIZE-1)
#define CORR_SCALE 256      /* entries are stored scaled, for integer averaging */
#define CORR_CLAMP (96*CORR_SCALE)   /* never correct by more than ~96cp */
static _Thread_local int CORRH[2][CORR_SIZE];

static inline unsigned corr_index(const Board *b){
    U64 k = (b->bb[WHITE][PAWN]*0x9E3779B97F4A7C15ULL)
          ^ (b->bb[BLACK][PAWN]*0xBF58476D1CE4E5B9ULL);
    return (unsigned)((k>>44) & CORR_MASK);
}

/* The static eval, corrected by what this search has learned about positions
 * with this pawn structure. Used for PRUNING DECISIONS ONLY. */
static inline int corrected_eval(const Board *b, int st){
    int c = CORRH[b->side][corr_index(b)] / CORR_SCALE;
    int e = st + c;
    if(e > S_MATE_TH) e = S_MATE_TH;
    if(e < -S_MATE_TH) e = -S_MATE_TH;
    return e;
}

static void corr_update(const Board *b, int st, int searched){
    int *slot = &CORRH[b->side][corr_index(b)];
    int diff = (searched - st) * CORR_SCALE;
    *slot += (diff - *slot) / 16;          /* exponential moving average */
    if(*slot >  CORR_CLAMP) *slot =  CORR_CLAMP;
    if(*slot < -CORR_CLAMP) *slot = -CORR_CLAMP;
}

static double now_sec(void)"""
assert a in s, "now_sec anchor not found"
s = s.replace(a, b, 1)

# --- use it in reverse futility -------------------------------------------
a = """        int st=eval_stm(b);
        if(st - RFP_MARGIN*depth >= beta){ SS.path_len--; return st; }"""
b = """        int st=eval_stm(b);
        /* decide on the corrected number; RETURN the honest one */
        if(corrected_eval(b,st) - RFP_MARGIN*depth >= beta){
            SS.path_len--; return st; }"""
assert a in s, "RFP block not found"
s = s.replace(a, b, 1)

# --- and in the null-move guard -------------------------------------------
a = "has_non_pawn(b) && eval_stm(b)>=beta){"
b = "has_non_pawn(b) && corrected_eval(b,eval_stm(b))>=beta){"
assert a in s, "null-move guard not found"
s = s.replace(a, b, 1)

# --- learn from every completed non-excluded search ------------------------
a = """    if(!excl){   /* don't pollute this position's TT entry from a verification search */
        int flag = best<=orig_alpha?TT_UPPERF : best>=beta?TT_LOWERF : TT_EXACTF;"""
b = """    if(!excl && !checked && best>-S_MATE_TH && best<S_MATE_TH){
        /* This node just learned what a real search returns here versus what
         * the static eval guessed. Skipped in check, where the static eval is
         * not meaningful, and for mate scores, which are on another scale. */
        corr_update(b, eval_stm(b), best);
    }
    if(!excl){   /* don't pollute this position's TT entry from a verification search */
        int flag = best<=orig_alpha?TT_UPPERF : best>=beta?TT_LOWERF : TT_EXACTF;"""
assert a in s, "TT store anchor not found"
s = s.replace(a, b, 1)

p.write_text(s)
print("correction history applied")

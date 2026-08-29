"""Wire the KPvK bitbase into the search as an exact node value.

Placed beside the existing draw detection, so a node that is exactly king+pawn
vs king returns ground truth instead of an eval estimate. This is a SEARCH-side
value like contempt, not an eval term: no concept, weight or PST changes, so
`evaluate_detailed` is untouched and `eval_check` must stay 0.000000.

Interpretability is arguably improved rather than compromised: "this position is
a tablebase draw" is a more faithful explanation than a heuristic passed-pawn
score, and it is exact.

Correctness details that matter:
  * the bitbase stores WIN vs NOT-WIN for the PAWN side. KPvK has no losses for
    the pawn side, so NOT-WIN is exactly a draw.
  * when Black holds the pawn the board is mirrored vertically (square ^ 56) and
    the side to move flips, because the table is indexed for White-to-win.
  * scores are returned from the SIDE TO MOVE's perspective, matching negamax.
  * a win is scored below a real mate but far above any eval, so the search
    still prefers a faster mate; a draw returns 0 and ignores contempt, because
    a tablebase draw is not a drawish position to be avoided, it is a fact.
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


# csearch.c is #included at the end of cengine.c and carries its own include
# block; eval_data.h is pulled in by ceval.c, not here.
sub("#include <pthread.h>", '#include <pthread.h>\n#include "kpk_data.h"', "include")

# placed just before eval_stm, which is after S_MATE is defined
sub("static int eval_stm(Board *b){",
    """/* KPvK bitbase probe. Returns 1 and sets *score if this node is exactly king +
 * one pawn vs king; 0 otherwise. Exact, generated from syzygy. */
static int kpk_probe(const Board *b, int ply, int *score){
    U64 wp=b->bb[WHITE][PAWN], bp=b->bb[BLACK][PAWN];
    if(b->bb[WHITE][KNIGHT]|b->bb[WHITE][BISHOP]|b->bb[WHITE][ROOK]|b->bb[WHITE][QUEEN]
     | b->bb[BLACK][KNIGHT]|b->bb[BLACK][BISHOP]|b->bb[BLACK][ROOK]|b->bb[BLACK][QUEEN])
        return 0;
    int nw=__builtin_popcountll(wp), nb=__builtin_popcountll(bp);
    if(nw+nb != 1) return 0;
    int strong = nw ? WHITE : BLACK;                 /* side holding the pawn */
    int wk=__builtin_ctzll(b->bb[strong][KING]);
    int bk=__builtin_ctzll(b->bb[!strong][KING]);
    int psq=__builtin_ctzll(nw ? wp : bp);
    if(strong==BLACK){ wk^=56; bk^=56; psq^=56; }    /* mirror so the pawn goes up */
    int stm = (b->side==strong) ? 0 : 1;             /* 0 = pawn side to move */
    long idx = ((long)(stm*64 + wk)*64 + bk)*48 + (psq - 8);
    int win = (KPK_BITS[idx>>3] >> (idx&7)) & 1;
    if(!win){ *score = 0; return 1; }                /* exact draw, ignores contempt */
    int v = S_MATE/2 - ply;                          /* below a real mate, above any eval */
    *score = (b->side==strong) ? v : -v;
    return 1;
}

static int eval_stm(Board *b){""",
    "probe")

sub("""    if(!done && (is_rep(h,b->hm)||insufficient(b))){ ret=drawv; done=1; }""",
    """    if(!done && (is_rep(h,b->hm)||insufficient(b))){ ret=drawv; done=1; }
    /* exact KPvK knowledge beats any evaluation of the same position */
    if(!done){ int kv; if(kpk_probe(b,ply,&kv)){ ret=kv; done=1; } }""",
    "call site")

p.write_text(s)
print(f"patched {p} (KPvK bitbase in search)")

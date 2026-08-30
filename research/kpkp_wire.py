"""Wire the KPvKP bitbase into the search: exact pawn-ending knowledge.

Loaded from core/kpkp.bin at first use rather than embedded, because 2.25MB is
impractical as a C array but trivial as a file. Falls back silently to ordinary
search if the file is missing, so a checkout without it still works.

IMPORTANT asymmetry against the KPvK probe. That one stores WIN vs NOT-WIN and
NOT-WIN is exactly a draw, because the pawn side cannot lose KPvK. Here White CAN
lose, so a clear bit means "not a proven White win" and carries NO information --
it may be a draw or a Black win. So only a SET bit is trusted; everything else
falls through to ordinary evaluation. Getting this backwards would assert draws
in lost positions, which is the confidently-wrong failure this whole approach is
designed to avoid.

The same 50-move guard as KPvK applies, and for the same reason: syzygy WDL is
DTZ-agnostic, so a proven win is only trustworthy while the halfmove clock is
low.

The board is mirrored when Black is the side we are testing for a win, so one
table serves both colours.

Interpretability: a search-side terminal value like contempt and KPvK, not an
eval term. eval_check must stay 0.000000.

Usage: kpkp_wire.py <worktree>
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


sub("static int kpk_probe(const Board *b, int ply, int *score){",
    """/* KPvKP bitbase, loaded from core/kpkp.bin. A SET bit means "White wins".
 * A clear bit carries NO information (White may be losing), unlike the KPvK
 * table where not-win is exactly a draw -- so only set bits are ever trusted. */
static unsigned char *KPKP = 0;
static int kpkp_tried = 0;
static void kpkp_load(void){
    if(kpkp_tried) return;
    kpkp_tried = 1;
    FILE *f = fopen("core/kpkp.bin", "rb");
    if(!f) f = fopen(KPKP_PATH, "rb");
    if(!f) return;
    KPKP = (unsigned char*)malloc(2359296);
    if(KPKP && fread(KPKP, 1, 2359296, f) != 2359296){ free(KPKP); KPKP = 0; }
    fclose(f);
}
static int kpkp_probe(const Board *b, int ply, int *score){
    if(b->hm > 40) return 0;                 /* WDL is DTZ-agnostic; see kpk_probe */
    U64 wp=b->bb[WHITE][PAWN], bp=b->bb[BLACK][PAWN];
    if(b->bb[WHITE][KNIGHT]|b->bb[WHITE][BISHOP]|b->bb[WHITE][ROOK]|b->bb[WHITE][QUEEN]
     | b->bb[BLACK][KNIGHT]|b->bb[BLACK][BISHOP]|b->bb[BLACK][ROOK]|b->bb[BLACK][QUEEN])
        return 0;
    if(__builtin_popcountll(wp)!=1 || __builtin_popcountll(bp)!=1) return 0;
    kpkp_load();
    if(!KPKP) return 0;
    /* test both colours: the table is indexed for a WHITE win, so for a Black
     * win the board is mirrored vertically and the colours swapped. */
    for(int side=0; side<2; side++){
        int wk, bk, wpi, bpi, stm;
        if(side==0){
            wk=__builtin_ctzll(b->bb[WHITE][KING]); bk=__builtin_ctzll(b->bb[BLACK][KING]);
            wpi=__builtin_ctzll(wp)-8; bpi=__builtin_ctzll(bp)-8;
            stm = (b->side==WHITE) ? 0 : 1;
        } else {
            wk=__builtin_ctzll(b->bb[BLACK][KING])^56; bk=__builtin_ctzll(b->bb[WHITE][KING])^56;
            wpi=(__builtin_ctzll(bp)^56)-8; bpi=(__builtin_ctzll(wp)^56)-8;
            stm = (b->side==BLACK) ? 0 : 1;
        }
        if(wpi<0||wpi>=48||bpi<0||bpi>=48) continue;
        long i = (((long)(stm*64 + wk)*64 + bk)*48 + wpi)*48 + bpi;
        if((KPKP[i>>3] >> (i&7)) & 1){
            int winner = (side==0) ? WHITE : BLACK;
            int v = S_MATE/2 - ply;
            *score = (b->side==winner) ? v : -v;
            return 1;
        }
    }
    return 0;                                /* clear bit: no information */
}

static int kpk_probe(const Board *b, int ply, int *score){""",
    "probe")

sub("""    if(!done){ int kv; if(kpk_probe(b,ply,&kv)){ ret=kv; done=1; } }""",
    """    if(!done){ int kv; if(kpk_probe(b,ply,&kv)){ ret=kv; done=1; } }
    if(!done){ int kv; if(kpkp_probe(b,ply,&kv)){ ret=kv; done=1; } }""",
    "call site")

sub("#include <pthread.h>",
    f'#include <pthread.h>\n#include <stdio.h>\n#define KPKP_PATH "{WT}/core/kpkp.bin"',
    "include")

p.write_text(s)
print(f"patched {p} (KPvKP bitbase in search)")

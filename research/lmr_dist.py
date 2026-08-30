"""What does |eval - material| look like AT LMR-ELIGIBLE NODES?

The uncertainty-aware RFP attempt failed partly because its thresholds (43 and
94cp) were taken from referee ROOT positions, while the rule fires at interior
nodes at remaining depth <= 6. The distributions are different, so the buckets
probably did not split those nodes anywhere near their terciles and the
modulation barely changed behaviour.

So measure the distribution where the rule actually fires before choosing any
threshold. LMR applies at depth >= 3, on quiet moves, not in check, from move
index 3 -- a very different node population from the root.

Emits a histogram of |eval_stm - material_stm| over every LMR-eligible node in a
fixed-depth search, from which the terciles can be read directly.
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


sub("static int g_threads = 1;",
    """static int g_threads = 1;
/* distribution instrumentation (measurement build only): |eval - material| at
 * LMR-eligible nodes, bucketed in 20cp steps */
#define UB 32
long g_unc_hist[UB];
static inline void unc_note(int u){ int b=u/20; if(b<0)b=0; if(b>=UB)b=UB-1; g_unc_hist[b]++; }""",
    "counters")

# record at the LMR site, before any reduction is chosen
sub("""            if(depth>=3 && quiet && !checked){ if(i>=12)red=3; else if(i>=3)red=2;""",
    """            if(depth>=3 && quiet && !checked && i>=3){
                int _m = 0;
                for(int _p=PAWN;_p<=QUEEN;_p++)
                    _m += SEEV[_p]*(__builtin_popcountll(b->bb[b->side][_p])
                                  - __builtin_popcountll(b->bb[!b->side][_p]));
                int _d = eval_stm(b) - _m; if(_d<0) _d = -_d;
                unc_note(_d);
            }
            if(depth>=3 && quiet && !checked){ if(i>=12)red=3; else if(i>=3)red=2;""",
    "lmr site")

sub("void c_set_threads(int n){",
    """void c_unc_stats(long *h){ for(int i=0;i<UB;i++) h[i]=g_unc_hist[i]; }
void c_unc_reset(void){ for(int i=0;i<UB;i++) g_unc_hist[i]=0; }
void c_set_threads(int n){""",
    "accessor")

p.write_text(s)
print(f"patched {p} (uncertainty distribution at LMR nodes)")

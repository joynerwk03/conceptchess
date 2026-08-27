"""Measure the ASPIRATION RE-SEARCH rate BY DEPTH. Unexplored, and it would explain the EBF.

Our EBF rises with depth (1.80 -> 2.11) where SF11's falls (1.98 -> 1.51), and
the cause is still open after ruling out the TT (size, replacement, hit rate),
check extensions, futility width, move ordering and the null-move schedule.

Aspiration is the one mechanism that inflates DEEP iterations specifically. Each
fail-high or fail-low re-runs the ENTIRE root search at that depth, so a
re-search rate that grows with depth multiplies exactly the iterations the EBF
measures -- and it would look like a fat tree while actually being repeated
work. The existing comment on `delta` records "17.1% of root loops at depth 9",
measured at ONE depth, which cannot see a trend.

This matters beyond diagnosis: a re-search is repeated work on the SAME tree, so
removing it discards no information. It is in the class of changes that has
worked here (spend information) rather than the class that has not (thinning),
and it is priceable by the +40.5 Elo/doubling speed curve, which applies to
searching the same tree faster and does not apply to a tree reduction.

Counters: `runs[d]` root searches performed at nominal depth d, `iters[d]` depth
iterations started. runs/iters = 1.0 means every window held first try.
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
/* aspiration instrumentation (measurement build only), by nominal depth */
#define ASPD 40
long g_asp_runs[ASPD], g_asp_iters[ASPD];
static inline int aspd_(int d){ return d<0?0:(d>=ASPD?ASPD-1:d); }""",
    "counters")

sub("""        for(;;){
            int a=alpha0, bt=beta0;""",
    """        g_asp_iters[aspd_(depth)]++;
        for(;;){
            g_asp_runs[aspd_(depth)]++;
            int a=alpha0, bt=beta0;""",
    "root loop")

sub("void c_set_threads(int n){",
    """void c_asp_stats(long *r, long *i){
    for(int k=0;k<ASPD;k++){ r[k]=g_asp_runs[k]; i[k]=g_asp_iters[k]; }
}
void c_asp_reset(void){
    for(int k=0;k<ASPD;k++) g_asp_runs[k]=g_asp_iters[k]=0;
}
void c_set_threads(int n){""",
    "accessor")

p.write_text(s)
print(f"patched {p} (aspiration re-searches by depth)")

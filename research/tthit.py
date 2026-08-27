"""Measure TT probe hit-rate BY DEPTH. This is the one unexplained measurement left.

Our effective branching factor RISES with depth (1.80 from depth 8->10, 2.11
from 10->12) while Stockfish 11's FALLS (1.98 -> 1.51). A falling EBF means each
deeper iteration costs proportionally less than the last -- the search converges
on what it already knows. A rising one means it diverges.

The standard mechanism for a converging search is the transposition table: the
previous iteration proved things the current one can cut on immediately. TT SIZE
was tested (64MB vs 512MB, no effect) and bucketed replacement was tested
(inconsistent), but the HIT RATE has never been measured, and least of all
broken down by depth. If it collapses at deep remaining-depth, that is the
mechanism behind the rising EBF and it is a different fault from anything tried
this session.

Counts, per remaining-depth bucket:
  probes    negamax TT lookups
  hits      key matched
  cuts      hit AND deep enough AND the bound allowed an immediate return

`cuts` is the number that matters. A hit that is too shallow to cut still costs a
probe and saves only move ordering.
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
/* TT instrumentation (measurement build only), bucketed by remaining depth */
#define TTB 8
long g_tt_probe[TTB], g_tt_hit[TTB], g_tt_cut[TTB];
static inline int ttb_(int d){ int b=d/3; return b<0?0:(b>=TTB?TTB-1:b); }""",
    "counters")

sub("""        TTEntry *e=&TT[h&TT_MASK];
        if(e->key==h){ unsigned int mdf=e->mdf;""",
    """        int _b = ttb_(depth); g_tt_probe[_b]++;
        TTEntry *e=&TT[h&TT_MASK];
        if(e->key==h){ g_tt_hit[_b]++; unsigned int mdf=e->mdf;""",
    "probe/hit")

sub("""                if(tt_flag==TT_EXACTF){ ret=tt_score; done=1; }""",
    """                if(tt_flag==TT_EXACTF){ ret=tt_score; done=1; g_tt_cut[_b]++; }""",
    "exact cut")
sub("""                else if(tt_flag==TT_LOWERF && tt_score>=beta){ ret=tt_score; done=1; }""",
    """                else if(tt_flag==TT_LOWERF && tt_score>=beta){ ret=tt_score; done=1; g_tt_cut[_b]++; }""",
    "lower cut")
sub("""                else if(tt_flag==TT_UPPERF && tt_score<=alpha){ ret=tt_score; done=1; }""",
    """                else if(tt_flag==TT_UPPERF && tt_score<=alpha){ ret=tt_score; done=1; g_tt_cut[_b]++; }""",
    "upper cut")

sub("void c_set_threads(int n){",
    """void c_tt_stats(long *pr, long *hi, long *cu){
    for(int i=0;i<TTB;i++){ pr[i]=g_tt_probe[i]; hi[i]=g_tt_hit[i]; cu[i]=g_tt_cut[i]; }
}
void c_tt_reset(void){
    for(int i=0;i<TTB;i++) g_tt_probe[i]=g_tt_hit[i]=g_tt_cut[i]=0;
}
void c_set_threads(int n){""",
    "accessor")

p.write_text(s)
print(f"patched {p} (TT hit-rate by depth)")

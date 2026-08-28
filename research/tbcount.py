"""Price in-search tablebases BEFORE porting tbprobe. How many nodes are even TB-reachable?

Porting SF11's tbprobe to this Board is hours of real work, so measure the
opportunity first -- the same discipline as "probe before refactoring", which
killed two planned rewrites here for the cost of minutes.

The tables on this box are 3-4-5 man, and the ROOT already probes them, so the
gain lives strictly in nodes where the root has >5 pieces but the search reaches
<=5. Counting those directly bounds the whole idea:

  * a few percent of nodes -> a real gain, worth the port
  * a fraction of a percent -> the port cannot pay and this is closed cheaply

Counted by piece count so the answer also says whether 6-man tables would change
the picture (they are not on this box, but it is free to know).

Positions come from the referee book, which is where our games actually start,
searched at a realistic depth rather than a toy one.
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
/* TB opportunity instrumentation (measurement build only) */
long g_pc_hist[33], g_pc_total;""",
    "counters")

# count every negamax node by piece count
sub("""    if(b->hm >= 100 && !in_check(b,b->side)){ ret=drawv; done=1; }""",
    """    { int _pc = 0; for(int _c=0;_c<2;_c++) for(int _t=1;_t<=6;_t++)
          _pc += __builtin_popcountll(b->bb[_c][_t]);
      if(_pc>32) _pc=32; g_pc_hist[_pc]++; g_pc_total++; }
    if(b->hm >= 100 && !in_check(b,b->side)){ ret=drawv; done=1; }""",
    "node count")

sub("void c_set_threads(int n){",
    """void c_pc_stats(long *h, long *tot){
    for(int i=0;i<33;i++) h[i]=g_pc_hist[i];
    *tot = g_pc_total;
}
void c_pc_reset(void){ for(int i=0;i<33;i++) g_pc_hist[i]=0; g_pc_total=0; }
void c_set_threads(int n){""",
    "accessor")

p.write_text(s)
print(f"patched {p} (piece-count histogram)")

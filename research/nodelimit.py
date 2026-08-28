"""Add an opt-in node limit to the search, so the iso-node screen stops wasting half its budget.

The iso-node screen currently picks the deepest FIXED-DEPTH search that fits the
baseline's node count. Depth is integral and the branching factor is ~1.8, so
the chosen depth typically uses only about half the budget -- the next ply would
overshoot. That biases against the candidate (conservative, not misleading) but
it blunts the instrument by roughly one ply.

A real node limit removes the granularity entirely: search to any depth and stop
exactly at the budget.

Design: a separate setter rather than a new `c_search` parameter, so the ctypes
signature of the hot entry point does not change and nothing else has to be
touched. Default 0 means unlimited, so this is behaviour-neutral for every
existing caller -- the check rides inside the existing 1-in-2048 poll that
already tests the clock, so it costs nothing measurable.

Node counting is per search-thread. The screen runs single-threaded, which is
the only regime where an exact node budget is meaningful anyway.
"""
import pathlib
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1
                    else "/home/joynerwk03/mission-control/projects/conceptchess")

# --- C side -----------------------------------------------------------------
p = ROOT / "core/csearch.c"
s = p.read_text()

anchor = "static int g_threads = 1;"
assert s.count(anchor) == 1, "threads global not found"
s = s.replace(anchor, anchor + """
/* Optional hard node budget. 0 = unlimited, which is every existing caller, so
 * this is behaviour-neutral by default. Used by the iso-node referee screen to
 * compare configurations at EQUAL work instead of equal nominal depth. */
static long g_node_limit = 0;""", 1)

old_stop = "if(!(SS.nodes&2047) && (g_stop || now_sec()>SS.stop_time)){ SS.stopped=1; return 0; }"
n = s.count(old_stop)
assert n == 2, f"expected 2 stop checks, found {n}"
s = s.replace(old_stop,
              "if(!(SS.nodes&2047) && (g_stop || now_sec()>SS.stop_time)){ SS.stopped=1; return 0; }\n"
              "    if(g_node_limit && SS.nodes >= g_node_limit){ SS.stopped=1; return 0; }")

anchor2 = "void c_set_threads(int n){"
assert s.count(anchor2) == 1, "c_set_threads not found"
s = s.replace(anchor2, "void c_set_node_limit(long n){ g_node_limit = n; }\n" + anchor2, 1)
p.write_text(s)
print(f"patched {p}")

# --- Python side ------------------------------------------------------------
q = ROOT / "engine/core.py"
t = q.read_text()
anchor3 = "def set_threads(n):"
assert t.count(anchor3) == 1, "set_threads not found in core.py"
t = t.replace(anchor3, '''def set_node_limit(n):
    """Cap the search at n nodes (0 = unlimited). Reads _lib like set_threads."""
    if _lib is not None and hasattr(_lib, "c_set_node_limit"):
        _lib.c_set_node_limit.argtypes = [ctypes.c_long]
        _lib.c_set_node_limit(int(n))


''' + anchor3, 1)
q.write_text(t)
print(f"patched {q}")

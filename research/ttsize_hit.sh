#!/bin/bash
# Is the falling TT hit rate EVICTION or just NOVELTY?
#
# At the same remaining depth the hit rate falls as the search deepens (66.3% ->
# 51.0% at rem 3-5). Two explanations predict opposite things:
#
#   eviction  the 4M-entry table is churned, deep entries are overwritten
#             -> a bigger table RAISES the hit rate
#   novelty   a depth-12 search simply visits 15x more distinct positions
#             -> a bigger table changes nothing
#
# TT size was tested before on Elo and node counts ("no effect"), never on the
# hit rate, which is the quantity it directly controls. Also clear the table
# between positions: it is allocated once and never reset, so the numbers from
# the first run were polluted by entries from earlier positions.
#
# 22 bits = 4M entries = 64MB (current); 25 bits = 32M = 512MB.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
cd "$CC"
for B in 22 25; do
  WT="$CC/research/worktrees/tts$B"
  git worktree remove --force "research/worktrees/tts$B" 2>/dev/null || true
  git worktree add "research/worktrees/tts$B" HEAD >/dev/null 2>&1
  python3 "$R/tthit.py" "$WT" >/dev/null
  sed -i "s/^#define TT_BITS 22/#define TT_BITS $B/" "$WT/core/csearch.c"
  grep -q "^#define TT_BITS $B" "$WT/core/csearch.c" || { echo "TT_BITS patch failed"; exit 1; }
  (cd "$WT" && sh core/build.sh >/dev/null 2>&1)
  [ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED $B"; exit 1; }
done

for B in 22 25; do
  WT="$CC/research/worktrees/tts$B"
  cd "$WT"
  TTB=$B PYTHONPATH=. "$CC/.venv/bin/python" - <<'PY'
import ctypes, os, chess
from engine.engine import Engine
from engine import core
assert core.HAS_CORE, "REFUSING TO PROBE: no compiled core"
core.set_threads(1)
lib = core._lib
A = ctypes.c_long * 8
lib.c_tt_stats.argtypes = [A, A, A]; lib.c_tt_stats.restype = None
lib.c_tt_reset.restype = None

BOOK = "/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
fens = [" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::40][:24]

bits = os.environ["TTB"]
print(f"\n=== TT_BITS {bits} ({(1<<int(bits))*16//(1024*1024)} MB) ===")
for depth in (8, 12):
    lib.c_tt_reset()
    tot = 0
    for f in fens:
        eng = Engine(use_book=False, use_tablebase=False)   # fresh TT state per position
        r = eng.best_move(chess.Board(f), movetime=999.0, max_depth=depth)
        tot += getattr(r, "nodes", 0) or 0
    pr, hi, cu = A(), A(), A()
    lib.c_tt_stats(pr, hi, cu)
    print(f"  depth {depth}  nodes {tot:,}")
    for b in range(8):
        if pr[b] == 0:
            continue
        print(f"    rem {b*3}-{b*3+2:<6}{pr[b]:>12,} probes  "
              f"hit {100*hi[b]/pr[b]:5.1f}%  cut {100*cu[b]/pr[b]:5.1f}%")
PY
done

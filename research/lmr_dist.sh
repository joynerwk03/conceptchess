#!/bin/bash
# Read the |eval - material| distribution at LMR-eligible nodes, and print the
# terciles that any modulation rule should actually use.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
WT="$CC/research/worktrees/lmrdist"
cd "$CC"
git worktree remove --force research/worktrees/lmrdist 2>/dev/null || true
git worktree add research/worktrees/lmrdist HEAD >/dev/null 2>&1
"$PY" /home/joynerwk03/ccruns/lmr_dist.py "$WT"
(cd "$WT" && sh core/build.sh >/dev/null 2>&1)
[ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED"; exit 1; }

cd "$WT"
PYTHONPATH=. "$PY" - <<'PY'
import ctypes, chess
from engine.engine import Engine
from engine import core
assert core.HAS_CORE
core.set_threads(1)
lib = core._lib
H = ctypes.c_long * 32
lib.c_unc_stats.argtypes = [H]; lib.c_unc_stats.restype = None
lib.c_unc_reset.restype = None

BOOK = "/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
fens = [" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::50][:20]
lib.c_unc_reset()
for f in fens:
    Engine(use_book=False, use_tablebase=False).best_move(
        chess.Board(f), movetime=999.0, max_depth=10)
h = H(); lib.c_unc_stats(h)
tot = sum(h)
print(f"\n{tot:,} LMR-eligible nodes\n")
print(f"{'|eval-material|':>18}{'count':>12}{'share':>8}{'cum':>8}")
cum = 0
marks = {}
for i in range(32):
    if h[i] == 0:
        continue
    cum += h[i]
    frac = cum / tot
    lo = i * 20
    print(f"  {lo:4d}-{lo+19:<10}{h[i]:>12,}{100*h[i]/tot:>7.1f}%{100*frac:>7.1f}%")
    for q in (0.333, 0.667):
        if q not in marks and frac >= q:
            marks[q] = lo + 20
print(f"\nterciles at this node population: "
      f"{marks.get(0.333,'?')}cp and {marks.get(0.667,'?')}cp")
print("(the RFP attempt used 43 and 94, taken from ROOT positions)")
PY

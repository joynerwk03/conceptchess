#!/bin/bash
# Does the TT stop cutting at depth? That would explain the rising EBF.
#
# Ours rises 1.80 -> 2.11 with depth; Stockfish 11's falls 1.98 -> 1.51. A
# converging search is one whose deeper iterations cut early on what the
# previous iteration proved, and the transposition table is what carries that.
# Size and replacement policy were both tested; the hit rate never was.
#
# Single thread and a fixed depth, so the counts are deterministic. Buckets are
# remaining depth in steps of 3.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
WT="$CC/research/worktrees/tth"
cd "$CC"
git worktree remove --force research/worktrees/tth 2>/dev/null || true
git worktree add research/worktrees/tth HEAD >/dev/null 2>&1
python3 "$R/tthit.py" "$WT"
(cd "$WT" && sh core/build.sh 2>&1 | grep -iE "\berror\b" | head -3 || true)
[ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED"; exit 1; }

cd "$WT"
PYTHONPATH=. "$CC/.venv/bin/python" - <<'PY'
import ctypes, chess
from engine.engine import Engine
from engine import core
core.set_threads(1)
lib = core._lib
lib.c_tt_reset.restype = None
A = ctypes.c_long * 8
lib.c_tt_stats.argtypes = [A, A, A]
lib.c_tt_stats.restype = None

BOOK="/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
fens=[" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::40][:24]
eng = Engine(use_book=False, use_tablebase=False)

for depth in (8, 12):
    lib.c_tt_reset()
    for f in fens:
        eng.best_move(chess.Board(f), movetime=999.0, max_depth=depth)
    pr, hi, cu = A(), A(), A()
    lib.c_tt_stats(pr, hi, cu)
    print(f"\n--- search depth {depth} ---")
    print(f"  {'rem depth':<12}{'probes':>12}{'hit%':>8}{'cut%':>8}")
    for b in range(8):
        if pr[b] == 0:
            continue
        print(f"  {b*3}-{b*3+2:<10}{pr[b]:>12,}{100*hi[b]/pr[b]:>7.1f}%"
              f"{100*cu[b]/pr[b]:>7.1f}%")
PY

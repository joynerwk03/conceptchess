#!/bin/bash
# Does the aspiration re-search rate GROW with depth? Single thread, fixed depth,
# so the counts are deterministic. Search to depth 14 and read the rate at each
# nominal depth on the way up.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
WT="$CC/research/worktrees/asp"
cd "$CC"
git worktree remove --force research/worktrees/asp 2>/dev/null || true
git worktree add research/worktrees/asp HEAD >/dev/null 2>&1
"$PY" "$R/asp.py" "$WT"
cd "$WT"
sh core/build.sh >/dev/null 2>&1
if [ ! -f core/libcengine.so ]; then echo "BUILD FAILED"; exit 1; fi

PYTHONPATH=. "$PY" - <<'PY'
import ctypes, chess
from engine.engine import Engine
from engine import core
assert core.HAS_CORE, "REFUSING TO PROBE: no compiled core"
core.set_threads(1)
lib = core._lib
A = ctypes.c_long * 40
lib.c_asp_stats.argtypes = [A, A]; lib.c_asp_stats.restype = None
lib.c_asp_reset.restype = None

BOOK = "/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
fens = [" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::25][:40]
lib.c_asp_reset()
for f in fens:
    Engine(use_book=False, use_tablebase=False).best_move(
        chess.Board(f), movetime=999.0, max_depth=14)
r, i = A(), A()
lib.c_asp_stats(r, i)
print(f"\n{'depth':>6}{'iters':>9}{'runs':>9}{'runs/iter':>12}{'re-search%':>12}")
for d in range(1, 20):
    if i[d] == 0:
        continue
    print(f"{d:>6}{i[d]:>9}{r[d]:>9}{r[d]/i[d]:>12.3f}{100*(r[d]-i[d])/i[d]:>11.1f}%")
PY

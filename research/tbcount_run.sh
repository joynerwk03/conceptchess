#!/bin/bash
# How much of the search is tablebase-reachable? Two regimes, because the answer
# depends entirely on where the game is: book openings (where our games start)
# and real endgames (where TBs would actually fire).
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
WT="$CC/research/worktrees/tbc"
cd "$CC"
git worktree remove --force research/worktrees/tbc 2>/dev/null || true
git worktree add research/worktrees/tbc HEAD >/dev/null 2>&1
"$PY" /home/joynerwk03/ccruns/tbcount.py "$WT"
(cd "$WT" && sh core/build.sh >/dev/null 2>&1)
[ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED"; exit 1; }

cd "$WT"
PYTHONPATH=. "$PY" - <<'PY'
import ctypes, chess
from engine.engine import Engine
from engine import core
assert core.HAS_CORE, "REFUSING TO PROBE: no compiled core"
core.set_threads(1)
lib = core._lib
H = ctypes.c_long * 33
lib.c_pc_stats.argtypes = [H, ctypes.POINTER(ctypes.c_long)]
lib.c_pc_stats.restype = None
lib.c_pc_reset.restype = None

BOOK = "/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
book = [" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::40][:24]
# real endgames: 7-10 pieces, the regime where a 5-man probe plausibly fires
endgames = [
    "8/5pk1/8/3pP2p/pB6/4KP2/7P/8 b - - 3 55",
    "8/8/4kp2/3p4/p2P1B2/4PK2/8/8 w - - 0 1",
    "8/6pk/8/8/1P6/5K2/6r1/3R4 w - - 0 1",
    "8/8/8/4kp2/8/4KP2/8/8 w - - 0 1",
    "8/2k5/8/8/3P4/3K4/8/7r w - - 0 1",
    "6k1/5ppp/8/8/8/8/5PPP/1R4K1 w - - 0 1",
]

for name, fens, depth in (("book openings", book, 12), ("endgames", endgames, 16)):
    lib.c_pc_reset()
    for f in fens:
        Engine(use_book=False, use_tablebase=False).best_move(
            chess.Board(f), movetime=999.0, max_depth=depth)
    h, tot = H(), ctypes.c_long()
    lib.c_pc_stats(h, ctypes.byref(tot))
    t = tot.value
    le5 = sum(h[i] for i in range(6))
    le6 = sum(h[i] for i in range(7))
    le7 = sum(h[i] for i in range(8))
    print(f"\n{name}: {t:,} nodes")
    print(f"  <=5 pieces (tables we HAVE): {le5:,}  = {100*le5/t:.4f}%")
    print(f"  <=6 pieces:                  {le6:,}  = {100*le6/t:.4f}%")
    print(f"  <=7 pieces:                  {le7:,}  = {100*le7/t:.4f}%")
PY

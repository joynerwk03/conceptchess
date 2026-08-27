#!/bin/bash
# Does the TT starve at 16 THREADS? Every TT test so far ran at 1 thread.
#
# TT size measured "no effect" and the hit-rate probe found novelty rather than
# eviction -- both at CC_THREADS=1, where a depth-12 search loads only a few
# percent of a 4M-entry table. At 16 threads the same table absorbs ~16x the
# store rate, which is the one regime where eviction is plausible. And the
# recorded SMP numbers are odd: 8->16 threads is worth only +22 Elo, and the
# depth probe reads T=10 at 15.46 against T=16 at 15.46 -- sixteen threads
# buying ZERO depth over ten.
#
# This is the goal configuration (16 threads, 1.0s), and unlike a tree reduction
# a deeper search at the same time control IS priceable by +40.5 Elo/doubling:
# it is the same tree searched further, not a tree with information removed.
#
# The probe swings ~0.35 plies, so read nothing smaller. Passes are INTERLEAVED
# A B B A so drift cannot land on one arm.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
cd "$CC"

for B in 25 27; do
  WT="$CC/research/worktrees/tt$B"
  git worktree remove --force "research/worktrees/tt$B" 2>/dev/null || true
  git worktree add "research/worktrees/tt$B" HEAD >/dev/null 2>&1
  sed -i "s/^#define TT_BITS 22/#define TT_BITS $B/" "$WT/core/csearch.c"
  grep -q "^#define TT_BITS $B" "$WT/core/csearch.c" || { echo "patch failed $B"; exit 1; }
  (cd "$WT" && sh core/build.sh >/dev/null 2>&1)
  if [ ! -f "$WT/core/libcengine.so" ]; then echo "BUILD FAILED $B"; exit 1; fi
  echo "built TT_BITS $B ($(( (1<<B)*16/1048576 )) MB)"
done

for PASS in 1 2 3 4; do
  case $PASS in 1|4) ORDER="22 25 27";; *) ORDER="27 25 22";; esac
  for V in $ORDER; do
    if [ "$V" = 22 ]; then D="$CC"; else D="$CC/research/worktrees/tt$V"; fi
    (cd "$D" && VAR=$V PYTHONPATH=. "$PY" - <<'PY'
import os, chess
from engine.engine import Engine
from engine import core
assert core.HAS_CORE, "REFUSING TO PROBE: no compiled core"
core.set_threads(16)
BOOK = "/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
fens = [" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::37][:16]
tot = 0.0
for f in fens:
    r = Engine(use_book=False, use_tablebase=False).best_move(
        chess.Board(f), movetime=1.0)
    tot += getattr(r, "depth", 0) or 0
print(f"TT_BITS {os.environ['VAR']}  mean depth {tot/len(fens):.2f}")
PY
    )
  done
done

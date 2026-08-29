#!/bin/bash
# Refine contempt. It is the only change that has worked, and its optimum is
# known only coarsely: 15 pooled to about +8 Elo over 4800 slots, 30 was mixed
# and rejected (-30.4 on one anchor). Nothing between was tested, and nothing
# below 15 either.
#
# Tested HEAD-TO-HEAD against the merged 15, not against no-contempt: the
# question is whether 15 is the right value, and a paired comparison of 10 vs 15
# and 22 vs 15 answers it with far less noise than re-deriving each from zero.
#
# The screen cannot judge this. Contempt changes draw scores, which barely moves
# move choice against SF11's MultiPV table in non-drawish positions, so it needs
# games.
#
# Two anchors near our gate-configuration strength (~2840 at 1 thread, 0.3s).
# Decision rule fixed BEFORE the run: adopt a new value only if BOTH anchors
# favour it over 15. Same rule that rejected deep-region LMR and contempt 30.
#
# ETA: 2 values x 2 anchors x 600 slots at 0.3s, concurrency 6 -> ~2.5 hours.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
cd "$CC"

for C in 10 22; do
  WT="$CC/research/worktrees/cont$C"
  git worktree remove --force "research/worktrees/cont$C" 2>/dev/null || true
  git worktree add "research/worktrees/cont$C" HEAD >/dev/null 2>&1
  sed -i "s/int drawv = (ply & 1) ? 15 : -15;/int drawv = (ply \& 1) ? $C : -$C;/" \
      "$WT/core/csearch.c"
  grep -q "? $C : -$C;" "$WT/core/csearch.c" || { echo "patch failed $C"; exit 1; }
  (cd "$WT" && sh core/build.sh >/dev/null 2>&1)
  [ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED $C"; exit 1; }
  echo "  contempt $C eval_check: $(cd "$WT" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
done

for C in 10 22; do
  WT="$CC/research/worktrees/cont$C"
  for ANCHOR in stockfish:2800 stockfish:2900; do
    echo ""
    echo "=== contempt $C vs merged 15, anchor $ANCHOR (positive favours $C) ==="
    (cd "$WT" && PYTHONPATH=. "$PY" -u -m research.abgate \
       --games 300 --opponent "$ANCHOR" --baseline-cwd "$CC" \
       --movetime 0.3 --threads 1 --concurrency 6 2>&1 | grep -vE '^game ' | tail -10)
  done
done

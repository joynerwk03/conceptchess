#!/bin/bash
# Two-anchor gate for the KPvK bitbase.
#
# Rule fixed BEFORE the run: merge only if BOTH anchors are non-negative. This is
# EXACT knowledge replacing an eval estimate, so unlike a heuristic it cannot be
# wrong at the node; the only risk is that it changes search shape badly. Hence a
# non-negative bar rather than strictly positive, and the expected effect is
# small because KPvK nodes are rare outside endgames (0.0000% of opening nodes).
#
# ETA: 2 anchors x 600 slots at 0.3s, concurrency 6 -> ~2 hours.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
WT="$CC/research/worktrees/kpk"

if [ ! -f "$WT/core/libcengine.so" ]; then
  echo "REFUSING TO GATE: kpk worktree not built"
  exit 1
fi

cd "$CC"
for ANCHOR in stockfish:2800 stockfish:2900; do
  echo ""
  echo "=== KPvK bitbase vs baseline, anchor ${ANCHOR} ==="
  cd "$WT"
  PYTHONPATH=. "$PY" -u -m research.abgate \
    --games 300 --opponent "${ANCHOR}" --baseline-cwd "$CC" \
    --movetime 0.3 --threads 1 --concurrency 6 2>&1 | grep -vE '^game ' | tail -10
  cd "$CC"
done

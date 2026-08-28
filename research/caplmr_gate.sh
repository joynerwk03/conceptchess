#!/bin/bash
# Two-anchor gate for capture LMR.
#
# Screened at d_mean -0.998 (t -1.61) with the calibration anchor holding, which
# earns games rather than a merge. Decision rule fixed BEFORE the run: merge only
# if BOTH anchors are positive. Same rule that rejected deep-region LMR at
# -16.9/-31.8 and contempt 30.
#
# Anchors chosen near this engine's strength AT THE GATE CONFIGURATION (1 thread,
# 0.3s, ~2840 measured), because information per game is highest near 50% -- and
# because gating contempt against a 3000 anchor, where we score 27%, is what
# produced a misleading first reading there.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
cd "$CC"

WT="$CC/research/worktrees/caplmr"
git worktree remove --force research/worktrees/caplmr 2>/dev/null || true
git worktree add research/worktrees/caplmr HEAD >/dev/null 2>&1
"$PY" "$R/newfeat.py" "$WT" caplmr
(cd "$WT" && sh core/build.sh >/dev/null 2>&1)
[ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED"; exit 1; }
echo "eval_check: $(cd "$WT" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"

for ANCHOR in stockfish:2800 stockfish:2900; do
  echo ""
  echo "=== caplmr vs $ANCHOR ==="
  (cd "$WT" && PYTHONPATH=. "$PY" -m research.abgate \
     --games 400 --opponent "$ANCHOR" --baseline-cwd "$CC" \
     --movetime 0.3 --threads 1 --concurrency 6 2>&1 | grep -vE '^game ' | tail -12)
done

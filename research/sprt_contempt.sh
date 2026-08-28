#!/bin/bash
# First use of SPRT: re-test contempt, whose pooled estimate is +8.3 Elo with an
# interval still touching zero after 4800 slots of fixed-block gating.
#
# H0 elo<=0 against H1 elo>=4, alpha=beta=0.05. If contempt is really worth ~8,
# this should accept H1 and give a decision with a stated error rate instead of
# an interval that grazes zero.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
cd "$CC"

WT="$CC/research/worktrees/nocontempt"
git worktree remove --force research/worktrees/nocontempt 2>/dev/null || true
git worktree add research/worktrees/nocontempt HEAD >/dev/null 2>&1
sed -i 's/int drawv = (ply & 1) ? 15 : -15;/int drawv = 0;/' "$WT/core/csearch.c"
grep -q 'int drawv = 0;' "$WT/core/csearch.c" || { echo "revert failed"; exit 1; }
(cd "$WT" && sh core/build.sh >/dev/null 2>&1)
[ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED"; exit 1; }

echo "=== SPRT: contempt15 vs no-contempt, anchor stockfish:2800 ==="
PYTHONPATH=. "$PY" research/sprt.py "$CC" "$WT" stockfish:2800 0 4 6000

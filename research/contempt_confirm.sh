#!/bin/bash
# Confirm contempt 15 at higher power than the run that merged it.
#
# It was merged on +10.5 and +18.3 with BOTH intervals containing zero, on 600
# slots each. Then a later run showed the baseline swinging 6.6 points on the
# same anchor between runs, which is a reminder that absolute scores are noisy
# and that this evidence is thin. It is the only merged Elo of this session, so
# it should be verified before any rating measurement is spent on top of it.
#
# Cleanest possible comparison: current HEAD (contempt 15) against the identical
# tree with the draw score set back to 0. One variable, nothing else differs.
#
# 1200 slots resolves about +/-23 Elo, which cannot certify a +10 effect on its
# own -- stated up front so the result is not over-read. What it CAN do is say
# whether the sign holds at double the games, which is the question that matters
# if +10.5/+18.3 was noise.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
cd "$CC"

WT="$CC/research/worktrees/nocontempt"
git worktree remove --force research/worktrees/nocontempt 2>/dev/null || true
git worktree add research/worktrees/nocontempt HEAD >/dev/null 2>&1
sed -i 's/int drawv = (ply & 1) ? 15 : -15;/int drawv = 0;/' "$WT/core/csearch.c"
grep -q 'int drawv = 0;' "$WT/core/csearch.c" || { echo "revert patch failed"; exit 1; }
(cd "$WT" && sh core/build.sh >/dev/null 2>&1)
[ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED"; exit 1; }
echo "no-contempt baseline eval_check: $(cd "$WT" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"

for ANCHOR in stockfish:2800 stockfish:2900; do
  echo ""
  echo "=== contempt15 (HEAD) vs no-contempt, anchor $ANCHOR ==="
  PYTHONPATH=. "$PY" -m research.abgate \
    --games 600 --opponent "$ANCHOR" --baseline-cwd "$WT" \
    --movetime 0.3 --threads 1 --concurrency 6 2>&1 | grep -vE '^game ' | tail -12
done

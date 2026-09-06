#!/bin/bash
# Capture LMR, re-tested at power. Closing an "unresolvable", not re-litigating.
#
# It was closed at -4.3 and +2.7 over 600 slots per anchor -- an instrument
# resolving about +/-35 Elo, which cannot distinguish 0 from +5. It also screened
# at d_mean -0.998, the best of twenty-three candidates and the only one on the
# good side of baseline that ever reached a game gate. So "closed" was the wrong
# word for it; "unresolvable" was right, and this run fixes that.
#
# 2000 slots per anchor gives se ~7.8, so about +/-15 Elo -- enough to separate a
# genuine +5 from zero, which 600 slots never could. Staged with early
# abandonment so a clear negative costs a fraction of that.
#
# Calibrated expectation, stated first so the result is not over-read: the
# screen's scale is Elo ~ -7.3 * (d_mean + 1.0), and d_mean -0.998 sits at
# break-even, i.e. it predicts ~0. If this lands near zero with a tight interval
# then the screen and the games agree and the candidate is genuinely closed
# rather than merely unmeasured. That is a real outcome, not a null result.
#
# ETA: up to 2000 slots x 2 anchors at 0.3s, concurrency 6 -> ~7 hours worst case,
# much less if abandonment fires.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
cd "$CC"

if [ ! -f research/worktrees/caplmr/core/libcengine.so ]; then
  echo "REFUSING TO GATE: caplmr worktree not built"; exit 1
fi

PYTHONPATH=. "$PY" research/gate.py \
  "$CC/research/worktrees/caplmr" "$CC" \
  --anchors stockfish:2800,stockfish:2900 \
  --slots 2000 --batch 400 --movetime 0.3 --concurrency 6 \
  --abandon -12

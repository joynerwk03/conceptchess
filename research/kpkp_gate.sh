#!/bin/bash
# KPvKP on the ENDGAME BOOK, where pawn endings actually occur.
#
# General openings measured +0.710 on the iso-node screen, which is the probe
# overhead rather than the mechanism -- KPvKP nodes are as rare there as KPvK
# nodes were (0.0000% of opening nodes).
#
# Rule fixed before the run: both anchors positive. Elo on a phase-specific book
# is inflated by ~1/f, so read DIRECTION only; a positive earns an ordinary
# two-anchor gate, not a merge.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"

if [ ! -f "$CC/research/worktrees/kpkp/core/libcengine.so" ]; then
  echo "REFUSING TO GATE: kpkp worktree not built"
  exit 1
fi

cd "$CC"
PYTHONPATH=. "$PY" research/gate.py \
  "$CC/research/worktrees/kpkp" "$CC" \
  --book research/books/endgame_uho.epd \
  --anchors stockfish:2800,stockfish:2900 \
  --slots 400 --batch 200 --movetime 0.3 --concurrency 6

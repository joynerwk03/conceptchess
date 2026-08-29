#!/bin/bash
# Build both 50-move variants, sanity-check them, then gate the SF-style one.
#
# Straight to games: 87.8% of referee positions have a halfmove clock under 10,
# so the iso-node screen is effectively blind to this. That is the same
# can-the-rule-fire-here check that invalidated the lmrdeep and cap6 screens,
# applied before wasting a screen rather than after.
#
# Rule fixed BEFORE the run: merge only if BOTH anchors are positive.
# ETA: 2 anchors x 600 slots at 0.3s, concurrency 6 -> ~2 hours.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
cd "$CC"

for M in sf soft; do
  WT="$CC/research/worktrees/f50_$M"
  git worktree remove --force "research/worktrees/f50_$M" 2>/dev/null || true
  git worktree add "research/worktrees/f50_$M" HEAD >/dev/null 2>&1
  "$PY" "$R/fifty.py" "$WT" "$M"
  (cd "$WT" && sh core/build.sh >/dev/null 2>&1)
  if [ ! -f "$WT/core/libcengine.so" ]; then echo "BUILD FAILED $M"; exit 1; fi
  echo "  f50_$M eval_check: $(cd "$WT" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
done

# the discount must actually bite: same position, different halfmove clock
echo ""
echo "sanity: score of one position at hm=0 vs hm=80 (sf variant)"
cd "$CC/research/worktrees/f50_sf"
PYTHONPATH=. "$PY" - <<'PY'
import chess
from engine.engine import Engine
from engine import core
core.set_threads(1)
for hm in (0, 80):
    b = chess.Board("8/8/4k3/8/8/4K3/4P3/8 w - - 0 1")
    b.halfmove_clock = hm
    r = Engine(use_book=False, use_tablebase=False).best_move(
        b, movetime=999.0, max_depth=6)
    print(f"  hm={hm:3d}  score {r.score:+.0f}")
PY

cd "$CC"
for ANCHOR in stockfish:2800 stockfish:2900; do
  echo ""
  echo "=== 50-move discount (sf) vs baseline, anchor ${ANCHOR} ==="
  cd "$CC/research/worktrees/f50_sf"
  PYTHONPATH=. "$PY" -u -m research.abgate \
    --games 300 --opponent "${ANCHOR}" --baseline-cwd "$CC" \
    --movetime 0.3 --threads 1 --concurrency 6 2>&1 | grep -vE '^game ' | tail -10
  cd "$CC"
done

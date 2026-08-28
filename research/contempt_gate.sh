#!/bin/bash
# Gate contempt on GAMES. The referee screen cannot price this -- it compares
# against SF11, which has its own draw preferences, so a difference there would
# measure disagreement rather than strength.
#
# Two values, because contempt has an interior optimum: too little does nothing,
# too much loses Elo by declining draws in positions we cannot win. Against an
# anchor at our own strength the bet is roughly even, so 15 is the conservative
# guess and 30 the aggressive one.
#
# Two anchors, decision rule fixed before the run: merge only if BOTH are
# positive for the same value. Same rule that rejected the LMR change.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
cd "$CC"

for C in 15 30; do
  WT="$CC/research/worktrees/cont$C"
  git worktree remove --force "research/worktrees/cont$C" 2>/dev/null || true
  git worktree add "research/worktrees/cont$C" HEAD >/dev/null 2>&1
  "$PY" "$R/contempt.py" "$WT" "$C"
  (cd "$WT" && sh core/build.sh >/dev/null 2>&1)
  if [ ! -f "$WT/core/libcengine.so" ]; then echo "BUILD FAILED $C"; exit 1; fi
  # interpretability guard: contempt must not have moved the evaluation
  echo "  contempt $C eval_check: $(cd "$WT" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
done

for C in 15 30; do
  WT="$CC/research/worktrees/cont$C"
  for ANCHOR in stockfish:3000 stockfish:2700; do
    echo ""
    echo "=== contempt $C vs $ANCHOR ==="
    (cd "$WT" && PYTHONPATH=. "$PY" -m research.abgate \
      --games 300 --opponent "$ANCHOR" --baseline-cwd "$CC" \
      --movetime 0.3 --threads 1 --concurrency 6 2>&1 | grep -vE '^game ' | tail -12)
  done
done

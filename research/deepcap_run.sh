#!/bin/bash
# EBF curve for the deep-cap variants. Games-free instrument for tree SHAPE.
#
# Cold node counts at fixed depth: fresh process per engine per depth, so no
# state carries between measurements. The question is not "fewer nodes" -- any
# reduction gives that -- but whether the EBF stops RISING, since that is the
# specific way this tree differs from SF11's.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
cd "$CC"

for V in lmr lmp both; do
  WT="$CC/research/worktrees/dc_$V"
  git worktree remove --force "research/worktrees/dc_$V" 2>/dev/null || true
  git worktree add "research/worktrees/dc_$V" HEAD >/dev/null 2>&1
  "$PY" "$R/deepcap.py" "$WT" "$V" >/dev/null
  (cd "$WT" && sh core/build.sh >/dev/null 2>&1)
  if [ ! -f "$WT/core/libcengine.so" ]; then echo "BUILD FAILED $V"; exit 1; fi
  echo "  dc_$V eval_check: $(cd "$WT" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
done

for V in base lmr lmp both; do
  if [ "$V" = base ]; then D="$CC"; else D="$CC/research/worktrees/dc_$V"; fi
  for DEPTH in 10 12 14; do
    (cd "$D" && DEPTH=$DEPTH VAR=$V PYTHONPATH=. "$PY" - <<'PY'
import os, chess
from engine.engine import Engine
from engine import core
assert core.HAS_CORE, "REFUSING TO PROBE: no compiled core"
core.set_threads(1)
BOOK = "/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
fens = [" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::50][:20]
d = int(os.environ["DEPTH"]); tot = 0
for f in fens:
    r = Engine(use_book=False, use_tablebase=False).best_move(
        chess.Board(f), movetime=999.0, max_depth=d)
    tot += getattr(r, "nodes", 0) or 0
print(f"{os.environ['VAR']} {d} {tot}")
PY
    )
  done
done

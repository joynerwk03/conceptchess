#!/bin/bash
# Re-test the two merged endgame changes on the endgame book.
#
# Contempt (~+8 pooled, interval touching zero) and the KPvK bitbase
# (+7.0/+13.1, both intervals containing zero) are the ENTIRE basis for the
# claim that the engine now sits near 3015 rather than 2999. Both were gated on
# general openings where an endgame mechanism is diluted by the ~80% of games it
# never touches, which is why both readings were ambiguous.
#
# The endgame book was just measured to give equivalent precision in 10.5x fewer
# slots. So an hour of games here decides whether a 37-hour rating run is worth
# starting -- by far the best trade available.
#
# Direction: gate.py reports CANDIDATE minus BASELINE. HEAD (which HAS the
# feature) is passed as the candidate, and the worktree with the feature REMOVED
# is the baseline. So a POSITIVE delta means the feature is real. Stated
# explicitly because I had this backwards in the first draft of this script.
#
# Elo here is inflated by ~1/f against real games. Read DIRECTION and rough
# magnitude, not a portable rating.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
cd "$CC"

mk() {
  local name="$1" sedexpr="$2"
  local wt="$CC/research/worktrees/$name"
  git worktree remove --force "research/worktrees/$name" 2>/dev/null || true
  git worktree add "research/worktrees/$name" HEAD >/dev/null 2>&1
  sed -i "$sedexpr" "$wt/core/csearch.c"
  (cd "$wt" && sh core/build.sh >/dev/null 2>&1)
  [ -f "$wt/core/libcengine.so" ] || { echo "BUILD FAILED $name"; exit 1; }
  echo "  $name eval_check: $(cd "$wt" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
}

# contempt off: draw score back to 0
mk no_contempt 's/int drawv = (ply & 1) ? 15 : -15;/int drawv = 0;/'
grep -q 'int drawv = 0;' "$CC/research/worktrees/no_contempt/core/csearch.c" \
  || { echo "contempt revert failed"; exit 1; }

# KPvK off: make the probe decline everywhere
mk no_kpk 's/if(b->hm > 40) return 0;/if(1) return 0;/'
grep -q 'if(1) return 0;' "$CC/research/worktrees/no_kpk/core/csearch.c" \
  || { echo "kpk revert failed"; exit 1; }

for V in no_contempt no_kpk; do
  echo ""
  echo "########## HEAD vs $V  (positive delta = the feature is REAL) ##########"
  PYTHONPATH=. "$PY" research/gate.py "$CC" "$CC/research/worktrees/$V" \
    --book research/books/endgame_uho.epd \
    --anchors stockfish:2800,stockfish:2900 \
    --slots 400 --batch 200 --movetime 0.3 --concurrency 6 || true
done

#!/bin/bash
# The softer 50-move variant, on the ENDGAME BOOK, via the staged gate.
#
# First use of both new tools, and the right test for this mechanism. The SF-style
# rule lost 19.8 and 11.8 Elo on general openings, most likely because it cuts
# the eval 30% at a halfmove clock of 30, which is ordinary middlegame territory.
# The soft variant discounts only past clock 40, so it should not touch normal
# play at all -- which means general openings are exactly where it is INVISIBLE,
# and the earlier gate design would have measured mostly noise.
#
# On the endgame book (6-12 pieces, |SF11| 50-300cp) the clock actually climbs,
# so the rule fires. Per the phase-specific arithmetic this is worth up to ~25x
# the games for a localised change.
#
# READ THE RESULT AS DIRECTION ONLY. Elo from a phase-specific book is inflated
# by roughly 1/f against real games. A positive here earns an ordinary two-anchor
# gate; it does not earn a merge.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
cd "$CC"

WT="$CC/research/worktrees/f50_soft"
git worktree remove --force research/worktrees/f50_soft 2>/dev/null || true
git worktree add research/worktrees/f50_soft HEAD >/dev/null 2>&1
"$PY" "$R/fifty.py" "$WT" soft
(cd "$WT" && sh core/build.sh >/dev/null 2>&1)
[ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED"; exit 1; }
echo "eval_check: $(cd "$WT" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
echo ""

PYTHONPATH=. "$PY" research/gate.py "$WT" "$CC" \
  --book research/books/endgame_uho.epd \
  --anchors stockfish:2800,stockfish:2900 \
  --slots 400 --batch 200 --movetime 0.3 --concurrency 6

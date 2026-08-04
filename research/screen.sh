#!/bin/bash
# Fast SPRT screen of a search variant. The research loop's throughput problem.
#
# The old workflow was: patch main, build, run 800 games (~50 min), revert. That
# is wrong twice over. It plays every game even when the verdict is obvious by
# game 200, and it leaves main dirty for the duration so a mistake gates the
# wrong tree. This does neither: the variant lives in its own worktree, main
# stays at the baseline, and SPRT stops as soon as the result is decisive.
#
# H0 = "no better than baseline", H1 = "+25 Elo". A true zero is usually rejected
# in 200-400 games (~15-25 min) instead of 800. Anything that survives the screen
# earns a full two-batch confirmation gate -- the screen ACCEPTS nothing on its
# own, it only kills.
#
# Usage:
#   research/screen.sh <name> '<sed-expression on core/csearch.c>' [movetime] [maxgames]
#
# Example:
#   research/screen.sh mdp 's/#define MAXPLY 128/#define MAXPLY 128\nMATE_DIST/' 0.3
set -eu

NAME="$1"
PATCH="$2"
MT="${3:-0.3}"
MAXG="${4:-800}"

CC="$(cd "$(dirname "$0")/.." && pwd)"
WT="$CC/research/worktrees/v_$NAME"

cd "$CC"
if [ -d "$WT" ]; then
  git worktree remove --force "$WT" 2>/dev/null || rm -rf "$WT"
fi
git worktree add --detach "$WT" HEAD >/dev/null 2>&1

cd "$WT"
eval "$PATCH"
if git diff --quiet; then
  echo "!! $NAME: patch changed nothing -- check the sed expression" >&2
  exit 1
fi
echo "--- $NAME: patch applied ---"
git diff --stat
sh core/build.sh >/dev/null

# Faithfulness first: a search-only change must leave the eval identical, and a
# broken variant must never reach a gate.
cd "$CC"
EV=$(cd "$WT" && PYTHONPATH=. "$CC/.venv/bin/python" core/eval_check.py 2>&1 | grep "max |C" || true)
echo "  $EV"
case "$EV" in
  *"0.000000"*) : ;;
  *) echo "!! $NAME: C eval no longer mirrors Python -- ABORTING before any game" >&2
     echo "!! The screen measures a variant whose explanation is a lie. Fix first." >&2
     exit 1 ;;
esac

echo "--- $NAME: SPRT screen vs baseline (H1=+25 Elo), $MT s, max $MAXG games ---"
date
"$CC/.venv/bin/python" -m research.match \
  --games "$MAXG" --movetime "$MT" --concurrency 8 --sprt --sprt-elo1 25 \
  --book research/books/uho_1000.epd \
  --ours-cwd "$WT" \
  --opponent "cmd:$CC/.venv/bin/python -m engine.uci" 2>&1 | tail -6
date

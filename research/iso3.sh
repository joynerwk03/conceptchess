#!/bin/bash
# Screen lmrdeep at a depth where its rule can actually fire.
#
# At base depth 9 the rule (remaining depth >= 7) covers only the top two plies,
# so the depth-9 reading tested overhead, not mechanism -- the cap6 trap again.
# At base depth 12 it covers the top five, which is where the 30.6% node
# reduction at depth 14 came from.
#
# rfp25 rides along as the calibration anchor: it is known -33 Elo and fires at
# every depth, so if the screen still orders it clearly worse at depth 12, the
# instrument is behaving at this depth too.
#
# Fewer positions because a depth-12 baseline costs roughly 4x a depth-9 one.
# STRIDE, never a block.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
cd "$CC"

awk 'NR%26==1' "$R/ref_partial.jsonl" > "$R/ref_d12.jsonl"
echo "positions: $(wc -l < "$R/ref_d12.jsonl")"

mk() {
  local name="$1"; shift
  local wt="$CC/research/worktrees/$name"
  git worktree remove --force "research/worktrees/$name" 2>/dev/null || true
  git worktree add "research/worktrees/$name" HEAD >/dev/null 2>&1
  "$@" "$wt"
  (cd "$wt" && sh core/build.sh >/dev/null 2>&1)
  [ -f "$wt/core/libcengine.so" ] || { echo "BUILD FAILED $name"; exit 1; }
  echo "  $name eval_check: $(cd "$wt" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
}
patch_rfp() { sed -i 's/^#define RFP_MARGIN 90/#define RFP_MARGIN 25/' "$1/core/csearch.c"; }
patch_lmr() { "$PY" "$R/deepcap.py" "$1" lmr >/dev/null; }

mk rfp25 patch_rfp
mk lmrdeep patch_lmr

echo ""
echo "=== base depth 12 (lmrdeep's rule covers the top 5 plies here) ==="
"$PY" research/screen_isonode.py "$R/ref_d12.jsonl" 12 \
  rfp25="$CC/research/worktrees/rfp25" \
  lmrdeep="$CC/research/worktrees/lmrdeep"

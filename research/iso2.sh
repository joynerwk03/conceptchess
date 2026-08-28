#!/bin/bash
# Re-calibrate the sharpened screen, then ask the question the old instrument
# could never answer about the thinners this project rejected.
#
#   rfp25   known -33 Elo, halves the tree   -> the calibration anchor
#   lmrdeep the deep-region LMR variant: cut the depth-14 tree 30.6%, bent the
#           EBF down, then gated -16.9 and -31.8. Did it lose because the games
#           disagreed with the screen, or because it is genuinely worse even
#           with its depth paid in full? rfp25 answers "genuinely worse"; this
#           is the one candidate where that was never established.
#
# Worktrees are rebuilt from HEAD so they carry the node limit.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
cd "$CC"

mk() {  # mk <name> <patch-command...>
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
"$PY" research/screen_isonode.py "$R/ref_calib.jsonl" 9 \
  rfp25="$CC/research/worktrees/rfp25" \
  lmrdeep="$CC/research/worktrees/lmrdeep"

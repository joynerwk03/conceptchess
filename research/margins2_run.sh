#!/bin/bash
# Batch-triage three missing search mechanisms on the calibrated iso-node screen.
# rfp25 rides along in every run as the calibration anchor: it is known -33 Elo,
# so if it does not read clearly worse, the run is underpowered and every other
# number in it is discarded. That check just caught a false positive at depth 12.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
cd "$CC"

ARGS=""
mk() {
  local name="$1"; shift
  local wt="$CC/research/worktrees/$name"
  git worktree remove --force "research/worktrees/$name" 2>/dev/null || true
  git worktree add "research/worktrees/$name" HEAD >/dev/null 2>&1
  if ! "$@" "$wt" >/dev/null 2>&1; then echo "  $name PATCH FAILED (skipped)"; return 0; fi
  (cd "$wt" && sh core/build.sh >/dev/null 2>&1)
  if [ ! -f "$wt/core/libcengine.so" ]; then echo "  $name BUILD FAILED (skipped)"; return 0; fi
  echo "  $name eval_check: $(cd "$wt" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
  ARGS="$ARGS $name=$wt"
}
patch_rfp()  { sed -i 's/^#define RFP_MARGIN 90/#define RFP_MARGIN 25/' "$1/core/csearch.c"; }
patch_feat() { "$PY" "$R/margins2.py" "$2" "$1"; }

mk rfp25 patch_rfp
for F in pcm150 pcm220 pcd4; do
  mk "$F" patch_feat "$F"
done

echo ""
"$PY" research/screen_isonode.py "$R/ref_calib.jsonl" 9 $ARGS

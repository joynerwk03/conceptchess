#!/bin/bash
# Screen a batch of pruning-policy variants on the search screen.
#
# Each is a one-line change to core/csearch.c, built in a throwaway worktree and
# scored in ~3 minutes against the 1800-position reference. This is the workflow
# the screen exists for: an hour of games per variant made it impossible to try
# six of anything, so the reduction schedule has been essentially untouched since
# it was first tuned.
#
# The screen KILLS; anything that clears it still earns a real gate.
exec > /home/joynerwk03/ccruns/screen_batch.log 2>&1
set -u
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
cd "$CC"

echo "=== baseline ==="
PYTHONPATH=. "$PY" research/search_screen.py score . --fast 0.1 \
  --save /tmp/sb_base.json | grep agreement

run () {   # $1 = name, $2 = sed program on core/csearch.c
  local WT="$CC/research/worktrees/sb_$1"
  git worktree remove --force "$WT" >/dev/null 2>&1 || rm -rf "$WT"
  git worktree add --detach "$WT" main >/dev/null 2>&1
  sed -i "$2" "$WT/core/csearch.c"
  if ! git -C "$WT" diff --quiet; then
    if (cd "$WT" && sh core/build.sh >/dev/null 2>&1); then
      echo
      echo "########## $1 ##########"
      PYTHONPATH=. "$PY" research/search_screen.py score "$WT" --fast 0.1 \
        --save "/tmp/sb_$1.json" | grep agreement
      PYTHONPATH=. "$PY" research/search_screen.py compare \
        /tmp/sb_base.json "/tmp/sb_$1.json" | tail -4
    else
      echo "$1: BUILD FAILED"
    fi
  else
    echo "$1: patch changed nothing"
  fi
  git worktree remove --force "$WT" >/dev/null 2>&1
}

date
# Reverse-futility margin: how much headroom we demand before assuming a fail-high.
run rfp70   's/#define RFP_MARGIN 90/#define RFP_MARGIN 70/'
run rfp120  's/#define RFP_MARGIN 90/#define RFP_MARGIN 120/'
# Reverse-futility depth: how deep the shortcut is allowed to apply.
run rfpd8   's/#define RFP_DEPTH 6/#define RFP_DEPTH 8/'
# Late-move pruning: how many quiets we look at before skipping the rest.
run lmp4    's/i >= ((3 + depth\*depth)/i >= ((4 + depth*depth)/'
run lmp2    's/i >= ((3 + depth\*depth)/i >= ((2 + depth*depth)/'
# Late-move REDUCTION onset: reduce from the 4th quiet instead of the 3rd.
run lmr4    's/if(i>=12)red=3; else if(i>=3)red=2;/if(i>=12)red=3; else if(i>=4)red=2;/'
# Null-move reduction, one ply deeper at every tier.
run nmp1    's/int r = depth>=12?5:(depth>=6?4:3);/int r = depth>=12?6:(depth>=6?5:4);/'
date
echo "###### done ######"

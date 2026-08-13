#!/bin/bash
# Structural pruning the search does not have, screened on the search screen.
#
# The eight variants tested on 2026-08-05 were all single-PARAMETER moves, and
# they showed the current knobs are locally tuned. That is a different claim
# from "the search is structurally complete". Effective branching factor is
# 1.852 where strong engines run 1.60-1.75, and closing that gap is worth
# +61 to +187 Elo at no NPS cost -- far more than any speed work available.
#
#   razor      at very shallow depth, a position far below alpha is unlikely to
#              be rescued by a quiet move; drop straight to qsearch. Absent.
#   seeprune   losing captures are currently searched at FULL WIDTH in the main
#              search. Skip them at shallow depth in non-PV nodes. (Captures
#              only: see() computes the first gain from the captured piece, so
#              it is not meaningful for quiets.)
#   histprune  skip quiets whose history is deeply negative at shallow depth --
#              moves that have been refuted repeatedly in this search.
exec > /home/joynerwk03/ccruns/ebf_variants.log 2>&1
set -u
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
cd "$CC"

echo "=== baseline ==="
PYTHONPATH=. "$PY" research/search_screen.py score . --fast 0.1 \
  --save /tmp/ebf_base.json | grep -E "agreement|mean depth"

run () {
  local name="$1"; shift
  local WT="$CC/research/worktrees/ebf_$name"
  git worktree remove --force "$WT" >/dev/null 2>&1 || rm -rf "$WT"
  git worktree add --detach "$WT" main >/dev/null 2>&1
  python3 "$1" "$WT" || { echo "$name: patch failed"; return; }
  if (cd "$WT" && sh core/build.sh >/dev/null 2>&1); then
    echo
    echo "########## $name ##########"
    PYTHONPATH=. "$PY" research/search_screen.py score "$WT" --fast 0.1 \
      --save "/tmp/ebf_$name.json" | grep -E "agreement|mean depth"
    PYTHONPATH=. "$PY" research/search_screen.py compare \
      /tmp/ebf_base.json "/tmp/ebf_$name.json" | tail -4
  else
    echo "$name: BUILD FAILED"
    (cd "$WT" && sh core/build.sh 2>&1 | head -5)
  fi
}

date
run razor     /home/joynerwk03/ccruns/patch_razor.py
run seeprune  /home/joynerwk03/ccruns/patch_seeprune.py
run histprune /home/joynerwk03/ccruns/patch_histprune.py
date
echo "###### done ######"

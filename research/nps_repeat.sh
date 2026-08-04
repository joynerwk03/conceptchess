#!/bin/bash
# Three benchmark runs a side. A single run has ~1-2% noise, and the effect
# being measured is about that size -- reporting one run would be reporting
# noise, which is the mistake this whole session has been about.
set -u
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
WT="$CC/research/worktrees/dev_pawnhash"

runs () {
  local dir="$1" label="$2" tot=0 n=0
  for i in 1 2 3; do
    local v
    v=$(cd "$dir" && PYTHONPATH=. "$PY" -m research.benchmark 2>&1 \
        | grep "avg nps" | sed 's/.*avg nps *//; s/ .*//' | tr -d ',')
    echo "    run $i: $v"
    tot=$((tot+v)); n=$((n+1))
  done
  echo "  $label mean: $((tot/n))"
  echo $((tot/n)) > "/tmp/nps_$3"
}

echo "main:"
runs "$CC" "main" a
echo "pawn hash + hoisted king lookup:"
runs "$WT" "pawnhash" b
A=$(cat /tmp/nps_a); B=$(cat /tmp/nps_b)
awk -v a="$A" -v b="$B" 'BEGIN{printf "\nDELTA: %+.2f%%\n", 100*(b-a)/a}'

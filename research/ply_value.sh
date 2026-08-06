#!/bin/bash
# What is a ply worth to THIS engine, and how much time buys one?
#
# Every diagnostic now points at search depth rather than evaluation: the blame
# analysis says no concept is biased at the decision margin, and the residual
# move-choice errors are horizon effects. So depth is the bottleneck -- and
# before anyone spends weeks chasing it, it is worth knowing the exchange rate.
#
# Two numbers, from the search screen's own time controls, which were measured
# against known-stronger and known-weaker controls:
#   agreement with the 3s reference at each time limit
#   the depth actually reached
exec > /home/joynerwk03/ccruns/ply_value.log 2>&1
set -u
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
cd "$CC"
for T in 0.05 0.1 0.2 0.4 0.8; do
  echo "### $T s"
  PYTHONPATH=. "$PY" research/search_screen.py score . --fast "$T" \
    --save "/tmp/ply_$T.json" | grep -E "agreement|mean depth"
done
echo
echo "=== paired against the 0.1s point ==="
for T in 0.05 0.2 0.4 0.8; do
  echo -n "$T s vs 0.1s: "
  PYTHONPATH=. "$PY" research/search_screen.py compare /tmp/ply_0.1.json "/tmp/ply_$T.json" \
    | grep "paired difference"
done

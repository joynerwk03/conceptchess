#!/bin/bash
# Depth-preferred TT replacement is a MULTI-THREAD hypothesis: ten helpers share
# one table and always-replace lets a shallow write clobber a deep one. The
# single-threaded screen said -2.72, but it cannot test that claim at all.
#
# So: measure the noise floor at 10 threads first (SMP makes the search
# nondeterministic, and a reading below the floor is nothing), then the variant.
exec > /home/joynerwk03/ccruns/tt_smp.log 2>&1
set -u
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
cd "$CC"

echo "=== noise floor at 10 threads: identical code, three runs ==="
for i in 1 2 3; do
  PYTHONPATH=. "$PY" research/search_screen.py score . --fast 0.1 --threads 10 \
    --save "/tmp/tt10_base$i.json" | grep agreement
done
echo "--- run1 vs run2 ---"
PYTHONPATH=. "$PY" research/search_screen.py compare /tmp/tt10_base1.json /tmp/tt10_base2.json | tail -3
echo "--- run1 vs run3 ---"
PYTHONPATH=. "$PY" research/search_screen.py compare /tmp/tt10_base1.json /tmp/tt10_base3.json | tail -3

echo
echo "=== depth-preferred TT at 10 threads ==="
PYTHONPATH=. "$PY" research/search_screen.py score research/worktrees/dev_ttdepth \
  --fast 0.1 --threads 10 --save /tmp/tt10_depth.json | grep agreement
PYTHONPATH=. "$PY" research/search_screen.py compare /tmp/tt10_base1.json /tmp/tt10_depth.json

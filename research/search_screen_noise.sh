#!/bin/bash
# The screen's own noise floor: the same build against itself.
#
# At a fixed TIME the search is not deterministic even single-threaded, so two
# runs of identical code disagree on some positions. Any reading smaller than
# that disagreement is nothing. Measuring it is the difference between an
# instrument and a random number generator.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
cd "$CC"
for i in 1 2 3; do
  PYTHONPATH=. ./.venv/bin/python research/search_screen.py score . \
    --fast 0.1 --save "/tmp/hits_noise$i.json" | grep "agreement"
done
echo
echo "=== run 1 vs run 2 (identical code) ==="
PYTHONPATH=. ./.venv/bin/python research/search_screen.py compare \
  /tmp/hits_noise1.json /tmp/hits_noise2.json
echo
echo "=== run 1 vs run 3 (identical code) ==="
PYTHONPATH=. ./.venv/bin/python research/search_screen.py compare \
  /tmp/hits_noise1.json /tmp/hits_noise3.json

#!/bin/bash
exec > /home/joynerwk03/ccruns/tc_scaling.log 2>&1
set -u
export PATH="$HOME/bin:$HOME/.local/bin:$PATH"
CC=/home/joynerwk03/mission-control/projects/conceptchess
cd "$CC"
echo "###### Does the anchored rating depend on the time control? ######"
echo "The 2839 figure is from 10s+0.1. Stockfish at UCI_Elo 2700 is STRENGTH-"
echo "LIMITED -- it plays to a target rating rather than playing its best -- so"
echo "it may not gain from extra time the way a full-strength engine does. If"
echo "our engine scales with time and the anchor does not, the anchored rating"
echo "is genuinely higher at longer controls, and 'improve until 3000 anchored"
echo "against Stockfish' has a term nobody here has measured."
echo
echo "60 games at 30s+0.3, concurrency 1, full thread width. Compare against the"
echo "150-game 10s+0.1 result: +80 =47 -23 (69.0%), +139 over the anchor."
date
"$CC/.venv/bin/python" -m research.match \
  --games 60 --clock 30 --inc 0.3 --concurrency 1 \
  --book research/books/uho_1000.epd \
  --opponent stockfish:2700 2>&1 | grep -vE "^game +[0-9]+:" | tail -8
date
echo "###### done ######"

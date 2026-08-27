#!/bin/bash
# Where does thread scaling actually stop? Measured, not inferred.
#
# The claim "8->16 threads is worth +22 Elo" and the probe reading T=10 and T=16
# at an identical 15.46 both come from an instrument that swings ~0.35 plies. If
# depth really is flat from 8 to 16, that is a broken Lazy SMP and the goal
# configuration is leaving Elo on the floor; if it scales normally, the +22 is
# just what sub-linear SMP looks like and this is closed for good.
#
# One binary, only CC_THREADS changes, so any difference is SMP and nothing
# else. Passes are INTERLEAVED and reversed so drift cannot land on one arm, and
# more positions than the usual probe to tighten the mean.
#
# A doubling of threads that buys a full ply is worth ~+40 Elo by the speed
# curve; one that buys 0.1 ply is worth nothing. That is the number to read.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
cd "$CC"

for PASS in 1 2 3 4; do
  case $PASS in 1|3) ORDER="1 4 8 16";; *) ORDER="16 8 4 1";; esac
  for T in $ORDER; do
    THR=$T PYTHONPATH=. "$PY" - <<'PY'
import os, chess
from engine.engine import Engine
from engine import core
assert core.HAS_CORE, "REFUSING TO PROBE: no compiled core"
t = int(os.environ["THR"])
core.set_threads(t)
BOOK = "/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
fens = [" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::31][:24]
d = 0.0
for f in fens:
    r = Engine(use_book=False, use_tablebase=False).best_move(
        chess.Board(f), movetime=1.0)
    d += getattr(r, "depth", 0) or 0
print(f"threads {t:>3}  mean depth {d/len(fens):.3f}", flush=True)
PY
  done
done

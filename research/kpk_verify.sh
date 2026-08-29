#!/bin/bash
# Does the probe actually FIRE, and does it agree with syzygy?
#
# Both smoke positions returned 0, which is consistent with the probe working
# (both may genuinely be draws) AND with the probe never firing. That ambiguity
# is exactly the "confidently wrong" failure mode, so it has to be resolved
# against ground truth on positions whose verdicts differ.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
cd "$CC/research/worktrees/kpk"

PYTHONPATH=. "$PY" - <<'PY'
import pathlib, chess, chess.syzygy
from engine.engine import Engine
from engine import core
assert core.HAS_CORE
core.set_threads(1)

FENS = [
    "4k3/8/4K3/4P3/8/8/8/8 w - - 0 1",     # white king in front of pawn: won
    "8/8/8/4k3/8/4K3/4P3/8 w - - 0 1",     # black has the opposition: draw
    "8/8/8/8/k7/8/P7/K7 w - - 0 1",        # rook pawn, king boxed in: draw
    "8/8/8/3k4/8/8/P7/K7 w - - 0 1",       # rook pawn, black king far: won
    "8/8/1P6/8/8/8/8/K5k1 w - - 0 1",      # far advanced pawn: won
]
tb = chess.syzygy.open_tablebase(str(pathlib.Path.home()/"syzygy345"))
print(f"{'fen':38s}{'syzygy':>9}{'engine':>9}")
bad = 0
for f in FENS:
    b = chess.Board(f)
    wdl = tb.probe_wdl(b)
    truth = "win" if wdl > 0 else ("draw" if wdl == 0 else "loss")
    r = Engine(use_book=False, use_tablebase=False).best_move(
        b, movetime=999.0, max_depth=8)
    got = "win" if r.score > 1000 else ("draw" if abs(r.score) < 50 else f"{r.score:+.0f}")
    flag = "" if got == truth else "   <-- MISMATCH"
    bad += got != truth
    print(f"{f:38s}{truth:>9}{got:>9}{flag}")
tb.close()
print(f"\n{'PROBE VERIFIED' if bad == 0 else f'{bad} MISMATCHES - DO NOT MERGE'}")
PY

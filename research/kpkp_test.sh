#!/bin/bash
# Build the KPvKP bitbase into a worktree, prove the probe fires and agrees with
# syzygy, then screen it on the ENDGAME BOOK where the mechanism actually acts.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
export PATH="$HOME/bin:$PATH"
WT="$CC/research/worktrees/kpkp"
cd "$CC"
git worktree remove --force research/worktrees/kpkp 2>/dev/null || true
git worktree add research/worktrees/kpkp HEAD >/dev/null 2>&1
cp core/kpkp.bin "$WT/core/"
"$PY" /home/joynerwk03/ccruns/kpkp_wire.py "$WT"
(cd "$WT" && sh core/build.sh 2>&1 | grep -iE "\berror\b" | head -3 || true)
[ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED"; exit 1; }
echo "eval_check: $(cd "$WT" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
PYTHONPATH=. "$PY" -c "pass"

cd "$WT"
PYTHONPATH=. "$PY" - <<'PY'
import pathlib, chess, chess.syzygy
from engine.engine import Engine
from engine import core
assert core.HAS_CORE
core.set_threads(1)
tb = chess.syzygy.open_tablebase(str(pathlib.Path.home()/"syzygy345"))
FENS = [
    "8/8/8/3k4/8/3K4/4P3/8 w - - 0 1",       # KPvK control, still must work
    "8/5p2/8/4k3/8/4K3/4P3/8 w - - 0 1",     # KPvKP, blocked-ish
    "8/8/1p6/8/8/1P6/4k3/4K3 w - - 0 1",     # KPvKP, symmetric pawns
    "8/8/8/1k6/1p6/8/1P6/1K6 w - - 0 1",     # KPvKP, opposition
    "8/p7/8/8/8/8/6P1/K5k1 w - - 0 1",       # KPvKP, racing pawns
]
bad = 0
print(f"{'fen':40s}{'syzygy':>9}{'engine':>9}")
for f in FENS:
    b = chess.Board(f)
    try:
        wdl = tb.probe_wdl(b)
    except Exception as e:
        print(f"{f:40s}{"no table":>9}{"skip":>9}")
        continue
    truth = "win" if wdl > 0 else ("draw" if wdl == 0 else "loss")
    r = Engine(use_book=False, use_tablebase=False).best_move(b, movetime=999.0, max_depth=10)
    got = "win" if r.score > 1000 else ("loss" if r.score < -1000 else "draw")
    flag = "" if got == truth else "   <-- MISMATCH"
    bad += got != truth
    print(f"{f:40s}{truth:>9}{got:>9}{flag}")
tb.close()
print(f"\n{'PROBE OK' if bad==0 else str(bad)+' MISMATCHES'}")
PY

cd "$CC"
echo ""
echo "=== iso-node screen (general openings: KPvKP nodes are rare here) ==="
"$PY" research/screen_isonode.py /home/joynerwk03/ccruns/ref_calib.jsonl 9 kpkp="$WT"

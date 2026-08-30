#!/bin/bash
# Gate the KPvK probe on a single cheap popcount, in place on main.
#
# The KPvKP experiment lost 16 Elo and the diagnosis was overhead rather than
# wrong knowledge: the probe ORs eight bitboards and runs two popcounts at EVERY
# node to find a position type that occurs in a vanishing fraction of them. The
# merged kpk_probe does exactly the same thing.
#
# KPvK is three pieces. A single popcount of the occupancy, rejecting anything
# above four, subsumes every one of those tests and costs one instruction.
#
# Tree-identical by construction: the same positions are detected, only the
# rejection path is cheaper. So node counts must match TO THE NODE, and by this
# project's rule that makes it self-validating -- NPS is sufficient evidence and
# no game gate is needed, nor could one resolve an effect this small.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
cd "$CC"

PYTHONPATH=. "$PY" - <<'PY'
import chess
from engine.engine import Engine
from engine import core
core.set_threads(1)
BOOK = "/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
fens = [" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::80][:12]
tot = 0
for f in fens:
    r = Engine(use_book=False, use_tablebase=False).best_move(
        chess.Board(f), movetime=999.0, max_depth=11)
    tot += r.nodes
open("/tmp/pc_before.txt", "w").write(str(tot))
print(f"before: {tot:,} nodes")
PY

python3 - "$CC/core/csearch.c" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text()
old = """    if(b->hm > 40) return 0;
    U64 wp=b->bb[WHITE][PAWN], bp=b->bb[BLACK][PAWN];"""
new = """    if(b->hm > 40) return 0;
    /* One popcount rejects ~every node. KPvK is three pieces, so anything above
     * four cannot match, and this subsumes the eight bitboard tests below --
     * which were being paid at every node in the search to find a position type
     * that is a vanishing fraction of them. Tree-identical: same positions
     * detected, cheaper rejection. */
    if(__builtin_popcountll(b->all) > 4) return 0;
    U64 wp=b->bb[WHITE][PAWN], bp=b->bb[BLACK][PAWN];"""
assert s.count(old) == 1, f"kpk_probe anchor not unique ({s.count(old)})"
p.write_text(s.replace(old, new, 1))
print("cheap guard applied")
PY

sh core/build.sh 2>&1 | grep -iE "\berror\b" | head -3 || true
[ -f core/libcengine.so ] || { echo "BUILD FAILED"; exit 1; }
echo "eval_check: $(PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"

PYTHONPATH=. "$PY" - <<'PY'
import chess
from engine.engine import Engine
from engine import core
core.set_threads(1)
BOOK = "/home/joynerwk03/mission-control/projects/conceptchess/research/books/uho_1000.epd"
fens = [" ".join(l.split()[:4]) for l in open(BOOK).read().splitlines() if l.strip()][::80][:12]
tot = 0
for f in fens:
    r = Engine(use_book=False, use_tablebase=False).best_move(
        chess.Board(f), movetime=999.0, max_depth=11)
    tot += r.nodes
before = int(open("/tmp/pc_before.txt").read())
print(f"after:  {tot:,} nodes")
print("TREE-IDENTICAL" if tot == before else f"*** DIFFERS by {tot-before} ***")
PY
PYTHONPATH=. "$PY" -m pytest -q -m 'not slow' 2>&1 | tail -2

"""Write the decisive-loss-tuned piece-square tables back as VISUAL blocks.

The tables are written rank-8-at-the-top on purpose -- a reader can see the
shape of the knight's preference for the centre at a glance, and that
readability is part of what this engine is for. Dumping tuned values as a flat
array of 64 floats would keep the Elo and throw that away, so the tuned numbers
go back in the same visual layout, rounded to integers.

Takes the tuner's output file as its argument:

    PYTHONPATH=. .venv/bin/python research/apply_pst.py research/data/pst_linear.json
"""
import json
import pathlib
import re
import sys

CC = pathlib.Path(__file__).resolve().parent.parent
SRC = (pathlib.Path(sys.argv[1]) if len(sys.argv) > 1
       else CC / "research/data/pst_tuned.json")
TUNED = json.load(open(SRC))["tables"]

NAME_TO_VIS = {"PAWN_MG": "_PAWN_MG_VIS", "PAWN_EG": "_PAWN_EG_VIS",
               "KNIGHT": "_KNIGHT_VIS", "BISHOP": "_BISHOP_VIS",
               "ROOK": "_ROOK_VIS", "QUEEN": "_QUEEN_VIS",
               "KING_MG": "_KING_MG_VIS", "KING_EG": "_KING_EG_VIS"}

p = CC / "engine/concepts/piece_placement.py"
s = p.read_text()

for name, var in NAME_TO_VIS.items():
    tbl = TUNED[name]
    # internal index is square number (rank 1 first); visual is rank 8 first
    rows = []
    for r in range(7, -1, -1):
        vals = [int(round(tbl[r * 8 + f])) for f in range(8)]
        rows.append("    " + ",".join(f"{v:4d}" for v in vals) + ",")
    block = f"{var} = [\n" + "\n".join(rows) + "\n]"
    pat = re.compile(re.escape(var) + r" = \[.*?\n\]", re.S)
    s, n = pat.subn(lambda m: block, s, count=1)
    assert n == 1, f"could not find {var}"

p.write_text(s)
print("rewrote 8 piece-square tables, visual layout preserved")

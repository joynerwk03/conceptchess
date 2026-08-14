"""Apply a joint fit: weights, piece-square tables, and the passed-pawn curve.

    PYTHONPATH=. .venv/bin/python research/apply_fit_all.py [json]
"""
import json
import pathlib
import re
import subprocess
import sys

CC = pathlib.Path(__file__).resolve().parent.parent
SRC = (pathlib.Path(sys.argv[1]) if len(sys.argv) > 1
       else CC / "research/data/fit_all.json")
FIT = json.load(open(SRC))

# --- weights: reuse the writer that knows about the two dict sections -------
tmp = CC / "research/data/_fit_all_weights.json"
json.dump({"weights": FIT["weights"]}, open(tmp, "w"))
subprocess.run([sys.executable, str(CC / "research/apply_linfit.py"), str(tmp)],
               check=True, cwd=str(CC))
tmp.unlink()

# --- piece-square tables ---------------------------------------------------
json.dump({"tables": FIT["tables"]}, open(tmp, "w"))
subprocess.run([sys.executable, str(CC / "research/apply_pst.py"), str(tmp)],
               check=True, cwd=str(CC))
tmp.unlink()

# --- passed-pawn curve -----------------------------------------------------
p = CC / "engine/concepts/pawn_structure.py"
s = p.read_text()
cur = [0] * 8
m = re.search(r"PASSED_BONUS = \[([^\]]*)\]", s)
assert m, "PASSED_BONUS not found"
cur = [int(x) for x in m.group(1).split(",")]
for k, v in FIT["passed_bonus"].items():
    cur[int(k)] = int(round(v))
new = "PASSED_BONUS = [" + ", ".join(str(v) for v in cur) + "]"
s = s[:m.start()] + new + s[m.end():]
p.write_text(s)
print(f"passed-pawn curve by rank -> {cur}")

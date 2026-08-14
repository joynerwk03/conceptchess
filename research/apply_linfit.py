"""Write linfit_tr's tuned weights back into engine/weights.py.

research/tune.py's writer only knows about W, and asserts each key matches
exactly once -- which fails outright for any key that also has an endgame
value, since the same name appears in both dicts. This one edits the two
sections separately, so a tapered weight's middlegame and endgame values go
to the right places.

Comments are preserved: they carry the chess reasoning for each number, which
is the part a reader needs and a tuner cannot regenerate.

    PYTHONPATH=. .venv/bin/python research/apply_linfit.py [json]
"""
import json
import pathlib
import re
import sys

CC = pathlib.Path(__file__).resolve().parent.parent
SRC = (pathlib.Path(sys.argv[1]) if len(sys.argv) > 1
       else CC / "research/data/linfit_tr.json")
TUNED = json.load(open(SRC))["weights"]

p = CC / "engine/weights.py"
lines = p.read_text().split("\n")

# section boundaries: W = { ... }  then  W_EG: dict[...] = { ... }
starts = [i for i, l in enumerate(lines) if l.startswith("W = {")]
egs = [i for i, l in enumerate(lines) if l.startswith("W_EG")]
assert len(starts) == 1 and len(egs) == 1, "unexpected weights.py shape"
w_lo, eg_lo = starts[0], egs[0]
w_hi = next(i for i in range(w_lo, len(lines)) if lines[i] == "}")
eg_hi = next(i for i in range(eg_lo, len(lines)) if lines[i] == "}")


def fmt(v):
    v = round(float(v), 4)
    return str(int(v)) if v == int(v) else str(v)


def patch(lo, hi, values):
    n = 0
    for i in range(lo, hi):
        for key, val in values.items():
            new, k = re.subn(rf'("{re.escape(key)}":\s*)[-\d.]+',
                             lambda m: m.group(1) + fmt(val), lines[i])
            if k:
                lines[i] = new
                n += k
    return n


nw = patch(w_lo, w_hi, TUNED["mg"])
ne = patch(eg_lo, eg_hi, TUNED["eg"])
print(f"rewrote {nw} middlegame and {ne} endgame weights")
assert nw == len(TUNED["mg"]), f"{nw} != {len(TUNED['mg'])} middlegame keys"
assert ne == len(TUNED["eg"]), f"{ne} != {len(TUNED['eg'])} endgame keys"
p.write_text("\n".join(lines))

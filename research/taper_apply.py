"""Apply the fitted (MG, EG) pairs to weights.py, in a worktree.

mg_k = W[k]*m_k goes back into W; eg_k = W[k]*e_k becomes a NEW W_EG entry. A key
absent from W_EG means "same in both phases", so adding one is exactly what
tapering that term means -- the concept keeps its name and gains a
phase-dependent value, which is why this preserves interpretability.

Usage: taper_apply.py <worktree> <taper_sol.npz>
"""
import pathlib
import re
import sys

import numpy as np

WT = pathlib.Path(sys.argv[1])
sol = np.load(sys.argv[2], allow_pickle=True)
keys = [str(x) for x in sol["keys"]]
m, e = sol["m"], sol["e"]

sys.path.insert(0, str(WT))
from engine.weights import W  # noqa: E402

p = WT / "engine/weights.py"
s = p.read_text()

# 1. rescale the middlegame value in place, preserving each line's comment
for i, k in enumerate(keys):
    new = W[k] * float(m[i])
    pat = re.compile(r'^(\s*"' + re.escape(k) + r'":\s*)(-?[\d.]+)(,.*)$', re.M)
    got = pat.findall(s)
    assert len(got) == 1, f"{k}: {len(got)} matches in W"
    s = pat.sub(lambda mo: f"{mo.group(1)}{new:.4f}{mo.group(3)}", s, count=1)

# 2. add the endgame values as new W_EG entries
block = "".join(
    f'    "{k}": {W[k] * float(e[i]):.4f},'
    f'  # tapered s33: EG/MG {float(e[i]) / float(m[i]):.2f}\n'
    for i, k in enumerate(keys))
anchor = "W_EG: dict[str, float] = {\n"
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + block, 1)

p.write_text(s)
print(f"applied {len(keys)} tapered pairs to {p}")

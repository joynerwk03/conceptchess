"""Bundle the two candidates that screened BETTER than baseline but individually failed.

Precedent from this project: the one merged search stack -- history-modulated
LMR, the king-attack endgame taper and a wider aspiration window -- was built
from changes that were individually under the significance bar and merged as a
combination. Of twenty candidates screened since, exactly two read on the good
side of baseline and neither was ever bundled:

    caplmr   -0.998   reduce late LOSING captures (SEE < 0), which LMR currently
                      skips because it is gated on `quiet`
    caphist  -0.657   order captures by cutoff history as well as SEE; quiets
                      already get this signal and captures do not

Both are capture-side and touch different mechanisms -- one reduces, one orders
-- so they are plausibly additive rather than redundant. caplmr gated at -4.3 and
+2.7, essentially zero; caphist was never gated at all.

Low prior, stated up front: the screen's calibrated scale is
Elo = -7.3 * (d_mean + 1.0), so break-even is d_mean -1.0 and the bar for
spending games is below -2. Individually these sit at break-even. If the bundle
does not reach -2 it is closed with them, for the cost of one 20-minute screen.

Usage: bundle.py <worktree>
"""
import pathlib
import subprocess
import sys

WT = pathlib.Path(sys.argv[1])
R = "/home/joynerwk03/ccruns"

# newfeat.py owns caplmr, iir.py owns caphist; apply both to the same tree
for script, mode in (("newfeat.py", "caplmr"), ("iir.py", "caphist")):
    r = subprocess.run([sys.executable, f"{R}/{script}", str(WT), mode],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"{script} {mode} failed")
    print(r.stdout.strip())

src = (WT / "core/csearch.c").read_text()
assert "see(b,m)<0) red=2" in src, "caplmr did not apply"
assert "caphist" in src, "caphist did not apply"
print("bundle applied: caplmr + caphist")

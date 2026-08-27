"""Apply a search-parameter vector to a worktree. Search only -- the eval is untouched.

Every search experiment in this project changed ONE constant and most measured
neutral. That is exactly the regime where joint tuning finds what single-axis
sweeps cannot: the constants interact (a wider RFP margin changes which nodes
LMR ever sees), so the surface can be flat along every axis and still have a
better point off-axis.

Parameters, with the seeds that are currently merged:

    rfp    RFP_MARGIN          90     cp conceded per ply by reverse futility
    lmp    LMP_DEPTH            5     max depth at which late quiets are skipped
    lmr2   LMR second threshold 3     move index at which red goes to 2
    lmr3   LMR third threshold 12     move index at which red goes to 3
    asp    aspiration delta    35     initial window half-width
    hist   history divisor   8192     scale of the history-modulated reduction

Bounds are chess-priors, not tuner artefacts: each is wide enough to contain a
real optimum and narrow enough that a runaway step cannot produce a degenerate
search. Values are rounded to integers because they ARE integers in the source.

Usage: spsa_patch.py <worktree> rfp=90 lmp=5 lmr2=3 lmr3=12 asp=35 hist=8192
"""
import pathlib
import sys

BOUNDS = {"rfp": (40, 160), "lmp": (3, 10), "lmr2": (2, 6),
          "lmr3": (6, 20), "asp": (12, 70), "hist": (2048, 32768)}


def clamp(k, v):
    lo, hi = BOUNDS[k]
    return int(round(max(lo, min(hi, v))))


def apply(wt, p):
    path = pathlib.Path(wt) / "core/csearch.c"
    s = path.read_text()

    def sub(old, new, what):
        nonlocal s
        assert s.count(old) == 1, f"{what}: anchor not unique ({s.count(old)})"
        s = s.replace(old, new, 1)

    sub("#define RFP_MARGIN 90", f"#define RFP_MARGIN {p['rfp']}", "rfp")
    sub("#define LMP_DEPTH 5", f"#define LMP_DEPTH {p['lmp']}", "lmp")
    sub("if(i>=12)red=3; else if(i>=3)red=2;",
        f"if(i>={p['lmr3']})red=3; else if(i>={p['lmr2']})red=2;", "lmr")
    sub("int delta = 35;", f"int delta = {p['asp']};", "asp")
    sub("MV_TO(m)] / 8192;", f"MV_TO(m)] / {p['hist']};", "hist")
    path.write_text(s)


if __name__ == "__main__":
    wt = sys.argv[1]
    p = {}
    for a in sys.argv[2:]:
        k, v = a.split("=")
        p[k] = clamp(k, float(v))
    apply(wt, p)
    print(" ".join(f"{k}={v}" for k, v in sorted(p.items())))

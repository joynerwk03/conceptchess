"""Two mechanisms this search lacks: internal iterative reduction, and capture history.

  iir      When a node has NO TT move, its move ordering is known to be
           unreliable, yet the search still invests full depth there. Internal
           iterative reduction spends one ply instead. This is a THINNING change
           justified by INFORMATION rather than by a margin: we do not prune
           because a number crossed a threshold, we reduce because we know
           ordering is bad at this specific node. Every one of the seven failed
           thinners here discarded information on a margin; the one merged search
           change (history-modulated LMR) spent information instead.

  caphist  Captures are ordered purely by SEE:
               sc[i] = (s>=0) ? (100000+s) : (-1000000+s);
           The search records which QUIETS caused cutoffs and never does the same
           for captures. Prior is low -- 88.82% of cutoffs already come on the
           first move, and continuation history died against that ceiling -- but
           capture ordering is a different slice than the quiet ordering that was
           tested, and it is cheap.

Both fire at every depth, so unlike lmrdeep they are testable at a depth-9
screen. Check the rule can fire at the screen depth before trusting a reading.

Usage: iir.py <worktree> <iir|caphist>
"""
import pathlib
import sys

WT = pathlib.Path(sys.argv[1])
MODE = sys.argv[2]
p = WT / "core/csearch.c"
s = p.read_text()


def sub(old, new):
    global s
    assert s.count(old) == 1, f"{MODE}: anchor not unique ({s.count(old)})"
    s = s.replace(old, new, 1)


if MODE == "iir":
    # after the TT probe block, before the move loop: no tt move => reduce a ply
    sub("""    /* singular extension: a deep, trusted TT fail-high move -- if a reduced-depth""",
        """    /* Internal iterative reduction: with no TT move this node's ordering is
     * unreliable, so spend a ply rather than invest full depth in a badly
     * ordered search. Thinning justified by information, not by a margin. */
    if(!done && !ttm && depth>=4 && !checked) depth--;

    /* singular extension: a deep, trusted TT fail-high move -- if a reduced-depth""")

elif MODE == "caphist":
    sub("    int history[2][64][64];",
        "    int history[2][64][64];\n    int caphist[2][64][64];   /* cutoffs by capture, mirroring quiet history */")
    sub("            sc[i] = (s>=0) ? (100000+s) : (-1000000+s);",
        """            /* order winning captures by SEE plus how often this capture has
             * actually produced a cutoff; quiets already get this signal. */
            int ch = SS.caphist[b->side][MV_FROM(m)][MV_TO(m)] / 64;
            if(ch > 400) ch = 400; else if(ch < -400) ch = -400;
            sc[i] = (s>=0) ? (100000+s+ch) : (-1000000+s);""")
    sub("                SS.history[b->side][MV_FROM(m)][MV_TO(m)] += bonus;",
        """                SS.history[b->side][MV_FROM(m)][MV_TO(m)] += bonus;
                if(is_capture(b,bestm))
                    SS.caphist[b->side][MV_FROM(bestm)][MV_TO(bestm)] += bonus;""")

else:
    raise SystemExit(f"unknown mode {MODE}")

p.write_text(s)
print(f"patched {p} ({MODE})")

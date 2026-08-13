"""Razoring: at very shallow depth, a position far below alpha is unlikely to be
rescued by a quiet move, so verify with qsearch and fail low if it agrees.

Absent from this engine entirely. Sits beside reverse futility, which handles
the mirror case (far ABOVE beta).
"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1]) / "core/csearch.c"
s = p.read_text()

a = "#define LMP_DEPTH 5"
b = ("#define RAZOR_DEPTH 3    /* razoring: max depth to try the qsearch shortcut */\n"
     "#define RAZOR_MARGIN 240 /* ...and how far below alpha the eval must sit */\n"
     "#define LMP_DEPTH 5")
assert a in s, "LMP_DEPTH define not found"
s = s.replace(a, b, 1)

a = """    /* reverse futility pruning (static null move): at shallow depth in a"""
b = """    /* Razoring: the mirror of reverse futility. If the static eval sits far
     * BELOW alpha at very shallow depth, a quiet move is unlikely to rescue the
     * position -- so ask quiescence, which is cheap, and fail low if it agrees.
     * Verified rather than assumed: qsearch still gets to find the tactic that
     * makes the position playable. */
    if(!pvnode && !checked && depth<=RAZOR_DEPTH
       && alpha>-S_MATE_TH && alpha<S_MATE_TH){
        int st=eval_stm(b);
        if(st + RAZOR_MARGIN*depth < alpha){
            int rs=qsearch(b,alpha-1,alpha,ply,0);
            if(SS.stopped){ SS.path_len--; return 0; }
            if(rs < alpha){ SS.path_len--; return rs; }
        }
    }

    /* reverse futility pruning (static null move): at shallow depth in a"""
assert a in s, "RFP comment not found"
s = s.replace(a, b, 1)

p.write_text(s)
print("razoring applied")

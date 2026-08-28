"""Three search features this engine does not have, for batch triage on the iso-node screen.

The knobs have all been swept -- RFP margin, LMP depth, LMR thresholds,
null-move R, aspiration delta -- and SPSA found nothing off-axis either. What
has NOT been tried is missing MECHANISM. These are three standard ones this
search lacks entirely.

  caplmr   LMR currently applies to quiets only (`depth>=3 && quiet && !checked`).
           Late LOSING captures are searched at full depth forever. Reducing
           them is standard and costs nothing in accuracy when SEE says the
           capture loses material.

  razor    At shallow depth, when the static eval sits far BELOW alpha, drop
           straight to quiescence instead of searching the full move list. The
           mirror of reverse futility, which this engine has; razoring is its
           missing other half.

  fmargin  Futility currently fires at depth<=2 with a fixed margin. Scale it
           with depth (`110*depth`) so it stays live one ply deeper, matching
           the shape of every other margin in the search.

Judged on the ISO-NODE screen: all three change tree size, which is exactly what
the fixed-depth screen cannot price and what this instrument was built for. All
three fire at remaining depth <= 3, so unlike lmrdeep they are testable at a
depth-9 screen -- check the rule can fire at the screen depth before trusting a
reading.

Usage: newfeat.py <worktree> <caplmr|razor|fmargin>
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


if MODE == "caplmr":
    sub("""            if(depth>=3 && quiet && !checked){ if(i>=12)red=3; else if(i>=3)red=2;""",
        """            /* Late LOSING captures are searched at full depth today: LMR is
             * gated on `quiet`. A capture that SEE says loses material is no
             * more likely to be best than a late quiet, so reduce it too. */
            if(depth>=3 && !quiet && !checked && i>=6 && see(b,m)<0) red=2;
            if(depth>=3 && quiet && !checked){ if(i>=12)red=3; else if(i>=3)red=2;""")

elif MODE == "razor":
    sub("""    if(!done && depth<=0){ ret=qsearch(b,alpha,beta,ply,0); done=1; }""",
        """    /* Razoring: the missing mirror of reverse futility. At shallow depth,
     * when the static eval is far BELOW alpha, this node is very unlikely to
     * raise it, so verify with quiescence instead of searching every move. */
    if(!done && !pvnode && !checked && depth<=2
       && alpha>-S_MATE_TH && alpha<S_MATE_TH
       && eval_stm(b) + 240*depth < alpha){
        int rs = qsearch(b,alpha,alpha+1,ply,0);
        if(rs <= alpha){ ret=rs; done=1; }
    }
    if(!done && depth<=0){ ret=qsearch(b,alpha,beta,ply,0); done=1; }""")

elif MODE == "fmargin":
    sub("""    if(depth<=2 && !checked && (alpha>-S_MATE_TH&&alpha<S_MATE_TH)){""",
        """    /* depth-scaled futility: every other margin in this search grows with
     * depth; this one was a flat rule capped at 2. */
    if(depth<=3 && !checked && (alpha>-S_MATE_TH&&alpha<S_MATE_TH)){""")

else:
    raise SystemExit(f"unknown mode {MODE}")

p.write_text(s)
print(f"patched {p} ({MODE})")

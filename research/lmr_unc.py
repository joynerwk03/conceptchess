"""Uncertainty-modulated LMR: reduce harder where the evaluation is trustworthy.

Our eval is measurably 1.71x less accurate in positions dominated by
non-material judgement (top third |eval - material| against bottom third,
against SF11 depth-13 scores). LMR currently reduces by move index alone, with
no reference to whether the eval backing that decision is reliable.

Why LMR rather than RFP, having already failed once at RFP. The thresholds were
NOT the problem: measured at LMR-eligible nodes the terciles are 40 and 100cp,
against the 43 and 94 taken from root positions, so the distributions are nearly
identical and my stated explanation for that failure was wrong. The real reason
is granularity -- RFP's margin at depth 6 is 540cp, against which a ~100cp
uncertainty signal is second order. LMR decides a 2-3 ply reduction, which is a
far finer decision and is exactly where eval reliability should matter.

    |eval - material| < 40   confident  -> reduce one MORE
    40 .. 100                unchanged
    > 100                    uncertain  -> reduce one LESS (never below 1)

Direction matches the one search change that has ever worked here:
history-modulated LMR reduces LESS on quiets the search has proven useful, i.e.
it SPENDS information rather than discarding it. This spends a different piece of
information the engine already has and currently throws away.

Cost is near zero: eval_stm is hash-cached and this node has almost certainly
probed it already for RFP or the improving flag, so it is an L1 hit -- the
recorded finding that hoisting four probes to one measured exactly zero NPS.

Interpretability: a search reduction, not an eval term. eval_check must stay
0.000000.

Usage: lmr_unc.py <worktree> <mild|firm>
"""
import pathlib
import sys

WT = pathlib.Path(sys.argv[1])
MODE = sys.argv[2] if len(sys.argv) > 2 else "mild"
p = WT / "core/csearch.c"
s = p.read_text()

OLD = """            if(depth>=3 && quiet && !checked){ if(i>=12)red=3; else if(i>=3)red=2;
                if(red>1 && !improving) red++;"""

# mild: only relax on uncertainty. firm: also tighten on confidence.
extra = ("""                    if(u > 100) red--;"""
         if MODE == "mild" else
         """                    if(u > 100) red--; else if(u < 40) red++;""")

NEW = f"""            if(depth>=3 && quiet && !checked){{ if(i>=12)red=3; else if(i>=3)red=2;
                if(red>1 && !improving) red++;
                /* Trust the eval less where it is measurably less accurate: the
                 * top third of nodes by |eval - material| carry 1.71x the
                 * static-eval error of the bottom third. Terciles measured at
                 * LMR-eligible nodes are 40 and 100cp. */
                if(red>1){{
                    int _m = 0;
                    for(int _p=PAWN;_p<=QUEEN;_p++)
                        _m += SEEV[_p]*(__builtin_popcountll(b->bb[b->side][_p])
                                      - __builtin_popcountll(b->bb[!b->side][_p]));
                    int u = eval_stm(b) - _m; if(u<0) u = -u;
{extra}
                    if(red<1) red=1;
                }}"""

assert s.count(OLD) == 1, f"LMR block not found ({s.count(OLD)})"
p.write_text(s.replace(OLD, NEW, 1))
print(f"patched {p} (uncertainty-modulated LMR, {MODE})")

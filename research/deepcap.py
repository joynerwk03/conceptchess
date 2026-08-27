"""Scale the reductions ONLY where they currently do not scale: remaining depth >= 7.

`red` is keyed on move index alone -- 3 max, 4 when not improving -- with no
depth term whatsoever. At remaining depth 20 a late quiet is reduced by 3, the
same as at remaining depth 4. LMP stops at depth 5 and RFP at depth 6, so past
remaining-depth 6 this is close to plain alpha-beta. That is the standing
explanation for our EBF RISING (1.80 -> 2.11) where SF11's FALLS (1.98 -> 1.51).

This is NOT the experiment that measured -57.2/-33.7. That one replaced the
whole schedule (`red = 0.7 + ln(d)*ln(m)/0.80`), changing reductions at EVERY
depth including the shallow nodes where five separate gates say this engine is
already at a local optimum. Here every node below remaining depth 7 is
BIT-IDENTICAL, and only the region the EBF curve says is unpruned changes.

  lmr    depth>=7 adds (depth-7)/5 + 1 to an already-reduced quiet
  lmp    LMP_DEPTH 5 -> 9 (the quadratic count already widens with depth)
  both   both of the above

Judged on the EBF curve and node counts, NOT on the fixed-depth referee screen:
this changes work per nominal depth, which is precisely what that screen cannot
price and what this project has misread twice.

Usage: deepcap.py <worktree> <lmr|lmp|both>
"""
import pathlib
import sys

WT = pathlib.Path(sys.argv[1])
MODE = sys.argv[2]
p = WT / "core/csearch.c"
s = p.read_text()

if MODE in ("lmr", "both"):
    old = """            if(depth>=3 && quiet && !checked){ if(i>=12)red=3; else if(i>=3)red=2;
                if(red>1 && !improving) red++;"""
    new = """            if(depth>=3 && quiet && !checked){ if(i>=12)red=3; else if(i>=3)red=2;
                if(red>1 && !improving) red++;
                /* Scale with depth ONLY past the region that already prunes.
                 * Below remaining depth 7 this is bit-identical to the tuned
                 * schedule; above it, `red` had no depth term at all, which is
                 * why the tree stops thinning where SF11's keeps thinning. */
                if(depth>=7 && red>1) red += (depth-7)/5 + 1;"""
    assert s.count(old) == 1, "LMR block not found"
    s = s.replace(old, new, 1)

if MODE in ("lmp", "both"):
    old = "#define LMP_DEPTH 5      /* late-move pruning: max depth to skip late quiets */"
    new = "#define LMP_DEPTH 9      /* late-move pruning: max depth to skip late quiets */"
    assert s.count(old) == 1, "LMP_DEPTH not found"
    s = s.replace(old, new, 1)

p.write_text(s)
print(f"patched {p} (deep caps: {MODE})")

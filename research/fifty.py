"""50-move discounting: the evaluation currently cannot see the halfmove clock.

`eval_core(U64 bb[2][6], int side)` does not receive it. So a won endgame 95
halfmoves into the counter evaluates identically to a fresh one, and the search
cannot steer toward the pawn move or capture that resets the clock and saves the
win -- both look the same in eval terms.

This is the category that has actually worked in this project. Sorting every
attempt by kind: ten margin tunings produced nothing, four missing standard
mechanisms produced nothing, and of three exact-structural-knowledge changes two
worked (contempt, the KPvK bitbase). This is the third of that kind.

Applied in eval_stm, AFTER the eval hash lookup, because the hash key does not
include the halfmove clock -- caching a discounted score would return the wrong
value for the same position at a different clock. Terminal scores (mate,
tablebase, draw) never pass through eval_stm, so they are correctly unaffected.

Interpretability: eval_check compares c_eval against Python evaluate, and c_eval
calls eval_core directly, so this cannot move it. The concept sum is untouched;
this is a search-side discount, like contempt and the KPvK probe.

Modes:
  sf    v * (100 - hm) / 100          Stockfish 11's rule exactly
  soft  discount only past hm 40      gentler, in case the SF rule is too eager
                                      in ordinary middlegames where hm reaches
                                      20-40 without any draw being near

Usage: fifty.py <worktree> <sf|soft>
"""
import pathlib
import sys

WT = pathlib.Path(sys.argv[1])
MODE = sys.argv[2] if len(sys.argv) > 2 else "sf"
p = WT / "core/csearch.c"
s = p.read_text()

marker = "static int eval_stm(Board *b){"
assert s.count(marker) == 1, "eval_stm not found"

# find the function body and patch every return so the discount applies to the
# cached path as well as the computed one
start = s.index(marker)
end = s.index("\n}", start)
body = s[start:end]

if MODE == "sf":
    disc = ("""    { int _hm = b->hm; if(_hm > 100) _hm = 100;
      if(_hm > 0) _v = (int)(((long)_v * (100 - _hm)) / 100); }""")
else:
    disc = ("""    { int _hm = b->hm; if(_hm > 100) _hm = 100;
      if(_hm > 40) _v = (int)(((long)_v * (140 - _hm)) / 100); }""")

# rewrite `return X;` as `{ int _v = X; <discount> return _v; }`
out = []
n = 0
for line in body.split("\n"):
    stripped = line.strip()
    if stripped.startswith("return ") and stripped.endswith(";"):
        expr = stripped[len("return "):-1]
        indent = line[:len(line) - len(line.lstrip())]
        out.append(f"{indent}{{ int _v = {expr};")
        out.append(disc)
        out.append(f"{indent}  return _v; }}")
        n += 1
    else:
        out.append(line)
assert n >= 1, "no returns found in eval_stm"

s = s[:start] + "\n".join(out) + s[end:]
p.write_text(s)
print(f"patched {p} (50-move discount, {MODE}, {n} return sites)")

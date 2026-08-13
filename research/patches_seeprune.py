"""SEE pruning of losing captures in the main search.

Losing captures are currently searched at FULL WIDTH here -- ordering demotes
them below quiets, but nothing skips them. At shallow depth in a non-PV node a
capture that loses material by static exchange almost never rescues the
position, and searching it costs a whole subtree.

Captures only. see() takes its first gain from the piece standing on the
destination square, so it is not meaningful for a quiet move -- applying it to
quiets would be pruning on a number that means nothing.
"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1]) / "core/csearch.c"
s = p.read_text()

a = "#define LMP_DEPTH 5"
b = ("#define SEEP_DEPTH 6     /* SEE pruning: max depth to skip losing captures */\n"
     "#define SEEP_MARGIN 90   /* ...cp of loss tolerated per ply of depth */\n"
     "#define LMP_DEPTH 5")
assert a in s, "LMP_DEPTH define not found"
s = s.replace(a, b, 1)

# Insert before the board copy, so a pruned move costs no make().
a = """        int ext = (m==ttm)? sing_ext : 0;     /* singular extension applies to the TT move */
        Board c=*b; make(&c,m);"""
b = """        int ext = (m==ttm)? sing_ext : 0;     /* singular extension applies to the TT move */
        /* Losing captures were searched at full width: ordering pushes them
         * below the quiets but nothing skipped them. At shallow depth in a
         * non-PV node, a capture that drops material by static exchange is
         * very unlikely to be the move -- and it costs an entire subtree.
         * Checked BEFORE make(), so a pruned move costs nothing at all. */
        if(!pvnode && !quiet && bestm && !checked && depth<=SEEP_DEPTH
           && MV_PROMO(m)==0 && see(b,m) < -SEEP_MARGIN*depth){ continue; }
        Board c=*b; make(&c,m);"""
assert a in s, "move-loop anchor not found"
s = s.replace(a, b, 1)

p.write_text(s)
print("SEE pruning applied")

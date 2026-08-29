"""Three more never-touched constants, for one more batch screen.

  qd120 / qd320   Quiescence delta-pruning margin, seeded 200 in
                  `if(stand+victim+200<alpha) continue;`. This decides which
                  captures quiescence bothers with. Never swept. Too tight and
                  it discards real tactics; too loose and quiescence bloats.

  hb_lin          History bonus is `depth*depth`, so a depth-12 cutoff is worth
                  144x a depth-1 one and deep noise dominates the table. Most
                  engines cap or linearise it. `4*depth` keeps the ordering
                  signal but stops one deep node from swamping the statistics.

All three fire at every depth, so they genuinely fire at the depth-9 screen --
the check that invalidated the earlier lmrdeep reading.

Screened, not gated. The bar before spending games is d_mean < -2, from the
screen's calibrated scale Elo ~ -7.3 * (d_mean + 1.0). Eleven candidates have
been screened this way and the best read -0.998, which then gated at zero, so
the prior here is low and the value is in closing them cheaply.

Usage: margins3.py <worktree> <qd120|qd320|hb_lin>
"""
import pathlib
import sys

WT = pathlib.Path(sys.argv[1])
MODE = sys.argv[2]
p = WT / "core/csearch.c"
s = p.read_text()

REPL = {
    "qd120":  ("if(stand+victim+200<alpha) continue;",
               "if(stand+victim+120<alpha) continue;"),
    "qd320":  ("if(stand+victim+200<alpha) continue;",
               "if(stand+victim+320<alpha) continue;"),
    "hb_lin": ("int bonus=depth*depth;",
               "int bonus=4*depth;   /* linear: stop deep nodes swamping the table */"),
}
old, new = REPL[MODE]
assert s.count(old) == 1, f"{MODE}: anchor not unique ({s.count(old)})"
p.write_text(s.replace(old, new, 1))
print(f"patched {p} ({MODE})")

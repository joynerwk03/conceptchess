"""Three untouched margins, for batch triage on the iso-node screen.

RFP margin, LMP depth, LMR thresholds, null-move R and aspiration delta have all
been swept, and SPSA found nothing off-axis. These three have never been touched
at all:

  pcm150 / pcm220   PROBCUT_MARGIN, seeded 180. ProbCut returns a score from a
                    shallow search when a capture clears beta by this much, so
                    the margin trades how often it fires against how often it is
                    wrong. Never swept.
  pcd4              PROBCUT_DEPTH 5 -> 4, letting ProbCut fire one ply shallower.
                    It currently cannot fire below remaining depth 5, which on a
                    depth-9 screen is only the top four plies.

All fire at remaining depth 4-5 or above, so on a depth-9 screen they DO fire --
the check that invalidated the lmrdeep reading. Screened, not gated: the bar
before spending games is d_mean < -2, from the screen's calibrated Elo scale
(Elo ~ -7.3 * (d_mean + 1.0)).

Usage: margins2.py <worktree> <pcm150|pcm220|pcd4>
"""
import pathlib
import sys

WT = pathlib.Path(sys.argv[1])
MODE = sys.argv[2]
p = WT / "core/csearch.c"
s = p.read_text()

REPL = {
    "pcm150": ("#define PROBCUT_MARGIN 180", "#define PROBCUT_MARGIN 150"),
    "pcm220": ("#define PROBCUT_MARGIN 180", "#define PROBCUT_MARGIN 220"),
    "pcd4":   ("#define PROBCUT_DEPTH 5", "#define PROBCUT_DEPTH 4"),
}
old, new = REPL[MODE]
assert s.count(old) == 1, f"{MODE}: anchor not unique ({s.count(old)})"
p.write_text(s.replace(old, new, 1))
print(f"patched {p} ({MODE})")

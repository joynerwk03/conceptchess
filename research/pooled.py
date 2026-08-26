"""Pooled estimate from the completed 600-game run plus the run in flight.

The decision this supports: the goal needs the WHOLE interval above 3000, so the
pooled point estimate must exceed the pooled half-width. The completed run gave
+3 Elo over 600 games (+151 =303 -146). If the pooled figure is still sitting
near +3 once the new run has a few hundred games in it, no feasible game count
will clear 3000 and the remaining hours are better spent elsewhere.

Reads the live progress log, so it can be run at any time without disturbing the
measurement.

Reports both the pooled estimate and, more usefully, the answer to "how many
total games would this need in order to clear 3000, if the current pooled score
is the truth" -- which is the number that decides whether to keep going.
"""
import math
import pathlib
import re

LOG = pathlib.Path("/home/joynerwk03/ccruns/rating_progress.log")

# completed run: 600 games at openings 0+, +151 =303 -146
PREV_W, PREV_D, PREV_L = 151, 303, 146

w = d = l = 0
if LOG.exists():
    for m in re.finditer(r"\(us: (win|draw|loss)\)", LOG.read_text()):
        k = m.group(1)
        w += k == "win"
        d += k == "draw"
        l += k == "loss"

def elo(score):
    score = min(max(score, 1e-6), 1 - 1e-6)
    return -400.0 * math.log10(1.0 / score - 1.0)

def report(name, W, D, L):
    n = W + D + L
    if n == 0:
        print(f"{name}: no games yet")
        return None
    s = (W + 0.5 * D) / n
    # per-game variance of the score, then SE of the mean
    var = (W * (1 - s) ** 2 + D * (0.5 - s) ** 2 + L * (0 - s) ** 2) / n
    se = math.sqrt(var / n)
    slope = 400.0 / (math.log(10) * s * (1 - s))
    e, half = elo(s), 1.96 * se * slope
    print(f"{name}: {W}W {D}D {L}L  n={n}  score {100*s:.2f}%  "
          f"Elo {e:+.1f}  95% [{e-half:+.1f}, {e+half:+.1f}]  -> "
          f"rating {3000+e:.0f} [{3000+e-half:.0f}, {3000+e+half:.0f}]")
    return s, e, se, slope

print("=== completed run (openings 0+) ===")
report("  600 games", PREV_W, PREV_D, PREV_L)
print("=== run in flight (openings 300+) ===")
report("  live     ", w, d, l)
print("=== POOLED ===")
r = report("  pooled   ", PREV_W + w, PREV_D + d, PREV_L + l)

if r:
    s, e, se, slope = r
    n = PREV_W + PREV_D + PREV_L + w + d + l
    print()
    if e <= 0:
        print("  Pooled estimate is at or below zero: no game count clears 3000.")
    else:
        # half-width shrinks as 1/sqrt(n); find n where half-width < e
        var_per = (se ** 2) * n
        need = var_per * (1.96 * slope / e) ** 2
        print(f"  To clear 3000 at this score would need ~{need:,.0f} total games "
              f"({n:,} played).")
        if need > 6000:
            print("  That is not affordable at ~126s/game -- the score has to rise, "
                  "not the sample.")

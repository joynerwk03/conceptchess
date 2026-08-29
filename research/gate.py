"""Two-anchor gate with early abandonment, replacing flat 2-hour fixed-N runs.

The measured shape of this project's candidates decides the design. Of seventeen
tried, roughly eleven were genuinely NEUTRAL, four clearly negative and two
positive. Full SPRT with tight bounds is fast at rejecting clearly-bad changes
but converges SLOWLY on neutral ones, because a truly-zero change sits on the H0
boundary -- and neutral is the common case here, so SPRT would often cost more
than fixed-N. That is why this is staged abandonment rather than SPRT; the
arithmetic did not support the tool I first reached for.

What it does:
  * runs the anchor in batches with a FRESH OPENING OFFSET each time, so pooled
    slots are distinct positions rather than repeats
  * abandons as soon as the pooled estimate is decisively negative, since the
    merge rule is "both anchors positive" and one clear rejection settles it
  * skips anchor 2 entirely when anchor 1 was abandoned -- currently that second
    anchor is run regardless, and it is pure waste on a rejection

Expected saving, from the observed mix: rejections drop from ~2h to ~30min,
about 6h across seventeen candidates, roughly 18%. Real, and smaller than the
25x available from testing phase-specific changes on an endgame book -- use both.

Usage:
  gate.py <candidate_cwd> <baseline_cwd> [--book B] [--movetime T]
          [--anchors a,b] [--slots N] [--batch N] [--abandon ELO]
"""
import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

CC = Path("/home/joynerwk03/mission-control/projects/conceptchess")
PY = str(CC / ".venv/bin/python")


def batch(cand, base, anchor, offset, games, movetime, book, concurrency):
    cmd = [PY, "-u", "-m", "research.abgate", "--games", str(games),
           "--opponent", anchor, "--baseline-cwd", str(base),
           "--movetime", str(movetime), "--threads", "1",
           "--concurrency", str(concurrency), "--opening-offset", str(offset)]
    if book:
        cmd += ["--book", book]
    r = subprocess.run(cmd, cwd=str(cand), capture_output=True, text=True)
    m = re.search(r"PAIRED external delta over (\d+) shared slots:\s*"
                  r"([-+]?[\d.]+) Elo\s*95% \[([-+]?[\d.]+),\s*([-+]?[\d.]+)\]",
                  r.stdout)
    if not m:
        sys.stderr.write(r.stdout[-1200:] + r.stderr[-400:])
        raise RuntimeError(f"could not parse abgate output for {anchor}")
    n = int(m.group(1))
    elo = float(m.group(2))
    se = (float(m.group(4)) - float(m.group(3))) / (2 * 1.96)
    return n, elo, se


def run_anchor(cand, base, anchor, slots, bsize, movetime, book, conc, abandon):
    """Returns (elo, se, n, abandoned)."""
    done = 0
    num = 0.0
    den = 0.0
    off = 0
    while done < slots:
        want = min(bsize, slots - done)
        n, elo, se = batch(cand, base, anchor, off, want, movetime, book, conc)
        off = (off + 991) % 1000
        w = 1.0 / max(se * se, 1e-9)
        num += elo * w
        den += w
        done += n
        pooled = num / den
        pse = math.sqrt(1.0 / den)
        print(f"    {anchor}  {done:5d} slots  {pooled:+7.1f} +/-{1.96*pse:5.1f} Elo",
              flush=True)
        # abandon only when the UPPER bound is still below zero: a decisive
        # rejection, not merely a negative point estimate
        if pooled + 1.96 * pse < 0 and pooled < abandon:
            print(f"    ABANDON: {anchor} decisively negative")
            return pooled, pse, done, True
    return num / den, math.sqrt(1.0 / den), done, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("baseline")
    ap.add_argument("--anchors", default="stockfish:2800,stockfish:2900")
    ap.add_argument("--slots", type=int, default=600)
    ap.add_argument("--batch", type=int, default=200)
    ap.add_argument("--movetime", type=float, default=0.3)
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--book", default=None)
    ap.add_argument("--abandon", type=float, default=-15.0)
    a = ap.parse_args()

    print(f"gate: {a.candidate}\n  vs  {a.baseline}")
    print(f"  anchors {a.anchors}, up to {a.slots} slots each, "
          f"abandon below {a.abandon} Elo")
    if a.book:
        print(f"  book {a.book}  (phase-specific: Elo here is INFLATED by ~1/f, "
              f"use for DIRECTION only)")
    print()

    results = []
    for anchor in a.anchors.split(","):
        elo, se, n, gone = run_anchor(a.candidate, a.baseline, anchor, a.slots,
                                      a.batch, a.movetime, a.book,
                                      a.concurrency, a.abandon)
        results.append((anchor, elo, se, n))
        if gone:
            print("\nVERDICT: REJECT (anchor abandoned; second anchor skipped)")
            return

    print("\n" + "=" * 62)
    for anchor, elo, se, n in results:
        print(f"  {anchor:20s} {elo:+7.1f} +/-{1.96*se:5.1f} Elo  ({n} slots)")
    ok = all(e > 0 for _a, e, _s, _n in results)
    print("=" * 62)
    print("VERDICT: both anchors positive -- eligible to merge" if ok
          else "VERDICT: REJECT (rule is both anchors positive)")


if __name__ == "__main__":
    main()

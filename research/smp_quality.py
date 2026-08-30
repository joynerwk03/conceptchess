"""Does 16-thread search produce better MOVES, or only more depth?

Every gate in this project runs at CC_THREADS=1; the rating is quoted at 16.
CLAUDE.md already warns that 16-thread faults are invisible to gating -- that is
how a missing ply cap survived every gate and then killed a rating run with
SIGSEGV. Depth scaling at 16 threads has been measured (13.40 -> 15.47 plies from
1 to 16). MOVE QUALITY at 16 threads never has.

This matters more after the verification result. Two changes gated positive at 1
thread and then measured a fifth of that on a sharper instrument. If Lazy SMP
also degrades quality per unit of time, then 1-thread gating is systematically
optimistic about what transfers to the configuration the engine is rated in, and
that would be a second reason those numbers did not hold.

Method: same binary, same positions, same wall-clock per move, only CC_THREADS
differs. Score each engine's move against the cached SF11 MultiPV referee table
and report the share losing more than 20/50/100cp -- the calibrated statistic,
never the mean, because mate scores put the mean's standard error at 89.6.

At equal TIME, 16 threads searches deeper, so it should be strictly BETTER. If it
is equal or worse, Lazy SMP is wasting the extra cores and the rating
configuration is not the strongest one available.

Fixed time is non-deterministic, so passes are INTERLEAVED and reversed and each
config is run twice; read nothing smaller than the spread between its own passes.

Usage: smp_quality.py <reftable.jsonl> <movetime> [threads_csv]
"""
import json
import sys
from pathlib import Path

import chess

ROOT = Path("/home/joynerwk03/mission-control/projects/conceptchess")
sys.path.insert(0, str(ROOT))

from engine.engine import Engine   # noqa: E402
from engine import core            # noqa: E402

CLAMP = 300


def run(fens, ref, movetime, threads):
    core.set_threads(threads)
    losses = []
    depth = 0.0
    for f in fens:
        b = chess.Board(f)
        r = Engine(use_book=False, use_tablebase=False).best_move(b, movetime=movetime)
        depth += getattr(r, "depth", 0) or 0
        row = ref[f]
        tab = row["moves"]
        uci = str(r.move)
        best = tab[row["best"]]
        got = tab[uci] if uci in tab else min(tab.values())
        losses.append(min(CLAMP, max(0, best - got)))
    n = len(losses)
    return {
        "mean": sum(losses) / n,
        "gt20": 100 * sum(x > 20 for x in losses) / n,
        "gt50": 100 * sum(x > 50 for x in losses) / n,
        "depth": depth / n,
    }


def main():
    assert core.HAS_CORE, "REFUSING TO PROBE: no compiled core"
    ref = {}
    for ln in open(sys.argv[1]):
        if ln.strip():
            r = json.loads(ln)
            ref[r["fen"]] = r
    movetime = float(sys.argv[2])
    threads = [int(x) for x in (sys.argv[3] if len(sys.argv) > 3 else "1,16").split(",")]
    fens = list(ref)
    print(f"{len(fens)} positions, movetime {movetime}s, threads {threads}\n")

    results = {t: [] for t in threads}
    for p in range(2):
        order = threads if p % 2 == 0 else list(reversed(threads))
        for t in order:
            r = run(fens, ref, movetime, t)
            results[t].append(r)
            print(f"  pass {p+1}  T={t:<3} depth {r['depth']:5.2f}  "
                  f">20cp {r['gt20']:5.1f}%  >50cp {r['gt50']:5.1f}%  "
                  f"mean {r['mean']:6.2f}cp", flush=True)

    print(f"\n{'threads':>8}{'depth':>8}{'>20cp':>9}{'>50cp':>9}{'mean':>9}")
    for t in threads:
        rs = results[t]
        print(f"{t:>8}{sum(x['depth'] for x in rs)/len(rs):>8.2f}"
              f"{sum(x['gt20'] for x in rs)/len(rs):>8.1f}%"
              f"{sum(x['gt50'] for x in rs)/len(rs):>8.1f}%"
              f"{sum(x['mean'] for x in rs)/len(rs):>9.2f}")
    if len(threads) == 2:
        a, b = threads
        da = sum(x["gt20"] for x in results[a]) / len(results[a])
        db = sum(x["gt20"] for x in results[b]) / len(results[b])
        spread = max(abs(x["gt20"] - y["gt20"])
                     for x in results[a] for y in results[a])
        print(f"\nT={b} vs T={a}: blunder rate {db-da:+.2f} points "
              f"(within-config spread {spread:.2f})")
        print("  more threads = better moves" if db < da
              else "  *** more threads did NOT improve move quality ***")


if __name__ == "__main__":
    main()

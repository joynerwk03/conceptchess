"""Build an unbalanced ENDGAME opening book, so phase-specific changes are measurable.

The problem this solves, stated as arithmetic. Measured resolution here is
se ~ 350/sqrt(N) Elo, so resolving an effect E at 95% needs N > (686/E)^2. A
change worth +8 Elo across all games therefore needs ~7,350 slots -- days. But
if it only acts in the ~20% of games that reach the relevant phase, then WITHIN
those games it is worth ~+40, which needs ~294 slots. Twenty-five times fewer.

That is not a hypothetical. Contempt, the KPvK bitbase and 50-move discounting
are all endgame mechanisms, and all three measured at the edge of noise with
intervals containing zero. Three ambiguous results in a row is not three
coincidences; it is the signal being diluted by the 80% of games where the
mechanism never fires.

Selection follows UHO philosophy, applied to endgames: positions that are
UNBALANCED but not decided, so games are sharp and decisive rather than drawn,
which is where the resolution comes from.

  pieces      6..12 total, so the search actually reaches tablebase-relevant and
              pawn-ending territory within a few plies
  |sf score|  50..300cp, using the SF11 depth-10 labels already computed by
              research/relabel.py -- unbalanced enough to be decisive, not so
              unbalanced that the result is fixed regardless of the engine
  dedupe      by position (first four FEN fields), since this data is self-play
              sampled every few plies and adjacent entries are near-identical

CAVEAT, and it decides how results may be used. Elo measured from these starts
is INFLATED by roughly 1/f against real games, because the games that would have
carried no signal are gone. So this is a high-power SCREEN and direction test,
not a merge magnitude. Merge on direction plus mechanism; quote real-game Elo
only from ordinary gates or the rating run.

Usage: make_endgame_book.py <labelled.jsonl> <out.epd> [count]
"""
import json
import sys


def piece_count(fen_board):
    return sum(1 for c in fen_board if c.isalpha())


def main():
    src, out = sys.argv[1], sys.argv[2]
    want = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

    seen = set()
    picked = []
    scanned = 0
    for ln in open(src):
        if not ln.strip():
            continue
        scanned += 1
        d = json.loads(ln)
        fen = d["fen"]
        parts = fen.split()
        n = piece_count(parts[0])
        if not (6 <= n <= 12):
            continue
        sf = abs(d.get("sf", 0))
        if not (50 <= sf <= 300):
            continue
        key = " ".join(parts[:4])
        if key in seen:
            continue
        seen.add(key)
        picked.append((fen, n, d["sf"]))

    print(f"scanned {scanned:,}; {len(picked):,} candidates after filters")
    if not picked:
        raise SystemExit("no positions matched -- widen the filters")

    # spread the sample across the piece-count range rather than taking the
    # first N, which would be dominated by whatever the file happens to open with
    picked.sort(key=lambda x: (x[1], abs(x[2])))
    step = max(1, len(picked) // want)
    sel = picked[::step][:want]

    with open(out, "w") as fh:
        for fen, _n, _s in sel:
            fh.write(fen + "\n")

    hist = {}
    for _f, n, _s in sel:
        hist[n] = hist.get(n, 0) + 1
    print(f"wrote {len(sel):,} positions -> {out}")
    print("piece-count distribution:")
    for n in sorted(hist):
        print(f"  {n:2d} pieces  {hist[n]:5d}")


if __name__ == "__main__":
    main()

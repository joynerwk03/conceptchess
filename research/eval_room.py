"""How much room is left in the STATIC evaluation, and WHERE is it?

Nine consecutive hand-picked knowledge bundles measured ~zero. The conclusion
drawn from that was "the knowledge seam is closed". That conclusion does not
follow. What is closed is *guessing*: nine terms chosen by chess intuition, each
screened after it was written. Nothing so far has ever measured where this
evaluation is actually wrong.

This does, by referencing a much stronger static evaluator on the same positions
and the same labels. Two questions, in order:

  1. **Is there room at all?** Score every position with this engine's eval and
     with Stockfish's `eval`, then compare their decisive-game outcome losses,
     each at its OWN best K. If a far stronger evaluator predicts game results
     barely better than this one, then static evaluation is genuinely finished
     and the remaining Elo is in speed. If it predicts them much better, the room
     is real and quantified.

  2. **Where is the room?** Partition the positions by interpretable features --
     phase, material imbalance, pawn count, queens on or off, opposite bishops,
     king exposure -- and compute the loss gap inside each bucket. Buckets are
     ranked by TOTAL recoverable loss (n x gap), not by relative gap, because a
     30% deficit on 1% of positions is worth less than a 3% deficit on half of
     them.

The ranking is the deliverable: it says which term to write next, instead of me
guessing a tenth time.

Two things this is NOT. It is not distillation -- no Stockfish number is fitted
to, and nothing it produces enters the evaluation. It is a measuring instrument,
the same role Stockfish already plays as the rating anchor and the suite miner.
And it is not an upper bound on interpretable strength; Stockfish's eval here is
an NNUE, so it marks where a *stronger function of the same board* exists, which
is what "is there room" means.

    PYTHONPATH=. .venv/bin/python research/eval_room.py --n 80000 --workers 12
"""
import argparse
import json
import multiprocessing as mp
import random
import re
import subprocess

import chess
import numpy as np

from research.texel import ROOT

KGRID = [0.24, 0.28, 0.32, 0.36, 0.40, 0.44, 0.48, 0.52, 0.56, 0.60, 0.70, 0.85]
# SF12+ prints "Final evaluation  +0.55 (white side)"; SF11 and earlier print
# "Total evaluation: -0.35 (white side)".
FINAL = re.compile(r"(?:Final|Total) evaluation:?\s+([+-]?\d+\.\d+)")
PV = {chess.PAWN: 100, chess.KNIGHT: 325, chess.BISHOP: 335,
      chess.ROOK: 500, chess.QUEEN: 975}


def sig(e, k):
    return 1.0 / (1.0 + np.exp(-(np.log(10.0) / (k * 400.0)) * e))


def best_loss(e, res):
    """Outcome loss at this evaluator's own best K -- scale-invariant."""
    return min(float(np.mean((sig(e, k) - res) ** 2)) for k in KGRID)


# ------------------------------------------------------------------ scoring
def sf_chunk(args):
    """Stockfish's static eval, in centipawns from White. One process, many
    positions -- the cost here is IPC and parsing the board table it prints."""
    fens, binary = args
    p = subprocess.Popen([binary], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, text=True, bufsize=1)
    p.stdin.write("uci\n")
    p.stdin.flush()
    while "uciok" not in (p.stdout.readline() or "uciok"):
        pass
    out = []
    for f in fens:
        # `isready` is a SYNC BARRIER, and it is why this is written this way.
        # Breaking out of the read loop as soon as the wanted line appears
        # leaves the rest of `eval`'s output sitting in the pipe, and every
        # later position then reads one evaluation behind -- which is silent,
        # since the values still parse. Draining to `readyok` every time keeps
        # the stream aligned no matter what the engine chose to print, and
        # works across Stockfish versions with different eval formats.
        p.stdin.write(f"position fen {f}\neval\nisready\n")
        p.stdin.flush()
        v = None
        while True:
            line = p.stdout.readline()
            if not line or line.startswith("readyok"):
                break
            if v is None:
                m = FINAL.search(line)          # "NNUE evaluation" cannot match
                if m:
                    v = float(m.group(1)) * 100.0
        out.append(v)
    p.stdin.write("quit\n")
    p.stdin.flush()
    p.wait(timeout=10)
    return out


def mine_chunk(fens):  # takes a plain list, not a tuple
    from engine.evaluation import evaluate
    return [evaluate(chess.Board(f)) for f in fens]


# ------------------------------------------------------------------ buckets
def features(fen):
    """Interpretable partitions. Each returns (dimension, bucket-label)."""
    b = chess.Board(fen)
    cnt = {c: {pt: len(b.pieces(pt, c)) for pt in PV} for c in (True, False)}
    npm = sum(PV[pt] * (cnt[True][pt] + cnt[False][pt])
              for pt in PV if pt != chess.PAWN)
    mat = sum(PV[pt] * (cnt[True][pt] - cnt[False][pt]) for pt in PV)
    pawns = cnt[True][chess.PAWN] + cnt[False][chess.PAWN]
    q = cnt[True][chess.QUEEN] + cnt[False][chess.QUEEN]

    f = []
    f.append(("phase", "opening" if npm >= 6000 else
              "middlegame" if npm >= 2600 else "endgame"))
    f.append(("material", "level" if abs(mat) < 80 else
              "small edge" if abs(mat) < 300 else
              "clear edge" if abs(mat) < 900 else "winning"))
    f.append(("queens", {0: "no queens", 1: "one queen"}.get(q, "both queens")))
    f.append(("pawns", "few (<=8)" if pawns <= 8 else
              "some (9-12)" if pawns <= 12 else "many (13-16)"))

    # non-material imbalance: material is close but the piece MIX differs. This
    # is the case a linear material sum cannot express, and the one Kaufman's
    # corrections exist for.
    mix = any(cnt[True][pt] != cnt[False][pt]
              for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN))
    f.append(("piece mix", "asymmetric mix, level material"
              if mix and abs(mat) < 300 else
              "asymmetric mix, material edge" if mix else "symmetric mix"))

    # bishop pair, the classic mix term
    bp = (cnt[True][chess.BISHOP] >= 2) - (cnt[False][chess.BISHOP] >= 2)
    f.append(("bishop pair", "one side has the pair" if bp else "neither/both"))

    # king exposure: a king off its back two ranks while queens are on
    ke = 0
    for c in (True, False):
        ks = b.king(c)
        if ks is None:
            continue
        rank = chess.square_rank(ks) if c else 7 - chess.square_rank(ks)
        if rank >= 2 and q:
            ke += 1
    f.append(("king exposure", "a king is out" if ke else "kings home"))

    # passed pawns -- the long-horizon feature that has paid before
    passed = 0
    for c in (True, False):
        them = b.pieces(chess.PAWN, not c)
        for sq in b.pieces(chess.PAWN, c):
            fl, r = chess.square_file(sq), chess.square_rank(sq)
            if not any(abs(chess.square_file(e) - fl) <= 1
                       and ((chess.square_rank(e) > r) if c
                            else (chess.square_rank(e) < r)) for e in them):
                passed += 1
    f.append(("passers", "none" if not passed else
              "one" if passed == 1 else "several (2+)"))
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "research/data/texel_all.jsonl"))
    ap.add_argument("--n", type=int, default=80000)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--classical", default="/home/joynerwk03/bin/stockfish11",
                    help="a pre-NNUE Stockfish -- the interpretable ceiling")
    ap.add_argument("--nnue", default="stockfish",
                    help="current Stockfish -- the total-room ceiling")
    ap.add_argument("--out", default=str(ROOT / "research/data/eval_room.json"))
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.data)]
    random.Random(20260816).shuffle(rows)
    rows = rows[:a.n]
    fens = [r["fen"] for r in rows]
    res = np.asarray([r["res"] for r in rows], dtype=float)
    print(f"{len(fens):,} positions")

    def par(fn, arg, tag):
        ch = [(fens[i::a.workers], arg) for i in range(a.workers)]
        with mp.Pool(a.workers) as pool:
            parts = pool.map(fn, ch if arg is not None
                             else [c[0] for c in ch])
        out = [None] * len(fens)
        for i, part in enumerate(parts):
            out[i::a.workers] = part
        print(f"  {tag} done")
        return out

    print("scoring with this engine...")
    mine = par(mine_chunk, None, "mine")
    refs = {}
    for tag, binary in (("sf11 (classical)", a.classical), ("sf (NNUE)", a.nnue)):
        print(f"scoring with {tag}...")
        refs[tag] = par(sf_chunk, binary, tag)

    ok = np.asarray([m is not None and all(r[i] is not None for r in refs.values())
                     for i, m in enumerate(mine)], dtype=bool)
    dec = ok & (res != 0.5)
    print(f"{int(ok.sum()):,} scored, {int(dec.sum()):,} from decisive games\n")

    E_m = np.asarray([m if m is not None else 0.0 for m in mine], dtype=float)
    E = {t: np.asarray([v if v is not None else 0.0 for v in r], dtype=float)
         for t, r in refs.items()}

    lm = best_loss(E_m[dec], res[dec])
    print("=" * 72)
    print(f"  this engine            decisive-game outcome loss  {lm:.6f}")
    for t, e in E.items():
        lt = best_loss(e[dec], res[dec])
        print(f"  {t:<22} decisive-game outcome loss  {lt:.6f}"
              f"   gap {100*(lm-lt)/lm:+6.2f}%")
    print("=" * 72)
    print("  sf11 is the INTERPRETABLE ceiling -- a classical concept sum, the\n"
          "  same architecture as this engine. The NNUE gap is the total room;\n"
          "  the sf11 gap is the part reachable without giving up the design.")

    # buckets are reported against the classical reference: that is the one
    # whose deficit this project could actually close.
    E_s = E["sf11 (classical)"]
    ls = best_loss(E_s[dec], res[dec])

    # ---------------------------------------------------------- where is it
    dims = {}
    for i, f in enumerate(fens):
        if not dec[i]:
            continue
        for dim, lab in features(f):
            dims.setdefault(dim, {}).setdefault(lab, []).append(i)

    report = {"overall": {"mine": lm, "sf": ls, "n": int(dec.sum())}, "dims": {}}
    print(f"\n{'bucket':<38}{'n':>8}{'mine':>10}{'SF':>10}{'gap':>9}{'share':>8}")
    print("-" * 83)
    total_gap = 0.0
    scored = []
    for dim, buckets in dims.items():
        for lab, idx in buckets.items():
            if len(idx) < 400:
                continue
            j = np.asarray(idx)
            bm, bs = best_loss(E_m[j], res[j]), best_loss(E_s[j], res[j])
            scored.append((len(idx) * (bm - bs), dim, lab, len(idx), bm, bs))
    # Total recoverable loss over the whole decisive set. Summing a single
    # partition breaks down when the reference is WORSE than this engine
    # overall: the total goes through zero and every "share" explodes.
    total_gap = int(dec.sum()) * (lm - ls)
    for share, dim, lab, n, bm, bs in sorted(scored, reverse=True):
        pct = (f"{100*share/total_gap:>6.0f}%" if total_gap > 1e-9 else "     -")
        print(f"{dim+': '+lab:<38}{n:>8,}{bm:>10.5f}{bs:>10.5f}"
              f"{100*(bm-bs)/bm:>8.1f}%{pct}")
        report["dims"].setdefault(dim, {})[lab] = {
            "n": n, "mine": bm, "sf": bs, "rel_gap": 100 * (bm - bs) / bm}
    print("\nshare = this bucket's contribution to the total recoverable loss,\n"
          "        as a fraction of the whole set (phase is a full partition).")

    json.dump(report, open(a.out, "w"), indent=1)
    print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()

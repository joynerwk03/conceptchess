"""Generate a KPvKP bitbase from syzygy: pawn endings, the next tractable ending after KPvK.

The full tbprobe port is 1600 lines with 51 Stockfish-internal dependencies and a
failure mode -- a subtly wrong prober returning confidently wrong scores -- that
makes it a fresh-session job. But the generate-from-syzygy approach that produced
the KPvK bitbase extends one step further than I first claimed. I ruled out
4-man endings because 4.2MB is impractical as a C array; that only rules out
EMBEDDING, not writing a binary loaded at startup.

KPvKP is the right next one. Pawn endings are common, they are where heuristic
evaluation is weakest, and the state space is bounded:
64 (wk) x 64 (bk) x 48 (wp) x 48 (bp) x 2 (stm) = 18,874,368 positions, one bit
each = 2.25MB. Correct by construction, since every bit is read from the syzygy
tables rather than from a format parser.

Storage is WIN / NOT-WIN for White. Unlike KPvK this is lossy -- White can LOSE a
pawn ending -- so the loader must treat not-win as "no information" rather than
"draw", and the search must fall through to ordinary evaluation there. Encoding
both would double the size for a signal the search can mostly find itself; the
value is in the proven wins.

Uses multiprocessing over white-king squares. Illegal positions (adjacent kings,
side-not-to-move in check, pawn on an impossible square) are skipped and left
zero, which is safe because the loader only ever trusts a set bit.
"""
import multiprocessing as mp
import pathlib
import sys

import chess
import chess.syzygy

TB = pathlib.Path.home() / "syzygy345"
NBP = 48                      # pawn squares a2..h7


def idx(stm, wk, bk, wp, bp):
    return (((stm * 64 + wk) * 64 + bk) * NBP + wp) * NBP + bp


def chunk(wk):
    """All positions for one white-king square. Returns (wk, set-bit indices)."""
    bits = []
    with chess.syzygy.open_tablebase(str(TB)) as tb:
        for bk in range(64):
            if bk == wk or chess.square_distance(wk, bk) <= 1:
                continue
            for wpi in range(NBP):
                wp = wpi + 8
                if wp in (wk, bk):
                    continue
                for bpi in range(NBP):
                    bp = bpi + 8
                    if bp in (wk, bk, wp):
                        continue
                    for stm in (0, 1):
                        b = chess.Board(None)
                        b.set_piece_at(wk, chess.Piece(chess.KING, chess.WHITE))
                        b.set_piece_at(bk, chess.Piece(chess.KING, chess.BLACK))
                        b.set_piece_at(wp, chess.Piece(chess.PAWN, chess.WHITE))
                        b.set_piece_at(bp, chess.Piece(chess.PAWN, chess.BLACK))
                        b.turn = chess.WHITE if stm == 0 else chess.BLACK
                        if not b.is_valid():
                            continue
                        try:
                            wdl = tb.probe_wdl(b)
                        except Exception:
                            continue
                        # a win for WHITE, expressed from the side to move
                        if (wdl > 0) if stm == 0 else (wdl < 0):
                            bits.append(idx(stm, wk, bk, wpi, bpi))
    return wk, bits


def main():
    out = pathlib.Path(sys.argv[1])
    nproc = min(12, mp.cpu_count())
    total_bits = 2 * 64 * 64 * NBP * NBP
    buf = bytearray((total_bits + 7) // 8)

    wins = 0
    with mp.Pool(nproc) as pool:
        for done, (wk, bits) in enumerate(pool.imap_unordered(chunk, range(64)), 1):
            for i in bits:
                buf[i >> 3] |= 1 << (i & 7)
            wins += len(bits)
            print(f"  {done}/64 king squares, {wins:,} wins so far", flush=True)

    out.write_bytes(bytes(buf))
    print(f"\nwrote {out} ({len(buf):,} bytes, {wins:,} white wins of "
          f"{total_bits:,} slots)")


if __name__ == "__main__":
    main()

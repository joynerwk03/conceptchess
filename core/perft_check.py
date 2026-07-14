"""Validate the compiled core's move generator against known perft values.

Run: sh core/build.sh && .venv/bin/python core/perft_check.py
A correct move generator reproduces these exactly; any mismatch is a movegen bug.
"""

import ctypes
from pathlib import Path

import chess

LIB = Path(__file__).parent / "libcengine.dylib"

CASES = [
    (chess.STARTING_FEN, [1, 20, 400, 8902, 197281, 4865609]),
    # Kiwipete
    ("r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
     [1, 48, 2039, 97862, 4085603]),
    # endgame with promotions/pins
    ("8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1", [1, 14, 191, 2812, 43238, 674624]),
    ("r2q1rk1/pP1p2pp/Q4n2/bbp1p3/Np6/1B3NBn/pPPP1PPP/R3K2R b KQ - 0 1",
     [1, 6, 264, 9467, 422333]),
    ("rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8", [1, 44, 1486, 62379]),
]


def main():
    lib = ctypes.CDLL(str(LIB))
    lib.c_perft.restype = ctypes.c_uint64
    lib.c_perft.argtypes = [ctypes.c_char_p, ctypes.c_int]
    ok_all = True
    for fen, expected in CASES:
        for d in range(1, len(expected)):
            got = lib.c_perft(fen.encode(), d)
            ok = got == expected[d]
            ok_all &= ok
            print(f"  [{'ok' if ok else 'FAIL'}] perft({d})={got:>9} "
                  f"exp {expected[d]:>9}  {fen[:28]}")
            if not ok:
                break
    print("ALL PERFT PASS:", ok_all)
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())

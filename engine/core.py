"""ctypes binding to the compiled core (core/libcengine.dylib).

The compiled core does move generation + search + a fast eval that is
cross-checked identical to the Python concept eval (core/eval_check.py), so
the fast search optimizes exactly what the Python explanation layer reports.
If the library is missing or won't build, HAS_CORE is False and the engine
falls back to the pure-Python search.
"""

import ctypes
import subprocess
from pathlib import Path

import chess

_CORE = Path(__file__).parent.parent / "core"
_LIB = _CORE / "libcengine.dylib"

HAS_CORE = False
_lib = None


def _load():
    global _lib, HAS_CORE
    if not _LIB.exists():
        try:
            subprocess.run(["sh", str(_CORE / "build.sh")], check=True,
                           capture_output=True)
        except Exception:
            return
    try:
        lib = ctypes.CDLL(str(_LIB))
        lib.c_search.restype = ctypes.c_int
        lib.c_search.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_double,
                                 ctypes.c_int, ctypes.c_char_p,
                                 ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_long)]
        lib.c_pv.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        lib.c_eval.restype = ctypes.c_double
        lib.c_eval.argtypes = [ctypes.c_char_p]
        _lib = lib
        HAS_CORE = True
    except Exception:
        HAS_CORE = False


_load()


def search(board, movetime=1.0, max_depth=64):
    """Return (move, score, depth, nodes, pv) using the compiled core.

    score is centipawns from the side-to-move's perspective (mate near
    +/-100000); pv is a list of chess.Move for the expected line.
    """
    start_fen = board.root().fen()
    moves = " ".join(m.uci() for m in board.move_stack)
    out = ctypes.create_string_buffer(8)
    depth = ctypes.c_int(0)
    nodes = ctypes.c_long(0)
    sc = _lib.c_search(start_fen.encode(), moves.encode(), float(movetime),
                       int(max_depth), out, ctypes.byref(depth), ctypes.byref(nodes))
    uci = out.value.decode()
    move = chess.Move.from_uci(uci) if uci else None

    pv_buf = ctypes.create_string_buffer(512)
    _lib.c_pv(start_fen.encode(), moves.encode(), pv_buf, 512)
    pv = [chess.Move.from_uci(u) for u in pv_buf.value.decode().split()] if pv_buf.value else []
    return move, sc, depth.value, nodes.value, pv


def c_eval(fen):
    """Compiled static eval of a FEN (White's perspective) — for cross-checks."""
    return _lib.c_eval(fen.encode())

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
                                 ctypes.c_double, ctypes.c_int, ctypes.c_char_p,
                                 ctypes.c_char_p, ctypes.POINTER(ctypes.c_int),
                                 ctypes.POINTER(ctypes.c_long)]
        lib.c_pv.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        lib.c_eval.restype = ctypes.c_double
        lib.c_eval.argtypes = [ctypes.c_char_p]
        lib.c_verify_hash.restype = ctypes.c_long
        lib.c_verify_hash.argtypes = [ctypes.c_char_p, ctypes.c_int]
        lib.c_verify_hash_fail_fen.restype = ctypes.c_char_p
        # Lazy-SMP thread count (default 1 = single-threaded, byte-identical).
        # Set via the CC_THREADS env var so match gates can pit N threads vs 1.
        if hasattr(lib, "c_set_threads"):
            lib.c_set_threads.argtypes = [ctypes.c_int]
            import os
            try:
                lib.c_set_threads(int(os.environ.get("CC_THREADS", "1")))
            except ValueError:
                pass
        _lib = lib
        HAS_CORE = True
    except Exception:
        HAS_CORE = False


_load()


def search(board, movetime=1.0, max_depth=64, max_time=None):
    """Return (move, score, depth, nodes, pv, second) using the compiled core.

    score is centipawns from the side-to-move's perspective (mate near
    +/-100000); pv is the expected line; second is the runner-up root move
    (chess.Move or None) for contrastive explanations.
    """
    start_fen = board.root().fen()
    moves = " ".join(m.uci() for m in board.move_stack)
    out = ctypes.create_string_buffer(8)
    second = ctypes.create_string_buffer(8)
    depth = ctypes.c_int(0)
    nodes = ctypes.c_long(0)
    sc = _lib.c_search(start_fen.encode(), moves.encode(), float(movetime),
                       float(max_time if max_time is not None else movetime),
                       int(max_depth), out, second, ctypes.byref(depth), ctypes.byref(nodes))
    uci = out.value.decode()
    move = chess.Move.from_uci(uci) if uci else None
    snd = chess.Move.from_uci(second.value.decode()) if second.value else None

    pv_buf = ctypes.create_string_buffer(512)
    _lib.c_pv(start_fen.encode(), moves.encode(), pv_buf, 512)
    pv = [chess.Move.from_uci(u) for u in pv_buf.value.decode().split()] if pv_buf.value else []
    return move, sc, depth.value, nodes.value, pv, snd


def eval_move(board, move, movetime=0.3):
    """How good is `move` for the side to move? Search the resulting position
    and report (score_for_mover_cp, line) where line starts with `move`.

    This is the atomic building block for candidate ranking, 'analyze my move',
    and the contrastive alternative — all reuse the same C search.
    """
    b = board.copy()
    b.push(move)
    reply, reply_sc, depth, nodes, reply_pv, _ = search(b, movetime)
    line = [move] + reply_pv
    return -reply_sc, line, depth


def c_eval(fen):
    """Compiled static eval of a FEN (White's perspective) — for cross-checks."""
    return _lib.c_eval(fen.encode())


def verify_hash(fen, depth):
    """Walk the perft tree from `fen` to `depth`, asserting the incrementally
    maintained Board.hash matches a from-scratch recompute at every node.
    Returns (ok, positions_checked, fail_fen)."""
    n = _lib.c_verify_hash(fen.encode(), depth)
    if n < 0:
        return False, 0, _lib.c_verify_hash_fail_fen().decode()
    return True, n, None

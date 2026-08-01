"""ctypes binding to the compiled core (core/libcengine.dylib).

The compiled core does move generation + search + a fast eval that is
cross-checked identical to the Python concept eval (core/eval_check.py), so
the fast search optimizes exactly what the Python explanation layer reports.
If the library is missing or won't build, HAS_CORE is False and the engine
falls back to the pure-Python search.
"""

import ctypes
import platform
import subprocess
from pathlib import Path

import chess

_CORE = Path(__file__).parent.parent / "core"
# macOS builds a .dylib, Linux/WSL2 a .so (see core/build.sh).
_LIBNAME = "libcengine.dylib" if platform.system() == "Darwin" else "libcengine.so"
_LIB = _CORE / _LIBNAME

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
        if hasattr(lib, "c_get_pv"):
            lib.c_get_pv.argtypes = [ctypes.c_char_p, ctypes.c_int]
        lib.c_eval.restype = ctypes.c_double
        lib.c_eval.argtypes = [ctypes.c_char_p]
        lib.c_verify_hash.restype = ctypes.c_long
        lib.c_verify_hash.argtypes = [ctypes.c_char_p, ctypes.c_int]
        lib.c_verify_hash_fail_fen.restype = ctypes.c_char_p
        # Lazy-SMP thread count (default 1 = single-threaded, byte-identical).
        # Set via the CC_THREADS env var so match gates can pit N threads vs 1.
        if hasattr(lib, "c_set_multipv"):
            lib.c_set_multipv.argtypes = [ctypes.c_int]
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


def set_threads(n):
    """Set the Lazy-SMP search thread count (1 = deterministic single-thread).

    The coach's move-verdict searches keep this at 1 for reproducibility; play
    and analysis raise it for deeper search (occasional PV nondeterminism is fine
    when you're playing or exploring, not scoring a move). No-op if no SMP."""
    if _lib is not None and hasattr(_lib, "c_set_threads"):
        _lib.c_set_threads(int(n))


def set_multipv(on):
    """Enable/disable the true 2nd-best root move (an extra full-window pass that
    excludes the best move). OFF by default so play pays nothing; the analysis
    GUI turns it on so its runner-up recommendation is real, not a move-order
    artifact. No-op if the core predates this feature."""
    if _lib is not None and hasattr(_lib, "c_set_multipv"):
        _lib.c_set_multipv(1 if on else 0)


def play_threads():
    """Full-strength default thread count: honor CC_THREADS if set, else all
    cores capped at the core's MAX_THREADS (8). Used by the UCI interface and the
    web play/analysis paths so the engine plays at full width by default. Research
    gates export CC_THREADS=1 to keep strength measurements clean single-thread."""
    import os
    env = os.environ.get("CC_THREADS")
    if env is not None:
        try:
            return max(1, int(env))
        except ValueError:
            pass
    return min(os.cpu_count() or 1, 8)


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

    # Full PV from the search's triangular PV table (never TT-truncated). Falls
    # back to the older TT-walk for a core built before c_get_pv existed.
    pv_buf = ctypes.create_string_buffer(1024)
    if hasattr(_lib, "c_get_pv"):
        _lib.c_get_pv(pv_buf, 1024)
    else:
        _lib.c_pv(start_fen.encode(), moves.encode(), pv_buf, 1024)
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

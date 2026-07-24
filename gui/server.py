"""Local web GUI server.

Run with: python -m gui.server  (then open http://localhost:8000)

Stateless API: the client sends the starting FEN + move list each request, so
the server can rebuild the full board history (needed for repetition detection).
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import chess

from engine import book as _book
from engine import core as _core
from engine.engine import Engine
from engine.explain import mate_distance, score_string
from gui import coach

STATIC = Path(__file__).parent / "static"
_engine = Engine()
_engine_lock = threading.Lock()

# The analysis board runs the engine at full width (Lazy SMP) for the deepest
# search — it's for exploring, so occasional PV nondeterminism is fine. The
# coach/play path stays single-threaded for reproducible move verdicts, so we
# raise the thread count only around an analysis search and reset it after.
ANALYSIS_THREADS = min(os.cpu_count() or 1, 8)


def build_board(payload):
    board = chess.Board(payload.get("start_fen") or chess.STARTING_FEN)
    for uci in payload.get("moves", []):
        board.push(chess.Move.from_uci(uci))
    return board


def san_history(payload, extra_uci=None):
    board = chess.Board(payload.get("start_fen") or chess.STARTING_FEN)
    sans = []
    moves = list(payload.get("moves", []))
    if extra_uci:
        moves.append(extra_uci)
    for uci in moves:
        mv = chess.Move.from_uci(uci)
        sans.append(board.san(mv))
        board.push(mv)
    return sans


def state_dict(board):
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        status = "ongoing"
        winner = None
    else:
        status = outcome.termination.name.lower()
        winner = {True: "white", False: "black", None: None}[outcome.winner]
    return {
        "fen": board.fen(),
        "turn": "white" if board.turn else "black",
        "in_check": board.is_check(),
        "legal_moves": [m.uci() for m in board.legal_moves],
        "status": status,
        "winner": winner,
    }


def analysis_step(board, max_depth, movetime, use_book):
    """One iterative-deepening step for the analysis board.

    The client calls this repeatedly with an increasing `max_depth`; the C
    core's transposition table persists across calls, so re-searching the
    shallow depths is near-free and each call effectively adds one ply. This
    gives a live-deepening analysis (depth climbing, best move refining) with
    no streaming machinery — just successive blocking searches. `movetime` is a
    per-call safety ceiling so a single very deep iteration can't hang forever.
    """
    turn_white = board.turn == chess.WHITE
    if use_book:
        mv, name = _book.lookup(board)
        if mv is not None:
            return {
                "book": True, "book_name": name,
                "best": mv.uci(), "best_san": board.san(mv), "second": None,
                "depth": 0, "nodes": 0, "score_white": None,
                "score_display": "book", "pv": [], "pv_uci": [],
                "mate": False, "done": True,
            }
    move, sc, depth, nodes, pv, second = _core.search(
        board, movetime=movetime, max_depth=max_depth)
    if move is None:
        return {"book": False, "best": None, "second": None, "depth": 0,
                "nodes": 0, "score_white": None, "score_display": "—",
                "pv": [], "pv_uci": [], "mate": False, "done": True}
    white_cp = sc if turn_white else -sc
    pv_san, tmp = [], board.copy()
    for m in pv:
        try:
            pv_san.append(tmp.san(m)); tmp.push(m)
        except Exception:
            break
    return {
        "book": False,
        "best": move.uci(), "best_san": board.san(move),
        "second": second.uci() if second else None,
        "depth": depth, "nodes": nodes,
        "score_white": round(white_cp, 1),
        "score_display": score_string(white_cp),
        "pv": pv_san, "pv_uci": [m.uci() for m in pv],
        "mate": mate_distance(sc) is not None,
        "done": mate_distance(sc) is not None,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the terminal quiet

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = (STATIC / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "bad json"}, 400)
            return

        try:
            if self.path == "/api/state":
                board = build_board(payload)
                s = state_dict(board)
                s["san_history"] = san_history(payload)
                self._json(s)
            elif self.path == "/api/eval":
                board = build_board(payload)
                breakdown = Engine.static_eval_detailed(board)
                self._json({
                    "breakdown": breakdown.as_dict(),
                    "score_display": score_string(breakdown.total),
                })
            elif self.path == "/api/engine":
                board = build_board(payload)
                movetime = float(payload.get("movetime", 1.0))
                with _engine_lock:
                    result, explanation = _engine.best_move_explained(
                        board, movetime=movetime)
                if result.move is None:
                    self._json({"error": "no legal moves", "state": state_dict(board)})
                    return
                uci = result.move.uci()
                board.push(result.move)
                s = state_dict(board)
                s["san_history"] = san_history(payload, extra_uci=uci)
                self._json({
                    "move": uci,
                    "explanation": explanation,
                    "state": s,
                })
            elif self.path == "/api/think":
                board = build_board(payload)
                max_depth = int(payload.get("max_depth", 64))
                movetime = float(payload.get("movetime", 20.0))
                use_book = bool(payload.get("book", False))
                with _engine_lock:
                    _core.set_threads(ANALYSIS_THREADS)
                    try:
                        res = analysis_step(board, max_depth, movetime, use_book)
                    finally:
                        _core.set_threads(1)   # keep the coach path deterministic
                res["threads"] = ANALYSIS_THREADS
                self._json(res)
            elif self.path == "/api/candidates":
                board = build_board(payload)
                mt = float(payload.get("movetime", 0.12))
                with _engine_lock:
                    self._json({"candidates": coach.candidates(board, movetime=mt)})
            elif self.path == "/api/analyze":
                board = build_board(payload)
                with _engine_lock:
                    self._json(coach.analyze_move(board, payload["move"],
                                                  movetime=float(payload.get("movetime", 0.4))))
            elif self.path == "/api/overlays":
                board = build_board(payload)
                self._json({"overlays": coach.overlays(board)})
            elif self.path == "/api/review":
                with _engine_lock:
                    self._json({"review": coach.review(
                        payload.get("start_fen"), payload.get("moves", []),
                        movetime=float(payload.get("movetime", 0.18)))})
            elif self.path == "/api/glossary":
                self._json({"glossary": coach.GLOSSARY})
            else:
                self.send_error(404)
        except Exception as e:  # surface errors to the client during development
            self._json({"error": f"{type(e).__name__}: {e}"}, 500)


def main(port=8000):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"ConceptChess GUI running at http://localhost:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

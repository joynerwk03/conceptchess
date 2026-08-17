"""Syzygy endgame tablebases — ground truth for positions with few pieces.

Why this exists
---------------
`research.convert` measured what a match gate never could: of eight endings with
a known theoretical result, the engine reached only five of them — a won K+B+B
vs K was drawn by the fifty-move rule, and the wins it did find took ~6 moves
longer than necessary. Against a strong opponent these positions barely occur, so
every Elo number the project has ever measured was blind to it; but a drawn won
game is a whole point, and the analysis board reaches these endings constantly.

(The same benchmark also cleared the engine of a charge: two K+P vs K positions
it "failed to win" are theoretical DRAWS. Ground truth now comes from the
tablebase rather than hand-written expectations, for exactly that reason.)

Below six pieces the right answer is not an estimate at all: it is known. A
tablebase gives perfect play by construction, in exactly the positions where the
hand-crafted eval is weakest and the search horizon helps least.

Interpretability
----------------
This deliberately does NOT feed the concept sum. `evaluate()` still equals
`evaluate_detailed().total`, the C eval still mirrors the Python eval, and the
search still maximises the number the breakdown displays — all of the project's
invariants are untouched, because the tablebase is consulted only at the ROOT and
reported as its own labelled authority:

    Tablebase: win, mate in 12 (DTZ 8)

That is arguably *more* interpretable than an evaluation, since it is ground
truth rather than a weighted guess, and it is clearly not claiming to be a
concept. The engine says "I know this position" rather than "I think this".

DTZ vs WDL
----------
WDL says win/draw/loss. DTZ says how many plies until the next irreversible move
(capture or pawn push) under optimal play. Picking a move by WDL alone is what
produces the classic shuffling: every winning move looks equally winning. DTZ is
what actually makes progress, and it is also what keeps the fifty-move rule
honest — so both table sets are used.
"""

import os
from pathlib import Path

import chess

try:
    import chess.syzygy
    _HAVE_SYZYGY = True
except ImportError:                                   # pragma: no cover
    _HAVE_SYZYGY = False

# Default location; override with CC_SYZYGY_PATH.
DEFAULT_PATH = Path.home() / "syzygy345"

_tb = None
_tried = False
_max_pieces = 0


def _open():
    """Open the tablebase once, lazily. Absent tables are not an error — the
    engine simply carries on with its own evaluation."""
    global _tb, _tried, _max_pieces
    if _tried:
        return _tb
    _tried = True
    if not _HAVE_SYZYGY:
        return None
    path = os.environ.get("CC_SYZYGY_PATH") or str(DEFAULT_PATH)
    if not Path(path).is_dir():
        return None
    try:
        _tb = chess.syzygy.open_tablebase(path)
    except Exception:
        return None
    # Work out the largest position the downloaded set actually covers, so we
    # never probe a table that is not there.
    names = {p.stem for p in Path(path).glob("*.rtbw")}
    _max_pieces = max((len(n.replace("v", "")) for n in names), default=0)
    return _tb


def available():
    return _open() is not None


def max_pieces():
    _open()
    return _max_pieces


def probe(board):
    """-> (wdl, dtz) from the side-to-move's point of view, or None.

    wdl: 2 win, 1 cursed win, 0 draw, -1 blessed loss, -2 loss.
    """
    tb = _open()
    if tb is None or chess.popcount(board.occupied) > _max_pieces:
        return None
    if board.castling_rights:            # Syzygy assumes castling is impossible
        return None
    try:
        return tb.probe_wdl(board), tb.probe_dtz(board)
    except (chess.syzygy.MissingTableError, KeyError, IndexError, ValueError):
        return None


def best_move(board):
    """The tablebase-optimal move, or None if this position is not covered.

    Ranks by (win/draw/loss first, then fastest progress). Choosing by WDL alone
    is what makes engines shuffle in won endings: every winning move looks the
    same. DTZ breaks that tie by preferring the move that gets to the next
    irreversible step soonest, which is what actually converts.

    Returns (move, wdl, dtz, mate_hint) or None.
    """
    tb = _open()
    if tb is None:
        return None
    if chess.popcount(board.occupied) > _max_pieces or board.castling_rights:
        return None
    if probe(board) is None:
        return None

    best = None
    for move in board.legal_moves:
        # Computed before the push: asking board.is_capture(move) after
        # board.push(move) interrogates the child, not the move.
        zeroing = 1 if board.is_zeroing(move) else 0
        board.push(move)
        try:
            if board.is_checkmate():
                board.pop()
                return move, 2, 0, "mate"
            if board.is_stalemate() or board.is_insufficient_material():
                key = (0, 0, 0, 0)
                child = None
            else:
                child = probe(board)
                if child is None:
                    board.pop()
                    continue
                wdl_them, dtz_them = child
                # Negate: the child's value is from the opponent's point of view.
                wdl_us = -wdl_them
                # Never walk into a repetition while winning. DTZ does not
                # strictly decrease every move, so picking purely by DTZ lets the
                # winning side oscillate between equally-rated moves -- which is
                # exactly how research.convert saw a won K+Q vs K+R drawn by
                # threefold repetition. When losing, repetition is a resource.
                repeats = board.is_repetition(2)
                anti_rep = (0 if repeats else 1) if wdl_us > 0 else \
                           ((1 if repeats else 0) if wdl_us < 0 else 0)
                # Among wins prefer the SMALLEST |dtz| (fastest progress); among
                # losses prefer the LARGEST (resist longest).
                progress = -abs(dtz_them) if wdl_us > 0 else \
                           (abs(dtz_them) if wdl_us < 0 else 0)
                # A move that resets the fifty-move counter is real progress,
                # and it must outrank raw DTZ rather than merely break its ties.
                # DTZ counts plies to the next irreversible move, so a quiet move
                # that leaves the position one ply from zeroing scores BETTER on
                # DTZ than the zeroing move itself, which resets the count and
                # reports the distance to the next one. Ranking DTZ first
                # therefore prefers being about to make progress over making it,
                # and the winning side shuffles until the fifty-move rule ends
                # the game -- which is exactly what KPP vs KP did, for 102 plies.
                # wdl_us is still first in the key, so only moves that preserve
                # the win are candidates at all.
                key = (wdl_us, anti_rep, zeroing, progress)
        finally:
            if board.move_stack and board.peek() == move:
                board.pop()
        if best is None or key > best[0]:
            best = (key, move, child)

    if best is None:
        return None
    key, move, child = best
    wdl_us = key[0]
    dtz = abs(child[1]) if child else 0
    return move, wdl_us, dtz, None


def describe(board):
    """A one-line, human-readable verdict for the GUI, or None."""
    got = probe(board)
    if got is None:
        return None
    wdl, dtz = got
    if wdl == 0:
        return "tablebase: draw"
    if wdl == 2:
        return f"tablebase: win (DTZ {abs(dtz)})"
    if wdl == -2:
        return f"tablebase: loss (DTZ {abs(dtz)})"
    if wdl == 1:
        return f"tablebase: win, but drawn by the 50-move rule (DTZ {abs(dtz)})"
    return f"tablebase: loss, but saved by the 50-move rule (DTZ {abs(dtz)})"

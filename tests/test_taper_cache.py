"""The concept caches must be keyed by everything their value depends on.

PawnStructure and KingSafety cache expensive sub-results keyed on the pawn
skeleton (plus king squares). That was sound while every weight had a single
value: the cached part was genuinely phase-free. Tapering broke it -- doubled,
isolated, backward, connected, shield_gap and open_file all read the phase now,
so the same skeleton scores differently once the pieces come off.

The bug is invisible in the obvious test, because a position never collides
with itself: you only see it when a *different* position with the same pawns
and a different phase got there first. That is why 6204 sequential positions
found it and every single-position check said the eval was fine.

These tests fill W_EG themselves, so they fail on the broken caches whether or
not the shipped weights happen to be tapered today.
"""
import chess
import pytest

from engine import evaluation
from engine.evaluation import evaluate
from engine.weights import W, W_EG

# Same pawns, same king squares, different phase: full army versus a knight
# each. The skeleton is deliberately lopsided -- White's a-pawns are doubled and
# isolated and Black's king keeps its shield -- because a symmetric one makes
# every tapered term cancel between the colours and the test passes on the very
# bug it exists to catch.
MG = "rnbqkbnr/p1p2ppp/8/8/8/P7/P7/RNBQKBNR w KQkq - 0 1"
EG = "1n2k3/p1p2ppp/8/8/8/P7/P7/1N2K3 w - - 0 1"


@pytest.fixture
def tapered():
    """Give the cached terms an endgame value that differs from the middlegame."""
    injected = {
        "pawn.doubled": W["pawn.doubled"] + 40.0,
        "pawn.isolated": W["pawn.isolated"] + 40.0,
        "king.shield_gap": W["king.shield_gap"] + 40.0,
        "king.open_file": W["king.open_file"] + 40.0,
    }
    saved = {k: W_EG.get(k) for k in injected}
    W_EG.update(injected)
    evaluation.clear_caches()
    yield
    for k, v in saved.items():
        if v is None:
            W_EG.pop(k, None)
        else:
            W_EG[k] = v
    evaluation.clear_caches()


@pytest.mark.parametrize("fen,other", [(MG, EG), (EG, MG)])
def test_eval_is_independent_of_what_was_evaluated_before(tapered, fen, other):
    """Warming the cache with a same-skeleton, different-phase position must not
    change the answer."""
    evaluation.clear_caches()
    cold = evaluate(chess.Board(fen))

    evaluation.clear_caches()
    evaluate(chess.Board(other))          # same pawns, same kings, other phase
    warm = evaluate(chess.Board(fen))

    assert warm == pytest.approx(cold, abs=1e-9), (
        f"{fen} scored {warm} after {other} but {cold} on its own -- a concept "
        f"cache is keyed on less than its value depends on"
    )


def test_the_two_phases_actually_score_differently(tapered):
    """Guard the guard: if these two positions ever evaluate the same, the test
    above passes for the wrong reason and stops protecting anything."""
    evaluation.clear_caches()
    mg = evaluate(chess.Board(MG))
    evaluation.clear_caches()
    eg = evaluate(chess.Board(EG))
    assert mg != pytest.approx(eg, abs=1.0)

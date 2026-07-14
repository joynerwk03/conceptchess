"""Explanation-layer invariants: the shown numbers must be real evals."""

import chess
import pytest

from engine.engine import Engine
from engine.evaluation import evaluate


@pytest.fixture(scope="module")
def explained():
    board = chess.Board(
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R w KQkq - 6 5")
    engine = Engine()
    result, ex = engine.best_move_explained(board, movetime=1.5)
    return board, result, ex


def test_breakdowns_are_faithful(explained):
    """Displayed breakdown totals equal the actual evaluation of the
    positions they describe."""
    board, result, ex = explained
    b = board.copy()
    for san in ex["pv"]:
        b.push_san(san)
    assert ex["breakdown_after"]["total"] == pytest.approx(evaluate(b), abs=0.06)


def test_alternative_present_and_faithful(explained):
    board, result, ex = explained
    alt = ex["alternative"]
    assert alt is not None
    assert alt["move"] != ex["move"]
    b = board.copy()
    for san in alt["pv"]:
        b.push_san(san)
    assert alt["breakdown_after"]["total"] == pytest.approx(evaluate(b), abs=0.06)
    # concept diffs must be exactly best_after - alt_after, concept by concept
    best_by = {c["name"]: c["score"] for c in ex["breakdown_after"]["concepts"]}
    alt_by = {c["name"]: c["score"] for c in alt["breakdown_after"]["concepts"]}
    for d in alt["concept_diffs"]:
        assert d["diff"] == pytest.approx(best_by[d["name"]] - alt_by[d["name"]], abs=0.2)


def test_explanation_has_contrast_sentence(explained):
    _, _, ex = explained
    assert any(ex["alternative"]["move"] in s for s in ex["explanation"])


def test_no_personification(explained):
    _, _, ex = explained
    text = " ".join(ex["explanation"]).lower()
    for banned in (" i ", "i'm", "i think", "my ", "me "):
        assert banned not in f" {text} "

"""Turn search results + eval breakdowns into human-readable explanations.

The explanation compares the concept breakdown of the current position with
the position at the end of the engine's principal variation: "after the line
I expect, here is how each concept changes."
"""

import chess

from engine.evaluation import evaluate_detailed
from engine.search import MATE_THRESHOLD, MATE_SCORE


def mate_distance(score):
    """Plies to mate if score is a mate score, else None."""
    if score > MATE_THRESHOLD:
        return MATE_SCORE - score
    if score < -MATE_THRESHOLD:
        return -(MATE_SCORE + score)
    return None


def score_string(score, pov_white=True):
    """Format a side-to-move score for display from White's perspective."""
    md = mate_distance(score)
    if md is not None:
        moves = (abs(md) + 1) // 2
        return f"M{moves}" if md > 0 else f"-M{moves}"
    return f"{score / 100:+.2f}"


def explain_move(board, result):
    """Build an explanation dict for the move chosen by search.

    board: position BEFORE the engine's move.
    result: SearchResult (score is from the mover's perspective).
    Returns a JSON-friendly dict.
    """
    mover_white = board.turn == chess.WHITE
    before = evaluate_detailed(board)

    b = board.copy(stack=False)
    pv_san = []
    for mv in result.pv:
        pv_san.append(b.san(mv))
        b.push(mv)
    after = evaluate_detailed(b)

    # Per-concept deltas over the expected line, from White's perspective.
    before_by = {c.name: c for c in before.concepts}
    deltas = []
    for c in after.concepts:
        d = c.score - before_by[c.name].score
        deltas.append({
            "name": c.name,
            "display_name": c.display_name,
            "before": round(before_by[c.name].score, 1),
            "after": round(c.score, 1),
            "delta": round(d, 1),
        })

    sentences = _sentences(board, result, deltas, mover_white)

    white_score = result.score if mover_white else -result.score
    return {
        "move": board.san(result.move) if result.move else None,
        "uci": result.move.uci() if result.move else None,
        "score_white": round(white_score, 1),
        "score_display": score_string(white_score),
        "mate_in": mate_distance(result.score),
        "depth": result.depth,
        "nodes": result.nodes,
        "nps": result.nps,
        "time": round(result.time, 2),
        "pv": pv_san,
        "breakdown_before": before.as_dict(),
        "breakdown_after": after.as_dict(),
        "concept_deltas": deltas,
        "explanation": sentences,
    }


def _sentences(board, result, deltas, mover_white):
    """Short natural-language summary of why the move was chosen."""
    out = []
    md = mate_distance(result.score)
    if md is not None:
        if md > 0:
            out.append(f"I found a forced mate in {(md + 1) // 2}.")
        else:
            out.append(f"I'm getting mated in {(abs(md) + 1) // 2} moves; "
                       "this line holds out longest.")
        return out

    sign = 1 if mover_white else -1
    gains, losses = [], []
    for d in deltas:
        my_delta = sign * d["delta"]
        if my_delta >= 8:
            gains.append((d["display_name"], my_delta))
        elif my_delta <= -8:
            losses.append((d["display_name"], my_delta))
    gains.sort(key=lambda x: -x[1])
    losses.sort(key=lambda x: x[1])

    if gains:
        parts = ", ".join(f"{name.lower()} ({v / 100:+.2f})" for name, v in gains[:3])
        out.append(f"In the line I expect, I gain in {parts}.")
    if losses:
        parts = ", ".join(f"{name.lower()} ({v / 100:+.2f})" for name, v in losses[:3])
        out.append(f"I concede some {parts}.")
    if not gains and not losses:
        out.append("No concept changes much in the expected line; "
                   "this move keeps the position balanced.")

    white_score = result.score if mover_white else -result.score
    verdict = _verdict(white_score, mover_white)
    if verdict:
        out.append(verdict)
    return out


def _verdict(white_score, mover_white):
    my_score = white_score if mover_white else -white_score
    if my_score > 150:
        return "Overall I think I'm clearly better here."
    if my_score > 50:
        return "Overall I think I'm somewhat better."
    if my_score > -50:
        return "I consider the position roughly balanced."
    if my_score > -150:
        return "I think I'm somewhat worse, so I'm defending."
    return "I'm clearly worse and looking for counterplay."

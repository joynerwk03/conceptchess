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


def book_explanation(board, move, name):
    """Explanation dict for an opening-book move (mirrors explain_move's shape
    where the GUI needs it, but says plainly that this is book theory)."""
    breakdown = evaluate_detailed(board)
    return {
        "alternative": None,
        "move": board.san(move),
        "uci": move.uci(),
        "score_white": round(breakdown.total, 1),
        "score_display": score_string(breakdown.total),
        "mate_in": None,
        "depth": 0,
        "nodes": 0,
        "nps": 0,
        "time": 0.0,
        "pv": [board.san(move)],
        "book": True,
        "book_name": name,
        "breakdown_before": breakdown.as_dict(),
        "breakdown_after": breakdown.as_dict(),
        "concept_deltas": [],
        "explanation": [f"Book move: {name}. Playing established opening theory "
                        f"rather than calculating."],
    }


def explain_move(board, result, sub_search=None):
    """Build an explanation dict for the move chosen by search.

    board: position BEFORE the engine's move.
    result: SearchResult (score is from the mover's perspective).
    sub_search: optional callable(board)->(score, pv); when given, the
        runner-up root move gets a brief sub-search to contrast the two futures.
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

    white_score = result.score if mover_white else -result.score
    sentences = _sentences(white_score, result.score, deltas, mover_white,
                           after.total)

    alternative = None
    if sub_search is not None and len(result.root_ranking) > 1 and result.root_ranking[1]:
        alternative = _explain_alternative(board, result, after, mover_white,
                                           sub_search)
        if alternative:
            sentences.extend(alternative["contrast"])

    return {
        "alternative": alternative,
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


def _explain_alternative(board, result, best_after, mover_white, sub_search):
    """Sub-search the runner-up root move and contrast the two futures."""
    alt_move = result.root_ranking[1]
    b = board.copy(stack=False)
    alt_san = b.san(alt_move)
    b.push(alt_move)
    sub_score, sub_pv = sub_search(b)
    # sub_score is from the opponent's perspective in the child position.
    alt_score_white = -sub_score if mover_white else sub_score

    alt_pv_san = [alt_san]
    for mv in sub_pv:
        alt_pv_san.append(b.san(mv))
        b.push(mv)
    alt_after = evaluate_detailed(b)

    best_by = {c.name: c for c in best_after.concepts}
    diffs = []
    for c in alt_after.concepts:
        d = best_by[c.name].score - c.score  # positive: best move's future is better for White
        diffs.append({"name": c.name, "display_name": c.display_name,
                      "best": round(best_by[c.name].score, 1),
                      "alt": round(c.score, 1), "diff": round(d, 1)})

    best_white = result.score if mover_white else -result.score
    gap = best_white - alt_score_white  # White perspective
    mover = "White" if mover_white else "Black"
    best_san = board.san(result.move)
    sentences = []
    mover_gap = gap if mover_white else -gap
    if mover_gap < 25:
        sentences.append(f"The choice between {best_san} and {alt_san} was close "
                         f"(evaluations within {abs(gap) / 100:.2f}; the alternative "
                         f"was checked at lower depth).")
    else:
        sign = 1 if mover_white else -1
        top = sorted((d for d in diffs
                      if d["name"] != "tempo" and sign * d["diff"] >= 10),
                     key=lambda d: -sign * d["diff"])[:3]
        if top:
            parts = ", ".join(f"{d['display_name'].lower()} ({d['diff'] / 100:+.2f})"
                              for d in top)
            sentences.append(f"{best_san} was preferred over {alt_san}: the line "
                             f"after {alt_san} is worse for {mover} mainly in {parts} "
                             f"(values from White's perspective).")
        else:
            sentences.append(f"{best_san} was preferred over {alt_san} "
                             f"({gap / 100:+.2f} difference in the expected lines).")

    return {
        "move": alt_san,
        "uci": alt_move.uci(),
        "score_white": round(alt_score_white, 1),
        "score_display": score_string(alt_score_white),
        "pv": alt_pv_san,
        "breakdown_after": alt_after.as_dict(),
        "concept_diffs": diffs,
        "contrast": sentences,
    }


def _sentences(white_score, stm_score, deltas, mover_white, static_after_total):
    """Neutral analytical summary. All values are from White's perspective."""
    out = []
    md = mate_distance(stm_score)
    if md is not None:
        winner_is_mover = md > 0
        winner = "White" if (winner_is_mover == mover_white) else "Black"
        out.append(f"Forced mate in {(abs(md) + 1) // 2} for {winner}.")
        return out

    out.append(_verdict(white_score))

    # Main factors: largest concept scores at the end of the expected line.
    mains = sorted((d for d in deltas if abs(d["after"]) >= 25),
                   key=lambda d: -abs(d["after"]))[:3]
    if mains:
        parts = ", ".join(
            f"{d['display_name'].lower()} {d['after'] / 100:+.2f}" for d in mains)
        out.append(f"Main factors (end of expected line): {parts}.")

    # Largest shifts caused by the expected line. Tempo is excluded: it just
    # flips with the side to move and carries no instructive signal here.
    shifts = sorted((d for d in deltas
                     if d["name"] != "tempo" and abs(d["delta"]) >= 15),
                    key=lambda d: -abs(d["delta"]))[:3]
    if shifts:
        parts = ", ".join(
            f"{d['display_name'].lower()} {d['delta'] / 100:+.2f}" for d in shifts)
        out.append(f"Biggest changes over this line: {parts} "
                   "(positive favors White).")

    # Honesty check: the search score comes from quiescence beyond the PV, so
    # it can differ from the static breakdown at the PV's end. Flag it when
    # the gap is material, instead of letting the chart silently disagree.
    residual = white_score - static_after_total
    if abs(residual) > 60:
        out.append(f"Note: unresolved captures/checks beyond the shown line "
                   f"account for a further {residual / 100:+.2f}.")
    return out


def _verdict(white_score):
    ws = white_score
    s = f"{ws / 100:+.2f}"
    if ws > 300:
        return f"White has a winning advantage ({s})."
    if ws > 120:
        return f"White is clearly better ({s})."
    if ws > 40:
        return f"White is slightly better ({s})."
    if ws >= -40:
        return f"The position is roughly equal ({s})."
    if ws >= -120:
        return f"Black is slightly better ({s})."
    if ws >= -300:
        return f"Black is clearly better ({s})."
    return f"Black has a winning advantage ({s})."

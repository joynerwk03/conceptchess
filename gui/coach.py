"""Coaching analysis for the learning GUI.

Everything here turns the engine's concept eval into teaching: ranked
candidate moves with reasons, verdicts on the human's move, board highlights
for the concepts that matter, and post-game blunder review. All of it reuses
the compiled search (core.eval_move) and the interpretable concept breakdown
(evaluate_detailed), so every number shown is a real evaluation.
"""

import chess

from engine import core
from engine.evaluation import evaluate_detailed
from engine.explain import score_string, mate_distance

PIECE_VALUE = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
               chess.ROOK: 5, chess.QUEEN: 9}


def classify(loss_cp):
    """Verdict for how far a move falls below the best, in centipawns."""
    if loss_cp < 15:
        return "best", "v-best", "the top move"
    if loss_cp < 50:
        return "good", "v-good", "a good move"
    if loss_cp < 100:
        return "inaccuracy", "v-inacc", "an inaccuracy"
    if loss_cp < 250:
        return "mistake", "v-mist", "a mistake"
    return "blunder", "v-blun", "a blunder"


def _mover_cp(score_stm, mover_white):
    """A side-to-move score, expressed from the mover's perspective (already
    is), just clamped for display sanity."""
    return score_stm


def _concept_reasons(board, line, top=2):
    """Given a line (list of moves) from `board`, describe the biggest concept
    changes it causes, from the moving side's perspective. Returns list of
    {name, display_name, delta} sorted by |delta|."""
    mover_white = board.turn == chess.WHITE
    before = {c.name: c for c in evaluate_detailed(board).concepts}
    b = board.copy()
    for m in line:
        b.push(m)
    after = evaluate_detailed(b)
    sign = 1 if mover_white else -1
    reasons = []
    for c in after.concepts:
        if c.name == "tempo":
            continue
        d = sign * (c.score - before[c.name].score)
        if abs(d) >= 8:
            reasons.append({"name": c.name, "display_name": c.display_name,
                            "delta": round(d, 1)})
    reasons.sort(key=lambda r: -abs(r["delta"]))
    return reasons[:top]


def candidates(board, movetime=0.12, k=5):
    """Rank the legal moves by the compiled search and attach a concept reason
    to each. Returns the top k as {san, uci, score_display, cp, reasons}."""
    mover_white = board.turn == chess.WHITE
    scored = []
    for mv in board.legal_moves:
        cp, line, _ = core.eval_move(board, mv, movetime)
        scored.append((cp, mv, line))
    scored.sort(key=lambda t: -t[0])
    best_cp = scored[0][0] if scored else 0
    out = []
    for cp, mv, line in scored[:k]:
        white_cp = cp if mover_white else -cp
        out.append({
            "san": board.san(mv),
            "uci": mv.uci(),
            "cp": round(cp, 0),
            "loss": round(best_cp - cp, 0),
            "score_display": score_string(white_cp),
            "reasons": _concept_reasons(board, line[:4]),
            "line": _san_line(board, line[:5]),
        })
    return out


def _san_line(board, line):
    b = board.copy()
    out = []
    for m in line:
        out.append(b.san(m))
        b.push(m)
    return out


def analyze_move(board, user_uci, movetime=0.4):
    """Compare the human's move to the engine's best, in concept terms.

    Returns a verdict, the eval of each, the better move if any, and the
    per-concept difference between the two futures.
    """
    user_move = chess.Move.from_uci(user_uci)
    if user_move not in board.legal_moves:
        return {"error": "illegal move"}
    mover_white = board.turn == chess.WHITE

    best_move, best_stm, _, _, best_pv, _ = core.search(board, movetime)
    user_cp, user_line, _ = core.eval_move(board, user_move, movetime)

    loss = max(0, best_stm - user_cp)  # cp the human's move gives up
    label, cls, phrase = classify(loss)
    is_best = user_move == best_move or loss < 15

    # concept contrast: best future vs the human's future (White perspective).
    # core.search's PV already starts with best_move.
    best_line = best_pv if best_pv else [best_move]
    best_after = {c.name: c for c in _line_end_breakdown(board, best_line)}
    user_after = _line_end_breakdown(board, user_line)
    diffs = []
    sign = 1 if mover_white else -1
    for c in user_after:
        d = best_after[c.name].score - c.score
        if abs(d) >= 8:
            diffs.append({"display_name": c.display_name,
                          "delta_mover": round(sign * d, 1)})
    diffs.sort(key=lambda x: -abs(x["delta_mover"]))

    sentences = []
    user_san = board.san(user_move)
    best_san = board.san(best_move)
    if is_best:
        sentences.append(f"{user_san} is {phrase} — well played.")
    else:
        sentences.append(f"{user_san} is {phrase}; it gives up "
                         f"{loss / 100:.2f} versus {best_san}.")
        worse = [d for d in diffs if d["delta_mover"] > 0][:2]
        if worse:
            parts = ", ".join(f"{d['display_name'].lower()} "
                              f"({-d['delta_mover'] / 100:+.2f})" for d in worse)
            sentences.append(f"Compared with {best_san}, your move ends up worse in "
                             f"{parts}.")
    return {
        "verdict": label, "verdict_class": cls,
        "user_san": user_san, "best_san": best_san,
        "user_score": score_string(user_cp if mover_white else -user_cp),
        "best_score": score_string(best_stm if mover_white else -best_stm),
        "loss": round(loss, 0),
        "is_best": is_best,
        "best_line": _san_line(board, best_line[:5]),
        "diffs": diffs[:3],
        "sentences": sentences,
    }


def _line_end_breakdown(board, line):
    b = board.copy()
    for m in line:
        if m in b.legal_moves:
            b.push(m)
    return evaluate_detailed(b).concepts


def overlays(board):
    """Board highlights that make concepts concrete for the learner:
    hanging pieces (both sides), a king under real attack, and passed pawns.
    Returns {square_name: {kind, label}}."""
    marks = {}
    stm = board.turn
    for color in (chess.WHITE, chess.BLACK):
        for sq in board.pieces(chess.PAWN, color):
            if _is_passed(board, sq, color):
                marks[chess.square_name(sq)] = {
                    "kind": "passed",
                    "label": f"Passed {'white' if color else 'black'} pawn"}
    # hanging pieces: attacked by the enemy and not defended
    for color in (chess.WHITE, chess.BLACK):
        for pt in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN):
            for sq in board.pieces(pt, color):
                if board.is_attacked_by(not color, sq) and not board.is_attacked_by(color, sq):
                    yours = color == stm
                    marks[chess.square_name(sq)] = {
                        "kind": "hang_you" if yours else "hang_them",
                        "label": (f"Your {chess.piece_name(pt)} is hanging"
                                  if yours else
                                  f"Undefended {chess.piece_name(pt)} — you can win it")}
    # king under attack (>=2 attackers on the king zone)
    for color in (chess.WHITE, chess.BLACK):
        ksq = board.king(color)
        if ksq is None:
            continue
        zone = chess.SquareSet(chess.BB_KING_ATTACKS[ksq]) | {ksq}
        attackers = set()
        for zs in zone:
            for a in board.attackers(not color, zs):
                pt = board.piece_type_at(a)
                if pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                    attackers.add(a)
        if len(attackers) >= 2:
            name = chess.square_name(ksq)
            if name not in marks:
                marks[name] = {"kind": "king_danger",
                               "label": f"{'White' if color else 'Black'} king under attack "
                                        f"({len(attackers)} pieces)"}
    return marks


def _is_passed(board, sq, color):
    file = chess.square_file(sq)
    rank = chess.square_rank(sq)
    for f in (file - 1, file, file + 1):
        if not 0 <= f <= 7:
            continue
        for r in range(8):
            s = chess.square(f, r)
            p = board.piece_at(s)
            if p and p.piece_type == chess.PAWN and p.color != color:
                if (color == chess.WHITE and r > rank) or (color == chess.BLACK and r < rank):
                    return False
    return True


def review(start_fen, moves_uci, movetime=0.18):
    """Post-game blunder review. Replays the game; at each ply the engine's
    best eval E_i (side-to-move cp) is measured, and the loss for the move
    actually played is E_i + E_{i+1} (see LOG). Returns per-ply verdicts."""
    board = chess.Board(start_fen or chess.STARTING_FEN)
    ucis = moves_uci or []
    evals = []       # engine best eval at each position (stm perspective)
    best_moves = []
    positions = [board.copy()]
    b = board.copy()
    for u in ucis:
        b.push(chess.Move.from_uci(u))
        positions.append(b.copy())
    for pos in positions:
        if pos.is_game_over():
            evals.append(None)
            best_moves.append(None)
            continue
        mv, sc, _, _, _, _ = core.search(pos, movetime)
        evals.append(sc)
        best_moves.append(mv)

    out = []
    for i, u in enumerate(ucis):
        e_i = evals[i]
        e_next = evals[i + 1]
        if e_i is None or e_next is None:
            loss = 0
        else:
            loss = max(0, e_i + e_next)   # cp given up by the mover at ply i
        label, cls, _ = classify(loss)
        pos = positions[i]
        played_san = pos.san(chess.Move.from_uci(u))
        best_san = pos.san(best_moves[i]) if best_moves[i] else None
        white_cp = evals[i + 1]
        white_cp = (-white_cp if pos.turn == chess.WHITE else white_cp) if white_cp is not None else 0
        out.append({
            "ply": i,
            "move_no": i // 2 + 1,
            "white": pos.turn == chess.WHITE,
            "san": played_san,
            "verdict": label, "verdict_class": cls,
            "loss": round(loss, 0),
            "best_san": best_san if label in ("mistake", "blunder", "inaccuracy") else None,
            "eval_white": round(white_cp / 100, 2),
        })
    return out


GLOSSARY = [
    {"name": "material", "display_name": "Material",
     "what": "The total value of the pieces each side has (pawn 1, knight/bishop 3, rook 5, queen 9).",
     "why": "The most fundamental factor — being up a piece usually wins. Watch for hanging pieces you can win or lose."},
    {"name": "placement", "display_name": "Piece placement",
     "what": "How well each piece is placed, from piece-square tables (knights love the centre, kings hide in the corner in the middlegame).",
     "why": "A well-placed piece is worth more than a badly-placed one of the same value. Centralise your pieces."},
    {"name": "pawn_structure", "display_name": "Pawn structure",
     "what": "Doubled, isolated, and passed pawns. Passed pawns (no enemy pawn can stop them) get a bonus that grows as they advance.",
     "why": "Pawns can't move backward, so weaknesses are permanent. A passed pawn is a long-term winning asset in the endgame."},
    {"name": "king_safety", "display_name": "King safety",
     "what": "Gaps in the pawn shield in front of your king and open files pointing at it.",
     "why": "An exposed king invites attacks. Castle early and keep the pawns in front of your king intact."},
    {"name": "king_attack", "display_name": "King attack",
     "what": "How many of your pieces bear down on the squares around the enemy king, weighted by piece.",
     "why": "Concentrating pieces near the enemy king is how attacks are built. Two or more attackers is the danger threshold."},
    {"name": "mobility", "display_name": "Mobility",
     "what": "How many safe squares your pieces can move to (squares controlled by enemy pawns don't count).",
     "why": "Active pieces with many options are strong; cramped pieces are weak. Give your pieces room."},
    {"name": "activity", "display_name": "Piece activity",
     "what": "The bishop pair, and rooks on open or half-open files and on the 7th rank.",
     "why": "These are classic positional advantages — two bishops in open positions, rooks on open files dominate."},
    {"name": "threats", "display_name": "Threats",
     "what": "Enemy pieces that are attacked and undefended (hanging).",
     "why": "Free material! Always check what's hanging — for both sides — before you move."},
    {"name": "mate_drive", "display_name": "Mating drive",
     "what": "In endgames where one side has only a king, the drive to push it to the corner and bring your king up.",
     "why": "Winning K+Q or K+R vs K needs technique: box the king toward the edge, then deliver mate."},
    {"name": "tempo", "display_name": "Tempo",
     "what": "A small bonus for the side to move.",
     "why": "Having the move is a slight advantage — the initiative matters."},
]

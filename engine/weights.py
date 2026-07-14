"""All tunable evaluation weights, by name.

Single source of truth for every number in the evaluation. Concepts read
these at call time, so the autoresearch loop can tune them centrally and the
explanation path automatically stays faithful (both paths read the same W).

After mutating W at runtime (tuning), call engine.evaluation.clear_caches().
Search move-ordering values live in engine/search.py on purpose — ordering
heuristics don't have to track eval weights.
"""

W = {
    # material
    "material.pawn": 100,
    "material.knight": 320,
    "material.bishop": 330,
    "material.rook": 500,
    "material.queen": 900,
    # piece-square tables: multiplier per piece type on the (tapered) table value
    "pst.pawn": 1,
    "pst.knight": 1,
    "pst.bishop": 1,
    "pst.rook": 1,
    "pst.queen": 1,
    "pst.king": 1,
    # pawn structure
    "pawn.doubled": 15,
    "pawn.isolated": 12,
    "pawn.passed_scale": 1,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 1.5,
    "pawn.blocked_passer": 0.5,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    # king safety
    "king.shield_gap": 12,
    "king.open_file": 15,
    "kattack.scale": 2.5,   # cp per weighted attack unit on the enemy king zone
    # mobility (cp per square above/below typical)
    "mob.knight": 3.394,
    "mob.bishop": 3.507,
    "mob.rook": 2.338,
    "mob.queen": 1.169,
    # piece activity
    "act.bishop_pair": 30,
    "act.rook_open": 20,
    "act.rook_semi": 10,
    "act.rook_seventh": 20,
    # threats
    "threat.hanging": 0.6,  # fraction of the hanging piece's value
    # tempo
    "tempo": 10,
}

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
    "pst.pawn": 0.502,
    "pst.knight": 0.594,
    "pst.bishop": 0.509,
    "pst.rook": 0.502,
    "pst.queen": 1.959,
    "pst.king": 1.959,
    # pawn structure
    "pawn.doubled": 7.523,
    "pawn.isolated": 6.42,
    "pawn.passed_scale": 0.719,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 2.939,
    "pawn.blocked_passer": 0.251,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    # king safety
    "king.shield_gap": 6.018,
    "king.open_file": 29.391,
    "kattack.scale": 2.588,   # cp per weighted attack unit on the enemy king zone
    # mobility (cp per square above/below typical)
    "mob.knight": 7.41,
    "mob.bishop": 5.878,
    "mob.rook": 3.919,
    "mob.queen": 1.959,
    # piece activity
    "act.bishop_pair": 15.046,
    "act.rook_open": 37.051,
    "act.rook_semi": 19.594,
    "act.rook_seventh": 10.031,
    # tempo
    "tempo": 19.594,
}

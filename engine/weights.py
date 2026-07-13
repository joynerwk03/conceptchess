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
    "pst.pawn": 0.574,
    "pst.knight": 0.69,
    "pst.bishop": 0.61,
    "pst.rook": 0.563,
    "pst.queen": 1.728,
    "pst.king": 1.728,
    # pawn structure
    "pawn.doubled": 8.444,
    "pawn.isolated": 6.755,
    "pawn.passed_scale": 0.861,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 2.59,
    "pawn.blocked_passer": 0.281,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    # king safety
    "king.shield_gap": 6.755,
    "king.open_file": 25.908,
    "kattack.scale": 2.747,   # cp per weighted attack unit on the enemy king zone
    # mobility (cp per square above/below typical)
    "mob.knight": 5.015,
    "mob.bishop": 5.182,
    "mob.rook": 3.454,
    "mob.queen": 1.728,
    # piece activity
    "act.bishop_pair": 16.889,
    "act.rook_open": 34.544,
    "act.rook_semi": 17.273,
    "act.rook_seventh": 11.259,
    # tempo
    "tempo": 17.273,
}

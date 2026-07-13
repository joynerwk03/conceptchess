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
    "material.pawn": 86.593,
    "material.knight": 381.994,
    "material.bishop": 364.201,
    "material.rook": 488.597,
    "material.queen": 1073.136,
    # piece-square tables: multiplier per piece type on the (tapered) table value
    "pst.pawn": 0.51,
    "pst.knight": 0.537,
    "pst.bishop": 0.509,
    "pst.rook": 0.502,
    "pst.queen": 1.998,
    "pst.king": 1.998,
    # pawn structure
    "pawn.doubled": 7.523,
    "pawn.isolated": 9.938,
    "pawn.passed_scale": 1.023,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 2.998,
    "pawn.blocked_passer": 0.386,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    # king safety
    "king.shield_gap": 6.018,
    "king.open_file": 29.979,
    "kattack.scale": 2.555,   # cp per weighted attack unit on the enemy king zone
    # mobility (cp per square above/below typical)
    "mob.knight": 7.863,
    "mob.bishop": 5.996,
    "mob.rook": 3.997,
    "mob.queen": 0.762,
    # piece activity
    "act.bad_bishop": 11.914,  # per own pawn (beyond 2) on the bishop's color
    "act.bishop_pair": 28.998,
    "act.rook_open": 39.319,
    "act.rook_semi": 19.986,
    "act.rook_seventh": 10.031,
    # tempo
    "tempo": 19.986,
}

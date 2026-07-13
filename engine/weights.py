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
    "pst.pawn": 0.72,
    "pst.knight": 0.72,
    "pst.bishop": 0.75,
    "pst.rook": 0.72,
    "pst.queen": 1.367,
    "pst.king": 1.367,
    # pawn structure
    "pawn.doubled": 10.802,
    "pawn.isolated": 8.641,
    "pawn.passed_scale": 1.037,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 2.049,
    "pawn.blocked_passer": 0.36,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    # king safety
    "king.shield_gap": 8.641,
    "king.open_file": 20.498,
    "kattack.scale": 2.922,   # cp per weighted attack unit on the enemy king zone
    # mobility (cp per square above/below typical)
    "mob.knight": 3.968,
    "mob.bishop": 4.1,
    "mob.rook": 2.733,
    "mob.queen": 1.367,
    # piece activity
    "act.bishop_pair": 21.604,
    "act.rook_open": 27.331,
    "act.rook_semi": 13.666,
    "act.rook_seventh": 14.403,
    # tempo
    "tempo": 13.666,
}

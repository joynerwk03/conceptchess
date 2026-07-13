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
    "pst.pawn": 0.43,
    "pst.knight": 0.649,
    "pst.bishop": 0.439,
    "pst.rook": 0.405,
    "pst.queen": 2.361,
    "pst.king": 2.228,
    # pawn structure
    "pawn.doubled": 6.081,
    "pawn.isolated": 7.563,
    "pawn.passed_scale": 0.686,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 3.539,
    "pawn.blocked_passer": 0.202,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    # king safety
    "king.shield_gap": 4.865,
    "king.open_file": 35.404,
    "kattack.scale": 2.427,   # cp per weighted attack unit on the enemy king zone
    # mobility (cp per square above/below typical)
    "mob.knight": 6.853,
    "mob.bishop": 7.081,
    "mob.rook": 4.72,
    "mob.queen": 2.013,
    # piece activity
    "act.bishop_pair": 12.162,
    "act.rook_open": 35.235,
    "act.rook_semi": 23.604,
    "act.rook_seventh": 8.108,
    # tempo
    "tempo": 23.604,
}

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
    "pst.pawn": 0.274,
    "pst.knight": 0.662,
    "pst.bishop": 0.268,
    "pst.rook": 0.248,
    "pst.queen": 3.772,
    "pst.king": 2.14,
    # pawn structure
    "pawn.doubled": 3.716,
    "pawn.isolated": 10.753,
    "pawn.passed_scale": 0.524,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 5.653,
    "pawn.blocked_passer": 0.185,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    # king safety
    "king.shield_gap": 2.973,
    "king.open_file": 56.557,
    "kattack.scale": 1.895,   # cp per weighted attack unit on the enemy king zone
    # mobility (cp per square above/below typical)
    "mob.knight": 5.922,
    "mob.bishop": 10.671,
    "mob.rook": 7.54,
    "mob.queen": 1.307,
    # piece activity
    "act.bishop_pair": 7.432,
    "act.rook_open": 32.458,
    "act.rook_semi": 37.707,
    "act.rook_seventh": 4.955,
    # tempo
    "tempo": 28.708,
}

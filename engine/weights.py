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
    "pst.pawn": 0.252,
    "pst.knight": 0.662,
    "pst.bishop": 0.118,
    "pst.rook": 0.109,
    "pst.queen": 3.917,
    "pst.king": 2.14,
    # pawn structure
    "pawn.doubled": 1.635,
    "pawn.isolated": 12.822,
    "pawn.passed_scale": 0.37,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 8.207,
    "pawn.blocked_passer": 0.253,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    # king safety
    "king.shield_gap": 1.308,
    "king.open_file": 67.437,
    "kattack.scale": 1.574,   # cp per weighted attack unit on the enemy king zone
    # mobility (cp per square above/below typical)
    "mob.knight": 4.917,
    "mob.bishop": 10.458,
    "mob.rook": 9.915,
    "mob.queen": 1.132,
    # piece activity
    "act.bishop_pair": 3.271,
    "act.rook_open": 28.68,
    "act.rook_semi": 40.753,
    "act.rook_seventh": 2.181,
    # tempo
    "tempo": 29.282,
}

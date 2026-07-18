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
    "pst.pawn": 0.75,
    "pst.knight": 0.8,
    "pst.bishop": 1.25,
    "pst.rook": 0.95,
    "pst.queen": 0.75,
    "pst.king": 0.95,
    # pawn structure
    "pawn.doubled": 12.75,
    "pawn.isolated": 9.0,
    "pawn.passed_scale": 0.8,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 1.2,
    "pawn.blocked_passer": 0.5,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    "pawn.passer_king_dist": 5.2,  # cp per square of net king distance to the passer's front square (endgame-scaled)
    "pawn.connected_passer": 11.25,  # per passer with a friendly passer on an adjacent file
    # king safety
    "king.shield_gap": 11.4,
    "king.open_file": 11.25,
    "kattack.scale": 3.125,   # cp per weighted attack unit on the enemy king zone
    "kattack.proximity": 2,  # cp per weighted closeness unit of pieces near the enemy king (phase-scaled)
    # mobility (cp per square above/below typical)
    "mob.knight": 2.5455,
    "mob.bishop": 4.3838,
    "mob.rook": 2.9225,
    "mob.queen": 1.4613,
    # piece activity
    "act.bishop_pair": 37.5,
    "act.rook_open": 25.0,
    "act.rook_semi": 12.5,
    "act.rook_seventh": 21.0,
    # threats
    "threat.hanging": 0.075,  # fraction of the hanging piece's value
    # mating drive (bare-king endgames)
    "mate_drive.corner": 12,
    "mate_drive.king_prox": 6,
    # tempo
    "tempo": 10,
}

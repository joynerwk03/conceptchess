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
    "pst.pawn": 0.5625,
    "pst.knight": 0.85,
    "pst.bishop": 1.3125,
    "pst.rook": 0.7125,
    "pst.queen": 0.75,
    "pst.king": 0.9,
    # pawn structure
    "pawn.doubled": 15.9375,
    "pawn.isolated": 11.25,
    "pawn.passed_scale": 0.8,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 1.44,
    "pawn.blocked_passer": 0.5,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    "pawn.passer_king_dist": 6.76,  # cp per square of net king distance to the passer's front square (endgame-scaled)
    "pawn.connected_passer": 8.4375,  # per passer with a friendly passer on an adjacent file
    # king safety
    "king.shield_gap": 13.11,
    "king.open_file": 14.0625,
    "kattack.scale": 3.9062,   # cp per weighted attack unit on the enemy king zone
    "kattack.proximity": 2,  # cp per weighted closeness unit of pieces near the enemy king (phase-scaled)
    # mobility (cp per square above/below typical)
    "mob.knight": 3.1819,
    "mob.bishop": 5.4798,
    "mob.rook": 3.6531,
    "mob.queen": 1.8266,
    # piece activity
    "act.bishop_pair": 46.875,
    "act.rook_open": 21.25,
    "act.rook_semi": 15.625,
    "act.rook_seventh": 22.05,
    # threats
    "threat.hanging": 0.0562,  # fraction of the hanging piece's value
    # mating drive (bare-king endgames)
    "mate_drive.corner": 12,
    "mate_drive.king_prox": 6,
    # tempo
    "tempo": 10,
}

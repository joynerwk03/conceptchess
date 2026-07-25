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
    "pst.pawn": 0.5125,
    "pst.knight": 0.75,
    "pst.bishop": 1.5094,
    "pst.rook": 0.7625,
    "pst.queen": 0.5625,
    "pst.king": 0.9,
    # pawn structure
    "pawn.doubled": 19.125,
    "pawn.isolated": 9.5625,
    "pawn.backward": 6,  # a pawn left behind its neighbours whose stop square an enemy pawn covers (x2 on a half-open file)
    "pawn.connected": 4,  # per connected pawn (phalanx or supported), x(rank-3) so only advanced duos score
    "pawn.passed_scale": 0.9,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 1.728,
    "pawn.blocked_passer": 0.4,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    "pawn.passer_king_dist": 6.76,  # cp per square of net king distance to the passer's front square (endgame-scaled)
    "pawn.connected_passer": 7.5,  # per passer with a friendly passer on an adjacent file
    "pawn.rook_behind_passer": 12,  # a friendly rook behind a passer supports its advance (Tarrasch)
    "pawn.rook_behind_enemy_passer": 10,  # an enemy rook behind our passer attacks/stops it
    # king safety
    "king.shield_gap": 14.421,
    "king.open_file": 17.5781,
    "kattack.scale": 4,   # cp per weighted attack unit on the enemy king zone
    "kattack.proximity": 2,  # cp per weighted closeness unit of pieces near the enemy king (phase-scaled)
    # mobility (cp per square above/below typical)
    "mob.knight": 3.9774,
    "mob.bishop": 5.6112,
    "mob.rook": 3.7408,
    "mob.queen": 1.8704,
    # piece activity
    "act.bishop_pair": 44.5312,
    "act.rook_open": 17,
    "act.rook_semi": 16,
    "act.rook_seventh": 22.05,
    # threats (fractions of the threatened piece's value)
    "threat.hanging": 0.0562,  # attacked and undefended (en prise)
    "threat.pawn": 0.1,   # a minor/rook/queen attacked by a pawn (must move or drop material)
    "threat.minor": 0.06,  # a rook/queen attacked by a knight/bishop
    "threat.rook": 0.04,   # a queen attacked by a rook
    "threat.initiative": 0.25,  # the side to move's threats count for more (it can execute them now)
    # drawishness (MULTIPLICATIVE modifier, not a summed concept): pure
    # opposite-colored-bishop endings are drawish, so the whole eval is scaled
    # toward zero. Shown in the breakdown as the marginal delta it applies.
    "ocb.draw_scale": 0.6,  # multiply eval by this in pure opposite-bishop endings
    # mating drive (bare-king endgames)
    "mate_drive.corner": 12,
    "mate_drive.king_prox": 6,
    # tempo
    "tempo": 10,
}

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
    "material.pawn": 88,
    "material.knight": 300.7011,
    "material.bishop": 325.7539,
    "material.rook": 514.3075,
    "material.queen": 1008,
    # piece-square tables: multiplier per piece type on the (tapered) table value
    "pst.pawn": 0.6467,
    "pst.knight": 0.4596,
    "pst.bishop": 1.1398,
    "pst.rook": 1.1126,
    "pst.queen": 0.6139,
    "pst.king": 1.788,
    # pawn structure
    "pawn.doubled": 9.375,
    "pawn.isolated": 12.645,
    "pawn.backward": 5.8109,  # a pawn left behind its neighbours whose stop square an enemy pawn covers (x2 on a half-open file)
    "pawn.connected": 7.6453,  # per connected pawn (phalanx or supported), x(rank-3) so only advanced duos score
    "pawn.passed_scale": 0.4168,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 1.5486,
    "pawn.blocked_passer": 0.3,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    "pawn.passer_king_dist": 5.366,  # cp per square of net king distance to the passer's front square (endgame-scaled)
    "pawn.connected_passer": 9.375,  # per passer with a friendly passer on an adjacent file
    "pawn.rook_behind_passer": 0.2918,  # a friendly rook behind a passer supports its advance (Tarrasch)
    "pawn.rook_behind_enemy_passer": 0.5905,  # an enemy rook behind our passer attacks/stops it
    # king safety
    "king.shield_gap": 14.4,
    "king.open_file": 26.3398,
    "kattack.scale": 3,   # cp per weighted attack unit on the enemy king zone
    "kattack.proximity": 2.0565,  # cp per weighted closeness unit of pieces near the enemy king (phase-scaled)
    # king danger: a check the defender cannot answer by capturing
    # the checker. Knight checks price highest because they cannot
    # be blocked -- the decisive-loss fit moved this one 24 -> 56.
    "kattack.check_knight": 69.4399,
    "kattack.check_bishop": 26.9035,
    "kattack.check_rook": 102.6809,
    "kattack.check_queen": 20.4448,
    # attacks without a queen are a different animal; a discount OFF
    # full price, so 0.0 is exactly the old behaviour
    "kattack.queenless_discount": 0.6382,
    # king-zone squares only the king itself defends
    "kattack.weak_zone": 0.9031,

    # mobility (cp per square above/below typical)
    "mob.knight": 5.9823,
    "mob.bishop": 4.2084,
    "mob.rook": 2.8056,
    "mob.queen": 0.606,
    # piece activity
    "act.bishop_pair": 36,
    "act.rook_open": 21.3578,
    "act.rook_semi": 19.8897,
    # Phase 3 bundle D: material imbalance and space.
    "imbalance.rook_flat": -14.5757,
    "imbalance.knight_pawns": -0.7804,
    "imbalance.rook_pawns": 11.8309,
    "imbalance.rook_pair": 14.28,
    "imbalance.knight_pair": -5.2361,
    "space.scale": 0.0904,
    "act.rook_seventh": 12.5,
    # minor-piece placement (Phase 3 bundle A). Priors are Stockfish 11's own
    # middlegame values scaled by 0.78, because its pawn is 128 and ours is 100.
    # They are starting points for the tuner, not claims.
    "minor.outpost_knight": 22.5014,   # defended, on the 4th-6th, unchaseable
    "minor.behind_pawn": 6.5041,      # sheltered directly behind a pawn
    "minor.bishop_pawns": 2.3914,      # PENALTY per own pawn on the bishop's colour
    "minor.long_diagonal": 13.9972,    # bishop raking both centre squares
    # threats (fractions of the threatened piece's value)
    "threat.hanging": 0.0375,  # attacked and undefended (en prise)
    "threat.pawn": 0.1297,   # a minor/rook/queen attacked by a pawn (must move or drop material)
    "threat.minor": 0.0454,  # a rook/queen attacked by a knight/bishop
    "threat.rook": 0.0536,   # a queen attacked by a rook
    "threat.initiative": 0.7871,  # the side to move's threats count for more (it can execute them now)
    # drawishness (MULTIPLICATIVE modifier, not a summed concept): pure
    # opposite-colored-bishop endings are drawish, so the whole eval is scaled
    # toward zero. Shown in the breakdown as the marginal delta it applies.
    "ocb.draw_scale": 0.9875,  # multiply eval by this in pure opposite-bishop endings
    # mating drive (bare-king endgames)
    "mate_drive.corner": 12.5915,
    "mate_drive.king_prox": 8.0237,
    # tempo
    "tempo": 14.9929,
}


# ---------------------------------------------------------------------------
# Endgame counterparts.
#
# Every weight above is conceptually a MIDDLEGAME value. In every strong
# classical engine each term is really a (middlegame, endgame) PAIR -- a rook on
# the seventh is not worth the same with queens on the board as it is in a pawn
# ending, and Stockfish 11 carries two numbers for literally every term. This
# engine tapers only the pawn and king piece-square tables, so the evaluation has
# roughly half the descriptive capacity it could have, and the Texel tuner has
# been converging against that limit for three sessions.
#
# W_EG holds the ENDGAME value for keys where it differs from the middlegame one.
# A key absent from this dict means "the same in both phases", and wt() then
# returns the middlegame number completely unchanged.
#
# It starts EMPTY on purpose. With no entries the evaluation is bit-for-bit what
# it was before this machinery existed, so introducing it is a provable no-op
# that can be validated without playing a single game -- and tuning can then fill
# it in one key at a time.
#
# material.* is deliberately NOT taperable: those values feed piece_value(),
# which SEE uses for static exchange arithmetic, and a phase-dependent piece
# value would change what "winning a trade" means inside the search.
W_EG: dict[str, float] = {
    "act.bishop_pair": 61.5659,
    "act.rook_open": 21.2146,
    "act.rook_semi": 24,
    "act.rook_seventh": 27.5069,
    "kattack.scale": 4.4917,
    "king.open_file": 34.4323,
    "king.shield_gap": 41.89,
    "mob.bishop": 7.0328,
    "mob.knight": 9.524,
    "mob.queen": 4.676,
    "mob.rook": 5.6112,
    "pawn.blocked_passer": 0.6443,
    "pawn.connected_passer": 3.75,
    "pawn.doubled": 3.75,
    "pawn.isolated": 9.3062,
    "pawn.passed_eg_scale": 2.1488,
    "pawn.passed_scale": 1.3748,
    "pawn.passer_king_dist": 10.14,
    "pawn.rook_behind_enemy_passer": 7.6772,
    "pawn.rook_behind_passer": 8.2999,
    "pst.bishop": 1.0496,
    "pst.king": 0.9479,
    "pst.knight": 0.25,
    "pst.pawn": 0.6639,
    "pst.queen": 0.15,
    "pst.rook": 0.3906,
    "threat.hanging": 0.0754,
    "threat.initiative": 4.3722,
    "threat.minor": 0.072,
    "threat.pawn": 0.0577,
    "threat.rook": 0.024,
}


def wt(key, phase):
    """Weight at this game phase (1.0 = opening, 0.0 = bare kings)."""
    mg = W[key]
    eg = W_EG.get(key)
    if eg is None or eg == mg:
        return mg
    return phase * mg + (1.0 - phase) * eg

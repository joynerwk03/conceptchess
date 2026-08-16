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
    "material.pawn": 90.657,
    "material.knight": 274.2143,
    "material.bishop": 295.4327,
    "material.rook": 485.1224,
    "material.queen": 935.5336,
    # piece-square tables: multiplier per piece type on the (tapered) table value
    "pst.pawn": 0.5846,
    "pst.knight": 0.4286,
    "pst.bishop": 0.9108,
    "pst.rook": 1.0431,
    "pst.queen": 0.5557,
    "pst.king": 1.4522,
    # pawn structure
    "pawn.doubled": 10.5312,
    "pawn.isolated": 11.2858,
    "pawn.backward": 4.3606,  # a pawn left behind its neighbours whose stop square an enemy pawn covers (x2 on a half-open file)
    "pawn.connected": 8.0052,  # per connected pawn (phalanx or supported), x(rank-3) so only advanced duos score
    "pawn.passed_scale": 0.2344,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 2.23,
    "pawn.blocked_passer": 0.3551,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    "pawn.passer_king_dist": 4.0245,  # cp per square of net king distance to the passer's front square (endgame-scaled)
    "pawn.connected_passer": 8.6528,  # per passer with a friendly passer on an adjacent file
    "pawn.rook_behind_passer": 0.1867,  # a friendly rook behind a passer supports its advance (Tarrasch)
    "pawn.rook_behind_enemy_passer": 0.1958,  # an enemy rook behind our passer attacks/stops it
    # can the passer actually run? (per relative rank)
    "pawn.path_clear": 4.1031,      # no enemy piece controls the road
    "pawn.path_defended": 9.594,   # our pieces cover the whole road
    "pawn.path_attacked": 3.3508,   # the square in front is covered

    # king safety
    "king.shield_gap": 12.9306,
    "king.open_file": 31.5114,
    "kattack.scale": 2.25,   # cp per weighted attack unit on the enemy king zone
    "kattack.proximity": 2.9891,  # cp per weighted closeness unit of pieces near the enemy king (phase-scaled)
    # king danger: a check the defender cannot answer by capturing
    # the checker. Knight checks price highest because they cannot
    # be blocked -- the decisive-loss fit moved this one 24 -> 56.
    "kattack.check_knight": 69.8711,
    "kattack.check_bishop": 57.4967,
    "kattack.check_rook": 41.9431,
    "kattack.check_queen": 8.3513,
    # attacks without a queen are a different animal; a discount OFF
    # full price, so 0.0 is exactly the old behaviour
    "kattack.queenless_discount": 0.8068,
    # king-zone squares only the king itself defends
    "kattack.weak_zone": 0,

    # mobility (cp per square above/below typical)
    "mob.knight": 3.8963,
    "mob.bishop": 4.8801,
    "mob.rook": 2.8025,
    "mob.queen": 0.6499,
    # piece activity
    "act.bishop_pair": 24.6255,
    "act.rook_open": 20.6765,
    "act.rook_semi": 19.1848,
    # Phase 3 bundle D: material imbalance and space.
    "imbalance.rook_flat": -18.4352,
    "imbalance.knight_pawns": 0,
    "imbalance.rook_pawns": 13.6289,
    "imbalance.rook_pair": 24.0096,
    "imbalance.knight_pair": -0.4925,
    "space.scale": 0.0081,
    "act.rook_seventh": 9.105,
    # minor-piece placement (Phase 3 bundle A). Priors are Stockfish 11's own
    # middlegame values scaled by 0.78, because its pawn is 128 and ours is 100.
    # They are starting points for the tuner, not claims.
    "minor.outpost_knight": 17.7773,   # defended, on the 4th-6th, unchaseable
    "minor.behind_pawn": 5.4142,      # sheltered directly behind a pawn
    "minor.bishop_pawns": 2.0157,      # PENALTY per own pawn on the bishop's colour
    "minor.long_diagonal": 13.4798,    # bishop raking both centre squares
    # threats (fractions of the threatened piece's value)
    "threat.hanging": 0.0281,  # attacked and undefended (en prise)
    "threat.pawn": 0.1553,   # a minor/rook/queen attacked by a pawn (must move or drop material)
    "threat.minor": 0.0272,  # a rook/queen attacked by a knight/bishop
    "threat.rook": 0.0753,   # a queen attacked by a rook
    "threat.initiative": 1.4336,  # the side to move's threats count for more (it can execute them now)
    # drawishness (MULTIPLICATIVE modifier, not a summed concept): pure
    # opposite-colored-bishop endings are drawish, so the whole eval is scaled
    # toward zero. Shown in the breakdown as the marginal delta it applies.
    "ocb.draw_scale": 0.8009,  # multiply eval by this in pure opposite-bishop endings
    # endgame drawishness, as DISCOUNTS off full price so that 0.0 is
    # exactly the old behaviour (the screen measures a bundle by
    # zeroing its keys; a bare scale factor would zero to nothing)
    "scale.no_pawns": 0.0605,      # ahead by <a rook, and no pawns to promote
    "scale.wrong_bishop": 0.0725,  # rook pawns + a bishop of the wrong colour

    # mating drive (bare-king endgames)
    "mate_drive.corner": 12.6271,
    "mate_drive.king_prox": 8.241,
    # tempo
    "tempo": 15.7792,
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
    "act.bishop_pair": 59.7911,
    "act.rook_open": 21.6644,
    "act.rook_semi": 14.7052,
    "act.rook_seventh": 20.9954,
    "kattack.scale": 3.3688,
    "king.open_file": 21.0973,
    "king.shield_gap": 36.2299,
    "mob.bishop": 4.6587,
    "mob.knight": 7.1025,
    "mob.queen": 5.5548,
    "mob.rook": 3.3367,
    "pawn.blocked_passer": 0.5562,
    "pawn.connected_passer": 3.5156,
    "pawn.doubled": 5.8594,
    "pawn.isolated": 9.1327,
    "pawn.passed_eg_scale": 1.4111,
    "pawn.passed_scale": 1.3897,
    "pawn.passer_king_dist": 10.3111,
    "pawn.rook_behind_enemy_passer": 15.4835,
    "pawn.rook_behind_passer": 13.5526,
    "pst.bishop": 0.984,
    "pst.king": 1.0673,
    "pst.knight": 0.1406,
    "pst.pawn": 0.4833,
    "pst.queen": 0.2344,
    "pst.rook": 0.6104,
    "threat.hanging": 0.0949,
    "threat.initiative": 4.8349,
    "threat.minor": 0.0959,
    "threat.pawn": 0.0346,
    "threat.rook": 0.0144,
}


def wt(key, phase):
    """Weight at this game phase (1.0 = opening, 0.0 = bare kings)."""
    mg = W[key]
    eg = W_EG.get(key)
    if eg is None or eg == mg:
        return mg
    return phase * mg + (1.0 - phase) * eg

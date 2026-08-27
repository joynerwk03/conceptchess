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
    # mobility curve for the knight: entry n is the score for n safe squares.
    # Seeded from the linear form w*(n-4) so this is a no-op until fitted.
    "mob.knight.0": -15.5852,
    "mob.knight.1": -11.6889,
    "mob.knight.2": -7.7926,
    "mob.knight.3": -3.8963,
    "mob.knight.4": 0.0,
    "mob.knight.5": 3.8963,
    "mob.knight.6": 7.7926,
    "mob.knight.7": 11.6889,
    "mob.knight.8": 15.5852,
    # mobility curve for the bishop: entry n is the score for n safe squares.
    # Seeded from the linear form w*(n-6) so this is a no-op until fitted.
    "mob.bishop.0": -29.2806,
    "mob.bishop.1": -24.4005,
    "mob.bishop.2": -19.5204,
    "mob.bishop.3": -14.6403,
    "mob.bishop.4": -9.7602,
    "mob.bishop.5": -4.8801,
    "mob.bishop.6": 0.0,
    "mob.bishop.7": 4.8801,
    "mob.bishop.8": 9.7602,
    "mob.bishop.9": 14.6403,
    "mob.bishop.10": 19.5204,
    "mob.bishop.11": 24.4005,
    "mob.bishop.12": 29.2806,
    "mob.bishop.13": 34.1607,
    # mobility curve for the rook: entry n is the score for n safe squares.
    # Seeded from the linear form w*(n-7) so this is a no-op until fitted.
    "mob.rook.0": -19.6175,
    "mob.rook.1": -16.815,
    "mob.rook.2": -14.0125,
    "mob.rook.3": -11.21,
    "mob.rook.4": -8.4075,
    "mob.rook.5": -5.605,
    "mob.rook.6": -2.8025,
    "mob.rook.7": 0.0,
    "mob.rook.8": 2.8025,
    "mob.rook.9": 5.605,
    "mob.rook.10": 8.4075,
    "mob.rook.11": 11.21,
    "mob.rook.12": 14.0125,
    "mob.rook.13": 16.815,
    "mob.rook.14": 19.6175,
    # mobility curve for the queen: entry n is the score for n safe squares.
    # Seeded from the linear form w*(n-13) so this is a no-op until fitted.
    "mob.queen.0": -8.4487,
    "mob.queen.1": -7.7988,
    "mob.queen.2": -7.1489,
    "mob.queen.3": -6.499,
    "mob.queen.4": -5.8491,
    "mob.queen.5": -5.1992,
    "mob.queen.6": -4.5493,
    "mob.queen.7": -3.8994,
    "mob.queen.8": -3.2495,
    "mob.queen.9": -2.5996,
    "mob.queen.10": -1.9497,
    "mob.queen.11": -1.2998,
    "mob.queen.12": -0.6499,
    "mob.queen.13": 0.0,
    "mob.queen.14": 0.6499,
    "mob.queen.15": 1.2998,
    "mob.queen.16": 1.9497,
    "mob.queen.17": 2.5996,
    "mob.queen.18": 3.2495,
    "mob.queen.19": 3.8994,
    "mob.queen.20": 4.5493,
    "mob.queen.21": 5.1992,
    "mob.queen.22": 5.8491,
    "mob.queen.23": 6.499,
    "mob.queen.24": 7.1489,
    "mob.queen.25": 7.7988,
    "mob.queen.26": 8.4487,
    "mob.queen.27": 9.0986,
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
    "kattack.proximity": 1.79346,   # endgame counterpart (x0.6: king attack is a middlegame phenomenon)
    "kattack.check_knight": 41.92266,   # endgame counterpart (x0.6: king attack is a middlegame phenomenon)
    "kattack.check_bishop": 34.49802,   # endgame counterpart (x0.6: king attack is a middlegame phenomenon)
    "kattack.check_rook": 25.16586,   # endgame counterpart (x0.6: king attack is a middlegame phenomenon)
    "kattack.check_queen": 5.01078,   # endgame counterpart (x0.6: king attack is a middlegame phenomenon)
    "kattack.queenless_discount": 0.48408,   # endgame counterpart (x0.6: king attack is a middlegame phenomenon)
    "kattack.weak_zone": 0.0,   # endgame counterpart (x0.6: king attack is a middlegame phenomenon)
    "mob.knight.0": -28.41,
    "mob.knight.1": -21.3075,
    "mob.knight.2": -14.205,
    "mob.knight.3": -7.1025,
    "mob.knight.4": 0.0,
    "mob.knight.5": 7.1025,
    "mob.knight.6": 14.205,
    "mob.knight.7": 21.3075,
    "mob.knight.8": 28.41,
    "mob.bishop.0": -27.9522,
    "mob.bishop.1": -23.2935,
    "mob.bishop.2": -18.6348,
    "mob.bishop.3": -13.9761,
    "mob.bishop.4": -9.3174,
    "mob.bishop.5": -4.6587,
    "mob.bishop.6": 0.0,
    "mob.bishop.7": 4.6587,
    "mob.bishop.8": 9.3174,
    "mob.bishop.9": 13.9761,
    "mob.bishop.10": 18.6348,
    "mob.bishop.11": 23.2935,
    "mob.bishop.12": 27.9522,
    "mob.bishop.13": 32.6109,
    "mob.rook.0": -23.3569,
    "mob.rook.1": -20.0202,
    "mob.rook.2": -16.6835,
    "mob.rook.3": -13.3468,
    "mob.rook.4": -10.0101,
    "mob.rook.5": -6.6734,
    "mob.rook.6": -3.3367,
    "mob.rook.7": 0.0,
    "mob.rook.8": 3.3367,
    "mob.rook.9": 6.6734,
    "mob.rook.10": 10.0101,
    "mob.rook.11": 13.3468,
    "mob.rook.12": 16.6835,
    "mob.rook.13": 20.0202,
    "mob.rook.14": 23.3569,
    "mob.queen.0": -72.2124,
    "mob.queen.1": -66.6576,
    "mob.queen.2": -61.1028,
    "mob.queen.3": -55.548,
    "mob.queen.4": -49.9932,
    "mob.queen.5": -44.4384,
    "mob.queen.6": -38.8836,
    "mob.queen.7": -33.3288,
    "mob.queen.8": -27.774,
    "mob.queen.9": -22.2192,
    "mob.queen.10": -16.6644,
    "mob.queen.11": -11.1096,
    "mob.queen.12": -5.5548,
    "mob.queen.13": 0.0,
    "mob.queen.14": 5.5548,
    "mob.queen.15": 11.1096,
    "mob.queen.16": 16.6644,
    "mob.queen.17": 22.2192,
    "mob.queen.18": 27.774,
    "mob.queen.19": 33.3288,
    "mob.queen.20": 38.8836,
    "mob.queen.21": 44.4384,
    "mob.queen.22": 49.9932,
    "mob.queen.23": 55.548,
    "mob.queen.24": 61.1028,
    "mob.queen.25": 66.6576,
    "mob.queen.26": 72.2124,
    "mob.queen.27": 77.7672,
}


def wt(key, phase):
    """Weight at this game phase (1.0 = opening, 0.0 = bare kings)."""
    mg = W[key]
    eg = W_EG.get(key)
    if eg is None or eg == mg:
        return mg
    return phase * mg + (1.0 - phase) * eg

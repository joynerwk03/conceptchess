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
    "material.pawn": 87.3318,
    "material.knight": 306.7195,
    "material.bishop": 324.7593,
    "material.rook": 531.861,
    "material.queen": 1063.1064,
    # piece-square tables: multiplier per piece type on the (tapered) table value
    "pst.pawn": 0.7794,
    "pst.knight": 0.4086,
    "pst.bishop": 0.9967,
    "pst.rook": 1.3908,
    "pst.queen": 0.6002,
    "pst.king": 1.9041,
    # pawn structure
    "pawn.doubled": 11.537,
    "pawn.isolated": 13.3009,
    "pawn.backward": 6.8318,  # a pawn left behind its neighbours whose stop square an enemy pawn covers (x2 on a half-open file)
    "pawn.connected": 7.213,  # per connected pawn (phalanx or supported), x(rank-3) so only advanced duos score
    "pawn.passed_scale": 0.3126,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 1.8583,
    "pawn.blocked_passer": 0.2959,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    "pawn.passer_king_dist": 5.366,  # cp per square of net king distance to the passer's front square (endgame-scaled)
    "pawn.connected_passer": 11.537,  # per passer with a friendly passer on an adjacent file
    "pawn.rook_behind_passer": 0.1167,  # a friendly rook behind a passer supports its advance (Tarrasch)
    "pawn.rook_behind_enemy_passer": 0.2362,  # an enemy rook behind our passer attacks/stops it
    # king safety
    "king.shield_gap": 11.7642,
    "king.open_file": 31.633,
    "kattack.scale": 2.25,   # cp per weighted attack unit on the enemy king zone
    "kattack.proximity": 3.8612,  # cp per weighted closeness unit of pieces near the enemy king (phase-scaled)
    # king danger: a check the defender cannot answer by capturing
    # the checker. Knight checks price highest because they cannot
    # be blocked -- the decisive-loss fit moved this one 24 -> 56.
    "kattack.check_knight": 74.1036,
    "kattack.check_bishop": 32.31,
    "kattack.check_rook": 83.8862,
    "kattack.check_queen": 16.7026,
    # attacks without a queen are a different animal; a discount OFF
    # full price, so 0.0 is exactly the old behaviour
    "kattack.queenless_discount": 0.8001,
    # king-zone squares only the king itself defends
    "kattack.weak_zone": 0,

    # mobility (cp per square above/below typical)
    "mob.knight": 5.195,
    "mob.bishop": 4.4327,
    "mob.rook": 3.0994,
    "mob.queen": 0.5199,
    # piece activity
    "act.bishop_pair": 32.834,
    "act.rook_open": 21.6999,
    "act.rook_semi": 23.8867,
    # Phase 3 bundle D: material imbalance and space.
    "imbalance.rook_flat": -14.0411,
    "imbalance.knight_pawns": 0,
    "imbalance.rook_pawns": 10.7334,
    "imbalance.rook_pair": 17.1497,
    "imbalance.knight_pair": -6.1097,
    "space.scale": 0.0271,
    "act.rook_seventh": 12.14,
    # minor-piece placement (Phase 3 bundle A). Priors are Stockfish 11's own
    # middlegame values scaled by 0.78, because its pawn is 128 and ours is 100.
    # They are starting points for the tuner, not claims.
    "minor.outpost_knight": 25.3961,   # defended, on the 4th-6th, unchaseable
    "minor.behind_pawn": 8.5041,      # sheltered directly behind a pawn
    "minor.bishop_pawns": 1.7274,      # PENALTY per own pawn on the bishop's colour
    "minor.long_diagonal": 13.249,    # bishop raking both centre squares
    # threats (fractions of the threatened piece's value)
    "threat.hanging": 0.0281,  # attacked and undefended (en prise)
    "threat.pawn": 0.1553,   # a minor/rook/queen attacked by a pawn (must move or drop material)
    "threat.minor": 0.0272,  # a rook/queen attacked by a knight/bishop
    "threat.rook": 0.0753,   # a queen attacked by a rook
    "threat.initiative": 0.896,  # the side to move's threats count for more (it can execute them now)
    # drawishness (MULTIPLICATIVE modifier, not a summed concept): pure
    # opposite-colored-bishop endings are drawish, so the whole eval is scaled
    # toward zero. Shown in the breakdown as the marginal delta it applies.
    "ocb.draw_scale": 0.8009,  # multiply eval by this in pure opposite-bishop endings
    # mating drive (bare-king endgames)
    "mate_drive.corner": 12.6271,
    "mate_drive.king_prox": 8.241,
    # tempo
    "tempo": 14.9871,
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
    "act.bishop_pair": 70.658,
    "act.rook_open": 17.3315,
    "act.rook_semi": 19.607,
    "act.rook_seventh": 22.472,
    "kattack.scale": 3.3688,
    "king.open_file": 28.1298,
    "king.shield_gap": 48.3065,
    "mob.bishop": 5.8037,
    "mob.knight": 7.524,
    "mob.queen": 5.845,
    "mob.rook": 4.2084,
    "pawn.blocked_passer": 0.5314,
    "pawn.connected_passer": 4.6875,
    "pawn.doubled": 4.6875,
    "pawn.isolated": 7.3062,
    "pawn.passed_eg_scale": 1.7639,
    "pawn.passed_scale": 1.4823,
    "pawn.passer_king_dist": 12.3877,
    "pawn.rook_behind_enemy_passer": 9.6772,
    "pawn.rook_behind_passer": 8.4704,
    "pst.bishop": 1.312,
    "pst.king": 1.1849,
    "pst.knight": 0.1875,
    "pst.pawn": 0.4979,
    "pst.queen": 0.1875,
    "pst.rook": 0.4883,
    "threat.hanging": 0.0949,
    "threat.initiative": 3.0218,
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

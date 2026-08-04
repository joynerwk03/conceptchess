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
    "pst.pawn": 0.5,
    "pst.knight": 0.5625,
    "pst.bishop": 1.13205,
    "pst.rook": 0.953125,
    "pst.queen": 0.5,
    "pst.king": 1.125,
    # pawn structure
    "pawn.doubled": 23.90625,
    "pawn.isolated": 11.953125,
    "pawn.backward": 6,  # a pawn left behind its neighbours whose stop square an enemy pawn covers (x2 on a half-open file)
    "pawn.connected": 4,  # per connected pawn (phalanx or supported), x(rank-3) so only advanced duos score
    "pawn.passed_scale": 0.675,     # multiplier on the per-rank passed bonus
    "pawn.passed_eg_scale": 1.3824,
    "pawn.blocked_passer": 0.32,  # multiplier when the square in front is occupied  # passed pawns matter more in the endgame
    "pawn.passer_king_dist": 5.07,  # cp per square of net king distance to the passer's front square (endgame-scaled)
    "pawn.connected_passer": 7.5,  # per passer with a friendly passer on an adjacent file
    "pawn.rook_behind_passer": 4.8,  # a friendly rook behind a passer supports its advance (Tarrasch)
    "pawn.rook_behind_enemy_passer": 9.0,  # an enemy rook behind our passer attacks/stops it
    # king safety
    "king.shield_gap": 15.8631,
    "king.open_file": 21.972625,
    "kattack.scale": 3.6,   # cp per weighted attack unit on the enemy king zone
    "kattack.proximity": 2,  # cp per weighted closeness unit of pieces near the enemy king (phase-scaled)
    # mobility (cp per square above/below typical)
    "mob.knight": 4.97175,
    "mob.bishop": 5.6112,
    "mob.rook": 3.7408,
    "mob.queen": 1.4028,
    # piece activity
    "act.bishop_pair": 44.5312,
    "act.rook_open": 21.25,
    "act.rook_semi": 16.0,
    # Phase 3 bundle D: material imbalance and space.
    "imbalance.rook_flat": -15.0,
    "imbalance.knight_pawns": -1.5,
    "imbalance.rook_pawns": 15.0,
    "imbalance.rook_pair": 10.2,
    "imbalance.knight_pair": -4.8,
    "space.scale": 0.2,
    "act.rook_seventh": 24.255,
    # minor-piece placement (Phase 3 bundle A). Priors are Stockfish 11's own
    # middlegame values scaled by 0.78, because its pawn is 128 and ours is 100.
    # They are starting points for the tuner, not claims.
    "minor.outpost_knight": 26.4,   # defended, on the 4th-6th, unchaseable
    "minor.behind_pawn": 6.3,      # sheltered directly behind a pawn
    "minor.bishop_pawns": 2.25,      # PENALTY per own pawn on the bishop's colour
    "minor.long_diagonal": 15.75,    # bishop raking both centre squares
    # threats (fractions of the threatened piece's value)
    "threat.hanging": 0.05,  # attacked and undefended (en prise)
    "threat.pawn": 0.15,   # a minor/rook/queen attacked by a pawn (must move or drop material)
    "threat.minor": 0.036,  # a rook/queen attacked by a knight/bishop
    "threat.rook": 0.06,   # a queen attacked by a rook
    "threat.initiative": 0.4,  # the side to move's threats count for more (it can execute them now)
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
    "act.bishop_pair": 48.98432,
    "act.rook_open": 17.85,
    "act.rook_semi": 32.0,
    "act.rook_seventh": 20.9475,
    "kattack.scale": 5.8,
    "king.open_file": 35.1562,
    "king.shield_gap": 28.842,
    "mob.bishop": 6.17232,
    "mob.knight": 7.35819,
    "mob.queen": 3.7408,
    "mob.rook": 6.92048,
    "pawn.blocked_passer": 0.6,
    "pawn.connected_passer": 3.0,
    "pawn.doubled": 8.60625,
    "pawn.isolated": 10.51875,
    "pawn.passed_eg_scale": 2.0736,
    "pawn.passed_scale": 1.1,
    "pawn.passer_king_dist": 13.52,
    "pawn.rook_behind_enemy_passer": 6.5,
    "pst.bishop": 1.5094,
    "pst.king": 0.5,
    "pst.knight": 0.3,
    "pst.pawn": 0.3125,
    "pst.queen": 0.225,
    "pst.rook": 0.3125,
    "threat.hanging": 0.1062,
    "threat.initiative": 0.5,
    "threat.minor": 0.12,
    "threat.pawn": 0.2,
    "threat.rook": 0.016,
}


def wt(key, phase):
    """Weight at this game phase (1.0 = opening, 0.0 = bare kings)."""
    mg = W[key]
    eg = W_EG.get(key)
    if eg is None or eg == mg:
        return mg
    return phase * mg + (1.0 - phase) * eg

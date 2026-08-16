"""King attack: piece pressure on the zone around the enemy king.

Counts attacked squares in the 3x3 king zone, weighted by attacker type,
and only when at least two pieces join the attack (one piece rarely mates).
Scaled by phase — attacks need material on the board.

Volume of pressure is not the same as danger, so three terms qualify it:
safe checks (a check the defender cannot answer by taking the checker), the
queenless discount (the queen is the piece that mates), and weak squares in
the king zone (the ones only the king defends — the mating squares).
"""

import chess

from engine.weights import W, W_EG, wt

_UNIT = {chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 5}

# King danger by attack "units", fitted rather than assumed. The old rule was
# `scale * units^2 / 10`: one free parameter, and a shape taken on faith.
# Fitted on decisive-game loss (monotone, since more pressure cannot be worth
# less), the curve turns out to be FLAT -- slightly negative -- while an attack
# is only notional, and to steepen sharply once enough material has committed.
# Two pieces vaguely pointing at a king is not an attack, and the quadratic was
# paying for it. Two rows so the phase taper stays exact.
KD_MAX = 128
KD_MG = [
    -36.4, -36.4, -36.4, -36.4, -36.4, -12.0, -12.0, -12.0,
    -12.0, 17.0, 29.0, 29.0, 29.0, 29.0, 29.0, 29.0,
    29.0, 29.0, 29.0, 29.0, 29.0, 29.0, 29.0, 29.0,
    57.0, 57.0, 57.0, 114.0, 114.0, 114.0, 202.9, 292.2,
    292.2, 292.2, 292.2, 292.2, 292.2, 308.1, 344.8, 344.8,
    360.0, 378.2, 396.9, 418.6, 435.6, 455.6, 476.1, 497.0,
    518.4, 540.2, 562.5, 585.2, 608.4, 632.0, 656.1, 680.6,
    705.6, 731.0, 756.9, 783.2, 810.0, 837.2, 864.9, 893.0,
    921.6, 950.6, 980.1, 1010.0, 1040.4, 1071.2, 1102.5, 1134.2,
    1166.4, 1199.0, 1232.1, 1265.6, 1299.6, 1334.0, 1368.9, 1404.2,
    1440.0, 1476.2, 1512.9, 1550.0, 1587.6, 1625.6, 1664.1, 1703.0,
    1742.4, 1782.2, 1822.5, 1863.2, 1904.4, 1946.0, 1988.1, 2030.6,
    2073.6, 2117.0, 2160.9, 2205.2, 2250.0, 2295.2, 2340.9, 2387.0,
    2433.6, 2480.6, 2528.1, 2576.0, 2624.4, 2673.2, 2722.5, 2772.2,
    2822.4, 2873.0, 2924.1, 2975.6, 3027.6, 3080.0, 3132.9, 3186.2,
    3240.0, 3294.2, 3348.9, 3404.0, 3459.6, 3515.6, 3572.1, 3629.0,
]
KD_EG = [
    -108.9, -108.9, -108.9, -108.9, -108.9, -2.9, -2.9, 136.2,
    136.2, 136.2, 136.2, 136.2, 136.2, 136.2, 136.2, 136.2,
    136.2, 326.5, 326.5, 326.5, 356.4, 356.4, 356.4, 356.4,
    356.4, 356.4, 356.4, 356.4, 356.4, 356.4, 356.4, 531.7,
    531.7, 531.7, 542.9, 542.9, 542.9, 542.9, 542.9, 542.9,
    542.9, 566.3, 594.3, 624.4, 652.2, 682.2, 712.8, 744.2,
    776.2, 808.8, 842.2, 876.2, 910.9, 946.3, 982.3, 1019.1,
    1056.5, 1094.5, 1133.3, 1172.7, 1212.8, 1253.5, 1295.0, 1337.1,
    1379.9, 1423.3, 1467.4, 1512.3, 1557.7, 1603.9, 1650.7, 1698.2,
    1746.4, 1795.2, 1844.8, 1895.0, 1945.8, 1997.4, 2049.6, 2102.5,
    2156.0, 2210.3, 2265.2, 2320.8, 2377.0, 2434.0, 2491.6, 2549.8,
    2608.8, 2668.4, 2728.7, 2789.7, 2851.4, 2913.7, 2976.7, 3040.3,
    3104.7, 3169.7, 3235.4, 3301.8, 3368.8, 3436.5, 3504.9, 3574.0,
    3643.7, 3714.1, 3785.2, 3856.9, 3929.4, 4002.5, 4076.2, 4150.7,
    4225.8, 4301.6, 4378.1, 4455.2, 4533.1, 4611.6, 4690.7, 4770.6,
    4851.1, 4932.3, 5014.1, 5096.7, 5179.9, 5263.7, 5348.3, 5433.5,
]


def _danger(units, phase):
    if units >= KD_MAX:
        units = KD_MAX - 1
    mg, eg = KD_MG[units], KD_EG[units]
    return mg if mg == eg else phase * mg + (1.0 - phase) * eg


_CHECK_KEY = {chess.KNIGHT: "kattack.check_knight",
              chess.BISHOP: "kattack.check_bishop",
              chess.ROOK: "kattack.check_rook",
              chess.QUEEN: "kattack.check_queen"}


def _slider_from(ksq, occ):
    """Squares a bishop / rook standing there would check the king from."""
    diag = chess.BB_DIAG_ATTACKS[ksq][chess.BB_DIAG_MASKS[ksq] & occ]
    rank = chess.BB_RANK_ATTACKS[ksq][chess.BB_RANK_MASKS[ksq] & occ]
    file = chess.BB_FILE_ATTACKS[ksq][chess.BB_FILE_MASKS[ksq] & occ]
    return diag, rank | file


class KingAttack:
    name = "king_attack"
    display_name = "King attack"

    def score(self, ctx):
        return sum(v for _, v in self._items(ctx, labels=False))

    def details(self, ctx):
        return self._items(ctx, labels=True)

    def _items(self, ctx, labels):
        items = []
        phase = ctx.phase
        if phase < 0.05:
            return items
        board = ctx.board
        occ = board.occupied
        scale = wt("kattack.scale", ctx.phase)
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            ksq = ctx.king_sq[not color]
            if ksq is None:
                continue
            zone = chess.BB_KING_ATTACKS[ksq] | (1 << ksq)
            units = 0
            attackers = 0
            by_type = {}
            for pt, w in _UNIT.items():
                acc = 0
                for sq in ctx.pieces[color][pt]:
                    a = ctx.attacks[sq]
                    acc |= a
                    hits = chess.popcount(a & zone)
                    if hits:
                        units += w * hits
                        attackers += 1
                by_type[pt] = acc

            # The queen is the piece that mates; an attack without one is a
            # different animal and should not be priced the same. Written as a
            # discount OFF a full-price attack, so that a weight of zero is
            # exactly the old behaviour -- the screening harness measures a
            # bundle by zeroing its keys, and a bare multiplier zeroed to 0
            # would delete every queenless attack instead of turning the term
            # off.
            has_queen = bool(ctx.pieces[color][chess.QUEEN])
            disc = (1.0 if has_queen
                    else 1.0 - wt("kattack.queenless_discount", ctx.phase))

            # Everything below is gated on a real attack existing. That is
            # partly chess -- a safe check matters most when pieces are already
            # pressing -- and partly cost: the ungated version scanned every
            # position and measured -4.62% NPS, about -4.6 Elo of lost depth
            # against +3.8 Elo of knowledge, a net loss. Most positions have no
            # two pieces near a king, so gating makes the scan rare.
            if attackers >= 2:
                v = sign * _danger(units, ctx.phase) * phase * disc
                if labels:
                    note = "" if has_queen else ", no queen"
                    items.append((f"{cname} attack on enemy king "
                                  f"({attackers} attackers, {units} units{note})", v))
                else:
                    items.append((None, v))

                # A check the defender cannot answer by capturing the checker
                # is what turns pressure into mate. "Safe" = the landing square
                # is not defended by any enemy piece other than the king.
                # ctx.attacks holds only N/B/R/Q, so the pawns come from
                # ctx.pawn_attacks and the king is simply left out -- which is
                # precisely the mask wanted here.
                defended = ctx.pawn_attacks[not color]
                for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                    for sq in ctx.pieces[not color][pt]:
                        defended |= ctx.attacks[sq]
                safe = ~defended & ~ctx.occupied_co[color]
                diag_from, line_from = _slider_from(ksq, occ)
                from_sq = {chess.KNIGHT: chess.BB_KNIGHT_ATTACKS[ksq],
                           chess.BISHOP: diag_from,
                           chess.ROOK: line_from,
                           chess.QUEEN: diag_from | line_from}
                for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
                    n = chess.popcount(by_type[pt] & from_sq[pt] & safe)
                    if n:
                        cv = (sign * wt(_CHECK_KEY[pt], ctx.phase) * n
                              * phase * disc)
                        if labels:
                            items.append((f"{cname} has {n} safe "
                                          f"{chess.piece_name(pt)} check(s)", cv))
                        else:
                            items.append((None, cv))

                # King-zone squares the attacker hits that only the king
                # defends. These are the squares a mate actually lands on.
                weak = chess.popcount(zone & ~defended
                                      & (by_type[chess.KNIGHT] | by_type[chess.BISHOP]
                                         | by_type[chess.ROOK] | by_type[chess.QUEEN]))
                if weak:
                    wv = sign * wt("kattack.weak_zone", ctx.phase) * weak * phase * disc
                    if labels:
                        items.append((f"{cname} hits {weak} weak square(s) "
                                      f"by the enemy king", wv))
                    else:
                        items.append((None, wv))

            # proximity gradient: pieces closing in on the king matter before
            # they attack the zone (smooth, like the s12 passer king race —
            # gradients give the search direction where discrete rules don't)
            prox = 0
            for pt, w in _UNIT.items():
                for sq in ctx.pieces[color][pt]:
                    d = chess.square_distance(sq, ksq)
                    if d < 4:
                        prox += w * (4 - d)
            if prox:
                pv = sign * wt("kattack.proximity", ctx.phase) * prox * phase
                if labels:
                    items.append((f"{cname} pieces near the enemy king "
                                  f"({prox} closeness units)", pv))
                else:
                    items.append((None, pv))
        return items

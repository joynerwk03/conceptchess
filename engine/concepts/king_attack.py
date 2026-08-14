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

from engine.weights import W, wt

_UNIT = {chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 3, chess.QUEEN: 5}

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
                v = sign * scale * units * units / 10 * phase * disc
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

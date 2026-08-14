"""Pawn structure: doubled, isolated, and passed pawns."""

import chess

from engine.weights import W, wt

# Passed pawn base bonus by rank (from the pawn's own side; rank index 0-7),
# scaled by wt("pawn.passed_scale", ctx.phase).
PASSED_BONUS = [0, 8, 12, 19, 38, 67, 120, 0]


def _rook_behind(board, passer_sign, sq, rook_color):
    """A rook of `rook_color` on the passer's file, behind it (on the side the
    passer advanced from) — the Tarrasch 'rook belongs behind the passed pawn',
    whether it's the pusher's rook (support) or the defender's (attack)."""
    f, r = sq & 7, sq >> 3
    rooks = board.rooks & board.occupied_co[rook_color] & chess.BB_FILES[f]
    behind = ((1 << (r * 8)) - 1) if passer_sign > 0 else ~((1 << ((r + 1) * 8)) - 1)
    return bool(rooks & behind)



def _path_ahead(sq, white):
    """Squares strictly in front of `sq` on its own file, up to promotion."""
    f = sq & 7
    if white:
        return chess.BB_FILES[f] & ~((1 << (sq + 1)) - 1)
    return chess.BB_FILES[f] & ((1 << sq) - 1)


def _path_terms(ctx, sign, sq, rel_rank, scale):
    """(label, value) for whether this passer's road to promotion is open.

    A passer on the sixth whose path is covered by enemy pieces is not the
    asset its rank suggests; one with a clear road in front of it is worth
    more than its rank suggests. Scaled by rank, because it matters most
    close to promotion.
    """
    white = sign > 0
    path = _path_ahead(sq, white)
    if not path:
        return []
    ours = ctx.attacked_by[white]
    theirs = ctx.attacked_by[not white]
    front = sq + 8 if white else sq - 8
    out = []
    if not (path & theirs):
        out.append(("path to promotion is clear of enemy control",
                    sign * wt("pawn.path_clear", ctx.phase) * rel_rank * scale))
    if path & ~ours == 0:
        out.append(("path to promotion fully covered by our pieces",
                    sign * wt("pawn.path_defended", ctx.phase) * rel_rank * scale))
    if 0 <= front <= 63 and (theirs >> front) & 1:
        out.append(("square in front is attacked",
                    -sign * wt("pawn.path_attacked", ctx.phase) * rel_rank * scale))
    return out


class PawnStructure:
    name = "pawn_structure"
    display_name = "Pawn structure"

    def __init__(self):
        # (white_pawn_bb, black_pawn_bb, phase) -> (base, [(sign, sq, raw, conn)]).
        # Pawn structure only changes on pawn moves/captures, so this hits
        # nearly always. Blockade checks (which depend on piece occupancy, not
        # just pawns) are applied outside the cache.
        #
        # `phase` is in the key because `base` is not phase-free: doubled,
        # isolated, backward and connected are tapered, so the same pawn
        # skeleton scores differently once the pieces come off. Leaving it out
        # was correct only while every weight had one value -- it cost 17.7cp
        # on 101 of 6204 positions the moment W_EG was filled, and only in long
        # runs, because a single position never collides with itself. It is
        # ph/24 for an integer ph in 0..24, so this adds at most 25 buckets.
        self._cache = {}

    def score(self, ctx):
        board = ctx.board
        key = (board.pawns & ctx.occupied_co[1], board.pawns & ctx.occupied_co[0],
               ctx.phase)
        cached = self._cache.get(key)
        if cached is None:
            cached = self._compute(ctx)
            if len(self._cache) > 200_000:
                self._cache.clear()
            self._cache[key] = cached
        base, passers = cached
        phase = ctx.phase
        scale = phase + (1 - phase) * wt("pawn.passed_eg_scale", ctx.phase)
        occupied = ctx.board.occupied
        blocked_mult = wt("pawn.blocked_passer", ctx.phase)
        # king race: escorting your passer / catching theirs (endgame-scaled;
        # depends on king squares, so applied outside the pawn-keyed cache)
        kd_w = wt("pawn.passer_king_dist", ctx.phase) * (1 - phase)
        wk = ctx.board.king(chess.WHITE)
        bk = ctx.board.king(chess.BLACK)
        s = base
        for sign, sq, raw, connected, rel_rank in passers:
            for _lbl, v in _path_terms(ctx, sign, sq, rel_rank, scale):
                s += v
            front = sq + 8 if sign > 0 else sq - 8
            mult = blocked_mult if (0 <= front <= 63 and (occupied >> front) & 1) else 1.0
            s += raw * mult * scale
            if connected:
                s += sign * wt("pawn.connected_passer", ctx.phase) * mult * scale
            if kd_w and 0 <= front <= 63:
                ok, ek = (wk, bk) if sign > 0 else (bk, wk)
                s += sign * kd_w * (chess.square_distance(ek, front)
                                    - chess.square_distance(ok, front))
            color = sign > 0
            if _rook_behind(board, sign, sq, color):
                s += sign * wt("pawn.rook_behind_passer", ctx.phase) * scale
            if _rook_behind(board, sign, sq, not color):
                s -= sign * wt("pawn.rook_behind_enemy_passer", ctx.phase) * scale
        return s

    def _compute(self, ctx):
        """Same arithmetic as details(), split into phase-free parts."""
        base = 0.0
        passers = []
        is_passed = self._is_passed
        for color, sign in ((chess.WHITE, 1), (chess.BLACK, -1)):
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            # passer files for this color (pawn-only fact -> cacheable),
            # for connected-passer detection below
            pfiles = set()
            for f in range(8):
                for r in own[f]:
                    if is_passed(color, f, r, enemy):
                        pfiles.add(f)
            for f in range(8):
                ranks = own[f]
                if not ranks:
                    continue
                n = len(ranks)
                if n > 1:
                    base -= sign * wt("pawn.doubled", ctx.phase) * (n - 1)
                if not ((f > 0 and own[f - 1]) or (f < 7 and own[f + 1])):
                    base -= sign * wt("pawn.isolated", ctx.phase) * n
                for r in ranks:
                    if is_passed(color, f, r, enemy):
                        rel_rank = r if color == chess.WHITE else 7 - r
                        connected = (f - 1 in pfiles) or (f + 1 in pfiles)
                        passers.append((sign, chess.square(f, r),
                                        sign * PASSED_BONUS[rel_rank] * wt("pawn.passed_scale", ctx.phase),
                                        connected, rel_rank))
        return base, passers

    def details(self, ctx):
        items = []
        phase = ctx.phase
        passed_scale = phase + (1 - phase) * wt("pawn.passed_eg_scale", ctx.phase)
        for color, sign, cname in ((chess.WHITE, 1, "White"), (chess.BLACK, -1, "Black")):
            own = ctx.pawn_files[color]
            enemy = ctx.pawn_files[not color]
            pfiles = set()
            for f in range(8):
                for r in own[f]:
                    if self._is_passed(color, f, r, enemy):
                        pfiles.add(f)
            for f in range(8):
                ranks = own[f]
                if not ranks:
                    continue
                if len(ranks) > 1:
                    items.append((f"{cname} doubled pawns on {chr(97 + f)}-file",
                                  -sign * wt("pawn.doubled", ctx.phase) * (len(ranks) - 1)))
                neighbors = (own[f - 1] if f > 0 else []) + (own[f + 1] if f < 7 else [])
                if not neighbors:
                    items.append((f"{cname} isolated pawn(s) on {chr(97 + f)}-file",
                                  -sign * wt("pawn.isolated", ctx.phase) * len(ranks)))
                for r in ranks:
                    if self._is_passed(color, f, r, enemy):
                        rel_rank = r if color == chess.WHITE else 7 - r
                        sq = chess.square(f, r)
                        front = sq + 8 if color == chess.WHITE else sq - 8
                        blocked = 0 <= front <= 63 and (ctx.board.occupied >> front) & 1
                        mult = wt("pawn.blocked_passer", ctx.phase) if blocked else 1.0
                        tag = " (blockaded)" if blocked else ""
                        items.append((f"{cname} passed pawn on {chess.square_name(sq)}{tag}",
                                      sign * PASSED_BONUS[rel_rank] * mult
                                      * wt("pawn.passed_scale", ctx.phase) * passed_scale))
                        for lbl, v in _path_terms(ctx, sign, sq, rel_rank, passed_scale):
                            items.append((f"{cname} {chess.square_name(sq)} passer: {lbl}", v))
                        if (f - 1 in pfiles) or (f + 1 in pfiles):
                            items.append((f"{cname} connected passer on {chess.square_name(sq)}",
                                          sign * wt("pawn.connected_passer", ctx.phase) * mult * passed_scale))
                        # king race (same arithmetic as score(); omit when 0)
                        kd_w = wt("pawn.passer_king_dist", ctx.phase) * (1 - phase)
                        if kd_w and 0 <= front <= 63:
                            wk = ctx.board.king(chess.WHITE)
                            bk = ctx.board.king(chess.BLACK)
                            ok, ek = (wk, bk) if sign > 0 else (bk, wk)
                            race = sign * kd_w * (chess.square_distance(ek, front)
                                                  - chess.square_distance(ok, front))
                            if race:
                                who = "escorted by king" if race * sign > 0 else "outrun by enemy king"
                                items.append((f"{cname} {chess.square_name(sq)} passer {who}",
                                              race))
                        col = sign > 0
                        if _rook_behind(ctx.board, sign, sq, col):
                            items.append((f"{cname} rook behind {chess.square_name(sq)} passer",
                                          sign * wt("pawn.rook_behind_passer", ctx.phase) * passed_scale))
                        if _rook_behind(ctx.board, sign, sq, not col):
                            items.append((f"Enemy rook behind {cname} {chess.square_name(sq)} passer",
                                          -sign * wt("pawn.rook_behind_enemy_passer", ctx.phase) * passed_scale))
        return items

    @staticmethod
    def _is_passed(color, file, rank, enemy_files):
        for f in (file - 1, file, file + 1):
            if 0 <= f <= 7:
                for er in enemy_files[f]:
                    if (color == chess.WHITE and er > rank) or (color == chess.BLACK and er < rank):
                        return False
        return True

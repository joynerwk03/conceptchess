"""Endgame drawishness — a MULTIPLICATIVE eval modifier.

Some endings are drawn no matter how the evaluation adds up, and they stay drawn
for longer than any search horizon. A knight ahead with no pawns cannot mate; a
bishop with the wrong rook pawn cannot promote past a king in the corner. The
concept sum scores both as winning, and the search cannot see far enough to find
out otherwise, so the verdict has to be corrected here.

Written as discounts off full price, so a weight of zero is exactly the old
behaviour. Like the opposite-bishop modifier, the breakdown reports the marginal
effect ``(factor - 1) x running_eval`` as a labelled item, so the explanation
still sums to the number search uses.
"""

import chess

from engine.weights import W

_NP = {chess.KNIGHT: "material.knight", chess.BISHOP: "material.bishop",
       chess.ROOK: "material.rook", chess.QUEEN: "material.queen"}


def _non_pawn(ctx, color):
    return sum(W[k] * len(ctx.pieces[color][pt]) for pt, k in _NP.items())


def _wrong_rook_pawn(ctx, strong):
    """Bishop + rook pawns only, bishop not covering the promotion square, and
    the defending king sitting on it. The oldest draw in the endgame book."""
    sp = ctx.pieces[strong]
    if len(sp[chess.BISHOP]) != 1 or sp[chess.KNIGHT] or sp[chess.ROOK] or sp[chess.QUEEN]:
        return False
    pawns = sp[chess.PAWN]
    if not pawns:
        return False
    files = {sq & 7 for sq in pawns}
    if files != {0} and files != {7}:
        return False                      # not purely rook pawns on one side
    f = 0 if files == {0} else 7
    promo = chess.square(f, 7 if strong == chess.WHITE else 0)
    bishop = sp[chess.BISHOP][0]
    b_light = bool(chess.BB_LIGHT_SQUARES & chess.BB_SQUARES[bishop])
    p_light = bool(chess.BB_LIGHT_SQUARES & chess.BB_SQUARES[promo])
    if b_light == p_light:
        return False                      # bishop controls the queening square
    dk = ctx.king_sq[not strong]
    return dk is not None and chess.square_distance(dk, promo) <= 1


class EndgameScale:
    name = "endgame_scale"
    display_name = "Endgame scale"

    def _cases(self, ctx):
        w, b = _non_pawn(ctx, chess.WHITE), _non_pawn(ctx, chess.BLACK)
        if w == b:
            return []
        strong = chess.WHITE if w > b else chess.BLACK
        out = []
        # A material edge smaller than a rook, with nothing to promote, is not a
        # win: there is no way to force mate and no pawn to make one.
        # BOTH sides pawnless. Requiring it only of the stronger side was wrong:
        # a bishop against three pawns counts the bishop's owner as "strong",
        # and scaling that toward zero mis-scores a position the pawns win.
        # Measured -0.198% on decisive games before this condition was tightened.
        if (not ctx.pieces[strong][chess.PAWN]
                and not ctx.pieces[not strong][chess.PAWN]
                and abs(w - b) < W["material.rook"]):
            out.append(("no pawns to promote and less than a rook ahead",
                        1.0 - W["scale.no_pawns"]))
        if _wrong_rook_pawn(ctx, strong):
            out.append(("bishop is the wrong colour for the rook pawn",
                        1.0 - W["scale.wrong_bishop"]))
        return out

    def factor(self, ctx):
        f = 1.0
        for _lbl, v in self._cases(ctx):
            f *= v
        return f

    def item_label(self, ctx):
        c = self._cases(ctx)
        return c[0][0] if c else "endgame scale"

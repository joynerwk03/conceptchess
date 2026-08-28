"""Contempt: score a draw as slightly bad for us, so the search declines drawish lines.

The rating run is 286W 539D 290L over 1115 games against stockfish:3000 --
dead level, and **48.3% draws**. That is the largest visible inefficiency left:
half the games are decided by neither side. Contempt is the standard, cheap way
to convert some of it, and it is untested here.

It does NOT touch interpretability. This is a search-side value for the DRAW
NODE, not an evaluation concept: `evaluate_detailed` is unchanged, the concept
sum is unchanged, and the C-equals-Python invariant is unaffected because no
weight and no term moves. `eval_check` must still print 0.000000, and if it does
not, something other than the draw score was altered.

Sign convention, using ply parity rather than a root-side global: at even ply it
is the root side to move, and negamax returns scores from the side-to-move's
perspective, so a draw is worth -C to us at even ply and +C at odd ply (good for
the opponent, which is the same statement).

Risk, stated up front: contempt is a bet that we are not worse. Against an
anchor at our own strength that bet is roughly even, so too large a value loses
Elo by declining draws in positions we cannot actually win. Standard engine
values are 10-30cp. This must be gated on GAMES -- the referee screen compares
against SF11, which has its own contempt, so it cannot price this.

Usage: contempt.py <worktree> <centipawns>
"""
import pathlib
import sys

WT = pathlib.Path(sys.argv[1])
C = int(sys.argv[2])
p = WT / "core/csearch.c"
s = p.read_text()

OLD = """    if(b->hm >= 100 && !in_check(b,b->side)){ ret=0; done=1; }
    if(!done && (is_rep(h,b->hm)||insufficient(b))){ ret=0; done=1; }"""
NEW = f"""    /* Contempt: a draw is worth -{C}cp to the root side, so the search prefers a
     * playable position to a repetition when it does not believe it is worse.
     * ply parity gives the root side directly -- even ply is our move, and
     * negamax scores from the side to move, so the sign flips with ply. This is
     * a value for the draw NODE, not an eval term: no concept and no weight
     * changes, so the explanation layer and eval_check are untouched. */
    int drawv = (ply & 1) ? {C} : -{C};
    if(b->hm >= 100 && !in_check(b,b->side)){{ ret=drawv; done=1; }}
    if(!done && (is_rep(h,b->hm)||insufficient(b))){{ ret=drawv; done=1; }}"""

assert s.count(OLD) == 1, "draw-score block not found"
p.write_text(s.replace(OLD, NEW, 1))
print(f"patched {p} (contempt {C}cp)")

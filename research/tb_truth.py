"""Grade the engine's endgame play against tablebase ground truth.

Every strength number this project has is a game result, and games are a noisy
instrument: 1200 paired slots resolve about +/-23 Elo, which is wider than any
change the engine can still produce. That is a property of games, not of the
engine, and it can be sidestepped for one part of chess -- below six pieces the
right answer is not an estimate, it is known.

So grade moves instead of counting games. For each position, ask the tablebase
for the theoretical result, ask the engine (with its own tablebase switched OFF)
for a move, and ask the tablebase again afterwards. Any move that turns a win
into a draw, or a draw into a loss, is an outright error -- not a small
disadvantage, an error with a proof. There is no sampling noise in that verdict,
so a few thousand positions give a sharper picture of endgame play than tens of
thousands of games could.

What it is good for: finding systematic blind spots (which material
configurations, which phase of the ending), and measuring whether a change helps
where the evaluation is weakest and the horizon helps least.

What it is not: an Elo number. Positions sampled uniformly are not positions
that arise in play, and a strong opponent avoids most of these endings
altogether. Read it as a defect count, not as strength.

    PYTHONPATH=. .venv/bin/python research/tb_truth.py --n 400 --movetime 0.2
"""
import argparse
import random

import chess

from engine import tablebase as tb


def random_position(rng, men):
    """A random legal position with `men` pieces, no castling rights."""
    pieces = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]
    for _ in range(400):
        b = chess.Board(None)
        squares = rng.sample(range(64), men)
        b.set_piece_at(squares[0], chess.Piece(chess.KING, chess.WHITE))
        b.set_piece_at(squares[1], chess.Piece(chess.KING, chess.BLACK))
        for sq in squares[2:]:
            pt = rng.choice(pieces)
            col = rng.choice([chess.WHITE, chess.BLACK])
            if pt == chess.PAWN and chess.square_rank(sq) in (0, 7):
                pt = chess.ROOK
            b.set_piece_at(sq, chess.Piece(pt, col))
        b.turn = rng.choice([chess.WHITE, chess.BLACK])
        b.clear_stack()
        if b.is_valid() and not b.is_game_over():
            return b
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--men", type=int, default=5)
    ap.add_argument("--movetime", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=20260817)
    # A uniformly random five-man position is nearly always lopsided, so almost
    # any move keeps the result and the test grades nothing: 300 such positions
    # produced ONE error. Keeping only positions where few legal moves preserve
    # the result concentrates the sample on decisions that can actually be got
    # wrong -- the endgame equivalent of mining a harder tactics suite once the
    # old one saturates.
    ap.add_argument("--max-preserving", type=float, default=0.34,
                    help="keep positions where at most this FRACTION of legal "
                         "moves preserves the theoretical result (1.0 = no filter)")
    a = ap.parse_args()

    if not tb.available() or tb.max_pieces() < a.men:
        raise SystemExit(f"need tablebases covering {a.men} men "
                         f"(have {tb.max_pieces()})")

    from engine.engine import Engine
    # The engine's OWN tablebase is switched off: the point is to grade the
    # search and evaluation, not to confirm that a lookup returns what the
    # lookup returned.
    eng = Engine(use_book=False, use_tablebase=False)
    rng = random.Random(a.seed)

    sgn = lambda w: (1 if w > 0 else (-1 if w < 0 else 0))       # noqa: E731

    def preserving_fraction(board, before_s):
        """What share of legal moves keeps the theoretical result?"""
        legal = list(board.legal_moves)
        keep = 0
        for mv in legal:
            board.push(mv)
            got = tb.probe(board)
            if got is not None and sgn(-got[0]) >= before_s:
                keep += 1
            board.pop()
        return (keep / len(legal)) if legal else 1.0, len(legal)

    tried = errs = wins_lost = draws_lost = scanned = 0
    by_kind = {}
    examples = []
    while tried < a.n:
        b = random_position(rng, a.men)
        if b is None:
            continue
        got = tb.probe(b)
        if got is None:
            continue
        wdl_before = got[0]
        scanned += 1
        if a.max_preserving < 1.0:
            frac, nlegal = preserving_fraction(b, sgn(wdl_before))
            if nlegal < 2 or frac > a.max_preserving:
                continue
        res = eng.best_move(b, movetime=a.movetime)
        if res.move is None:
            continue
        tried += 1
        b.push(res.move)
        after = tb.probe(b)
        if after is None:
            b.pop()
            continue
        wdl_after = -after[0]          # back to the mover's point of view
        # 2/1 win, 0 draw, -1/-2 loss. Collapse cursed/blessed into the
        # ordinary categories: the fifty-move rule makes them draws in play.
        sgn = lambda w: (1 if w > 0 else (-1 if w < 0 else 0))   # noqa: E731
        before_s, after_s = sgn(wdl_before), sgn(wdl_after)
        kind = "".join(sorted(chess.piece_symbol(p.piece_type).upper()
                              for p in b.piece_map().values()))
        rec = by_kind.setdefault(kind, [0, 0])
        rec[0] += 1
        if after_s < before_s:
            errs += 1
            rec[1] += 1
            if before_s > 0:
                wins_lost += 1
            else:
                draws_lost += 1
            if len(examples) < 8:
                b.pop()
                examples.append((b.fen(), res.move.uci(), before_s, after_s))
                b.push(res.move)
        b.pop()

    print(f"\n{tried:,} {a.men}-man positions, {a.movetime}s per move, "
          f"engine tablebase OFF")
    print(f"  moves that threw away the theoretical result: {errs:,} "
          f"({100*errs/max(tried,1):.1f}%)")
    print(f"    win  -> draw/loss : {wins_lost:,}")
    print(f"    draw -> loss      : {draws_lost:,}")

    worst = sorted((v[1] / v[0], k, v) for k, v in by_kind.items() if v[0] >= 8)
    if worst:
        print(f"\n  worst material configurations (>=8 samples):")
        for rate, k, v in worst[-8:][::-1]:
            print(f"    {k:<8} {v[1]:>3}/{v[0]:<3} errors  {100*rate:5.1f}%")
    if examples:
        print(f"\n  examples:")
        for fen, mv, bs, as_ in examples:
            print(f"    {mv}  {['loss','draw','win'][bs+1]} -> "
                  f"{['loss','draw','win'][as_+1]}   {fen}")


if __name__ == "__main__":
    main()

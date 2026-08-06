"""Does the opening book help, and where does it leave the engine?

The book has never been measured. Every gate in the LOG starts from a UHO
opening -- a position several moves deep that is almost never in the book -- so
the book simply never fires. It fires in every game the user actually plays.

Two questions this answers without playing anything:
  1. How far into a game does the book actually reach, in plies and in clock?
  2. When it runs out, does it hand over a position the engine likes?

The second matters more than it sounds: a book line that ends in a structure the
engine misevaluates is worse than no book at all.
"""
import sys

import chess

CC = "/home/joynerwk03/mission-control/projects/conceptchess"
sys.path.insert(0, CC)

from engine import book  # noqa: E402
from engine.evaluation import evaluate  # noqa: E402

print(f"{len(book.BOOK)} positions, {len(book.LINES)} openings, "
      f"{sum(len(v) for v in book.LINES.values())} lines\n")

print(f"{'opening':22s} {'plies':>6s} {'eval at exit':>13s}  final position")
print("-" * 92)
exits = []
for name, lines in sorted(book.LINES.items()):
    for ln in lines:
        b = chess.Board()
        n = 0
        for san in ln.split():
            try:
                b.push_san(san)
            except ValueError:
                print(f"{name:22s} ILLEGAL SAN {san!r} in line: {ln}")
                break
            n += 1
        else:
            ev = evaluate(b)
            exits.append((name, n, ev, b.fen()))

for name, n, ev, fen in exits:
    print(f"{name:22s} {n:6d} {ev:+12.1f}  {fen.split(' ')[0][:34]}")

evs = [e for _, _, e, _ in exits]
plies = [n for _, n, _, _ in exits]
print()
print(f"lines that parse: {len(exits)}")
print(f"book depth: {min(plies)}-{max(plies)} plies, mean {sum(plies)/len(plies):.1f}")
print(f"eval at book exit: min {min(evs):+.1f}  max {max(evs):+.1f}  "
      f"mean {sum(evs)/len(evs):+.1f}")
print()
print("A book is doing its job if it exits near equality from White's side of a")
print("balanced line. Large negative exits mean the book is walking the engine")
print("into positions its own evaluation dislikes -- worse than having no book.")

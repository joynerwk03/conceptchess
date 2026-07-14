# ConceptChess

A chess **coach** that shows its work. The engine plays at roughly 2400 Elo
(a fast compiled core), but its evaluation is deliberately a sum of named,
human-meaningful concepts — material, piece placement, pawn structure, king
safety, king attack, mobility, activity, threats, tempo — so every judgment can
be explained. Tests enforce that the displayed breakdown is *exactly* the
evaluation the search maximized (even the compiled eval is verified identical
to the readable Python one), so nothing shown is a post-hoc summary.

## Play & learn

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m gui.server
# open http://localhost:8000
```

The web app is built to teach:

- **Coach my moves** — after each move you play, an instant verdict
  (best / good / inaccuracy / mistake / blunder) versus the engine's choice,
  explained in concept terms ("gives up 0.46; worse in threats and placement").
- **Candidates** — the engine's top moves for the position, ranked, each with
  the concepts it changes and its line. Click one to see it on the board.
- **Insights** — hanging pieces (yours in red, winnable in green), a king under
  attack, and passed pawns highlighted right on the board.
- **Review** — after the game, every move is marked on the eval graph and move
  list by quality, with the better move on hover.
- **Concepts** — a glossary of every evaluation term: what it means and why.
- **Analysis** — the engine's own move: its assessment, the expected line, the
  runner-up it considered, and the full concept breakdown.

The engine also speaks UCI (`python -m engine.uci`) for your own GUI.

## Project layout

| Path | What |
|---|---|
| `engine/concepts/` | one module per evaluation concept |
| `engine/search.py` | iterative-deepening alpha-beta (TT, quiescence, null move) |
| `engine/explain.py` | concept deltas → natural-language explanations |
| `gui/` | local web interface |
| `tests/` | invariants (faithfulness, symmetry), search correctness, tactics gate |
| `research/` | benchmark / tactics / match harnesses, research log & roadmap |

## Development

```bash
.venv/bin/python -m pytest -q                    # full test suite
.venv/bin/python -m research.benchmark           # speed (depth / NPS)
.venv/bin/python -m research.match --games 20 --opponent stockfish:1400
```

This repository is structured for an ongoing automated research loop aimed at
making the strongest possible *interpretable* engine — see `CLAUDE.md` for the
protocol and `research/ROADMAP.md` for the hypothesis backlog.

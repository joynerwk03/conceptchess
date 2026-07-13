# ConceptChess

A chess engine that **shows its work**. The evaluation is a sum of named,
human-meaningful concepts — material, piece placement, pawn structure, king
safety, mobility, piece activity, tempo — and while you play against it, the
GUI shows exactly how each concept contributes to its judgment and how the
engine expects each one to change in the line it's calculating.

The explanation is not a summary bolted on afterward: tests enforce that the
displayed breakdown is *exactly* the evaluation the search maximized.

## Play

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m gui.server
# open http://localhost:8000
```

Click a piece, click a destination (promotions auto-queen). After each engine
move the right panel shows:

- the evaluation and the line the engine expects (PV)
- a neutral summary of the main factors behind the score and how they change
  over the expected line
- every concept's contribution, with per-item detail (click a row)

The engine also speaks UCI (`python -m engine.uci`) if you prefer your own GUI.

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

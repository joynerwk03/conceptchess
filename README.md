# ConceptChess

A chess **coach** that shows its work. The engine plays around **2650–2700 Elo**
(compiled C core; Stockfish-ladder-anchored), but its evaluation is deliberately
a sum of named, human-meaningful concepts — material, piece placement, pawn
structure (incl. passed-pawn king races and connected passers), king safety,
king attack, king pressure, mobility, piece activity, threats, tempo, and
endgame mating technique — so every judgment can be explained. Tests enforce
that the displayed breakdown is *exactly* the evaluation the search maximized
(even the compiled eval is verified identical to the readable Python one on
6,204 positions), so nothing shown is a post-hoc summary.

The engine is built by an **automated research loop**: each idea is implemented
as a single-hypothesis change, screened against invariants, and gated by a
60-game match before it's kept — negative results are logged, not hidden. Over
~160 gated experiments the engine rose from ~1570 to its current strength
(measured +223 Elo at 1 s/move against its own four-days-earlier self). See
`research/LOG.md` for the full experiment record and `research/elo_report.html`
for the Elo timeline.

## Play & learn

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m gui.server
# open http://localhost:8000
```

The web app opens on an **analysis board** (the default view): set up any
position — make moves for either side, or paste a FEN — and the engine thinks
about it for as long as you let it, the depth climbing live as its evaluation,
best line, and recommendation arrows (best move green, runner-up faint) refine
in place. An optional opening book, board flip, and one-click reset round it out.
Every number on screen is still a real concept evaluation, shown in the
breakdown beside the board. Switch to **Play vs engine** in the header for a full
game with move-by-move coaching:

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

For maximum playing strength, set `CC_THREADS` to your core count — the
compiled core runs a Lazy-SMP parallel search (~+140–190 Elo on 4–8 cores).
The default is single-threaded and deterministic, which keeps the coach's
explanations reproducible.

## Project layout

| Path | What |
|---|---|
| `engine/concepts/` | one module per evaluation concept (the readable reference eval) |
| `engine/search.py` | readable reference search (iterative-deepening alpha-beta) |
| `core/` | compiled C core that actually plays: bitboard movegen + magic sliders, search, and an eval verified identical to the Python concept eval (`core/eval_check.py`) |
| `engine/explain.py` | concept deltas → natural-language explanations |
| `gui/` | local web interface |
| `tests/` | invariants (faithfulness, symmetry, C-vs-Python eval), search correctness, tactics gate |
| `research/` | benchmark / tactics / match / tuning harnesses, research log, roadmap, Elo timeline |

Any change to the concept eval requires regenerating the C constants
(`python core/gen_eval_data.py && sh core/build.sh`) — a test fails by design
otherwise, so the compiled engine can never silently diverge from the
explanation.

## Development

```bash
.venv/bin/python -m pytest -q                    # full test suite
.venv/bin/python -m research.benchmark           # speed (depth / NPS)
.venv/bin/python -m research.match --games 20 --opponent stockfish:1400
```

This repository is structured for an ongoing automated research loop aimed at
making the strongest possible *interpretable* engine — see `CLAUDE.md` for the
protocol and `research/ROADMAP.md` for the hypothesis backlog.

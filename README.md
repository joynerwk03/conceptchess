# ConceptChess

A chess **coach** that shows its work. At 16 threads and 1s/move it measures
**3004 Elo, 95% CI [2994, 3014]** — 2,400 games against a `UCI_Elo 3000`
Stockfish anchor from unbalanced openings. Single-threaded at 0.3s it is
**2805 [2783, 2827]** on a three-anchor ladder. *(Always quote the thread count
and time control: this engine gains ~+40.5 Elo per doubling of time, so a bare
Elo figure is underspecified.)* Its evaluation is deliberately a sum of named,
human-meaningful
concepts — material, piece placement, pawn structure (incl. passed-pawn king
races and connected passers), king safety, king attack, king pressure, mobility,
piece activity, threats (pieces pressured by a lower-value attacker, weighted by
whose move it is), tempo, and endgame mating technique — so every judgment can be
explained. Tests enforce
that the displayed breakdown is *exactly* the evaluation the search maximized
(even the compiled eval is verified identical to the readable Python one on
6,204 positions), so nothing shown is a post-hoc summary.

The engine is built by an **automated research loop**: each idea is implemented
as a single-hypothesis change, screened against invariants, then gated against
**two independent external anchors** — one anchor is not an external gate, and a
change must be positive on both under a rule fixed *before* the run. Negative
results are logged, not hidden; the log is mostly negative results, and several
entries record measurements overturning the conclusions of earlier ones. See
`research/LOG.md` for the full record and `research/elo_report.html` for the
timeline.

Two honest caveats a reader should have. First, at this strength the measurement
is the bottleneck: resolution is `se ≈ 350/√N` Elo, so *confirming* a +5 Elo
change takes ~19,400 games. Most late-stage candidates are better described as
**unresolvable** than disproven. Second, the evaluation appears to be at a
model-class ceiling — it sits −2.96% against Stockfish 11's classical eval but
+16.94% against an NNUE, with that gap spread evenly across every bucket, which
is the signature of a class limit rather than a missing term. See
`research/INTERPRETABILITY_COST.md` for what the constraint costs, measured.

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
in place — and because analysis is for exploring, not scoring a single move, the
board runs the engine at **full width (all cores, Lazy SMP)** for the deepest
search, while the coach below stays single-threaded and reproducible. An optional
opening book, board flip, and one-click reset round it out.
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

**Playing strength: full-width by default.** When it plays — UCI, the web
play-vs-engine opponent, and the analysis board — the engine runs a Lazy-SMP
parallel search across all cores, worth roughly **+190 Elo** over a single thread
at the same time control. Note the scaling is bounded by *physical* cores, not
logical ones: on a 10-core / 20-thread machine, measured depth per doubling runs
+0.59, +0.69, then only **+0.20** plies from 8→16 threads, because everything
past 10 is hyperthreads and this search is memory-bound. The one place it stays
single-threaded is the **coach's move verdicts**
(best/good/mistake calls, candidate ranking, review), so those stay reproducible.
Override the thread count with `CC_THREADS` (e.g. `CC_THREADS=1` for a
deterministic engine); the research match harness sets `CC_THREADS=1` itself so
version-vs-version strength gates stay clean single-thread comparisons.

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

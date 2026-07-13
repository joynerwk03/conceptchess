# ConceptChess — autoresearch codebase

An interpretable ("symbolic") chess engine: the evaluation is a sum of named
concepts (material, king safety, mobility, ...), and the GUI shows the player
exactly why the engine judges a position the way it does.

**Research goal: the strongest possible interpretable chess engine.** Strength
comes from speed (deeper search) and evaluation accuracy; interpretability is a
hard constraint, not a nice-to-have.

## The core invariant (never break this)

The explanation shown to the user IS the evaluation used by search:

- `evaluate(board)` (fast path) must equal `evaluate_detailed(board).total`
- each concept's `details()` items must sum to its `score()`

`tests/test_eval.py::TestFaithfulness` enforces this. An eval speedup or new
term that can't be attributed to a concept item is not acceptable. Opaque
evaluations (NN evals, unexplained blended terms) are out of scope by design.

## Repo map

- `engine/context.py` — `EvalContext`: shared precomputed position facts (built
  once per eval; put anything two concepts need here, not in the concepts)
- `engine/concepts/` — one module per concept; registry in `__init__.py`
- `engine/evaluation.py` — sums concepts; fast + detailed paths
- `engine/search.py` — iterative-deepening negamax: TT, MVV-LVA/killer/history
  ordering, quiescence + delta pruning, null move, check extension, soft time
- `engine/explain.py` — SearchResult + breakdowns → JSON/natural language
- `engine/uci.py` — UCI interface (`python -m engine.uci`); used by match harness
- `gui/server.py` + `gui/static/index.html` — local web GUI (`python -m gui.server`)
- `tests/` — invariants, search correctness, tactics regression gate
- `research/` — benchmark, tactics runner, suite miner, match harness, LOG, ROADMAP

## Commands

```bash
.venv/bin/python -m pytest -q                  # full suite (~40s; -m 'not slow' to skip tactics)
.venv/bin/python -m research.benchmark --save  # speed baseline → baselines.json
.venv/bin/python -m research.tactics tests/suites/tactics_v1.epd --movetime 1.0
.venv/bin/python -m research.make_suite --count 24 --out <path>   # mine new Stockfish-verified suites
.venv/bin/python -m research.match --games 20 --movetime 0.5 --opponent stockfish:1400
# vs a baseline revision of this engine:
git worktree add research/worktrees/base <rev> && (cd research/worktrees/base && python3 -m venv .venv && .venv/bin/pip -q install chess)
.venv/bin/python -m research.match --games 20 --movetime 0.5 --opponent "cmd:.venv/bin/python -m engine.uci" --opponent-cwd research/worktrees/base
.venv/bin/python -m gui.server                 # play at http://localhost:8000
```

Stockfish is at /opt/homebrew/bin/stockfish (used for suite mining + matches only — never inside the engine).

## Research loop protocol

Each session:

1. **Read `research/LOG.md` (last entries) and `research/ROADMAP.md`.** Pick the
   highest-value hypothesis; prefer finishing in-flight threads over starting new ones.
2. **Baseline.** Note current numbers from `research/baselines.json` + LOG (avg
   depth, NPS, tactics %, last match results). Re-measure if machine conditions differ.
3. **Implement** the change on `main` (small, single-hypothesis diffs).
4. **Gate.** In order (cheap → expensive):
   a. `pytest -q` — all green, faithfulness sacred
   b. `research.benchmark` — no unexplained speed regression (>10% NPS drop needs justification)
   c. `research.tactics` — no regression below the test threshold
   d. `research.match` vs previous commit (20+ games) for strength-relevant changes —
      accept if score ≥ 50% (or clearly positive Elo for eval changes); speed-only
      refactors can skip the match if a–c hold and NPS improves
5. **Record.** Append a LOG entry: date, hypothesis, diff summary, numbers
   before/after, verdict (ACCEPTED/REJECTED + why). Update ROADMAP (check off /
   add follow-ups). Update thresholds in `tests/test_tactics.py` when the
   baseline durably improves. `research.benchmark --save` after accepted speed changes.
6. **Commit** accepted work (one commit per accepted hypothesis). Rejected
   experiments: revert the code, keep the LOG entry — negative results are data.

Rules of thumb:
- Time-to-depth and NPS are means, not ends; the match is the ground truth.
- Elo error bars are big at 20 games (~±120); use 50+ games before claiming small gains.
- When tactics accuracy saturates (>95%), mine a harder suite (deeper `--depth`,
  bigger `--gap`, add quiet-move filters) and add it beside the old one.
- Keep concepts human-meaningful. Splitting/merging concepts is allowed; adding
  a "misc adjustments" bucket is not.

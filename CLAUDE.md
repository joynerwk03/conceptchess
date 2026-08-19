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
- **the compiled C eval must equal the Python eval** (see below)

`tests/test_eval.py::TestFaithfulness` and `tests/test_core.py` enforce this. An
eval speedup or new term that can't be attributed to a concept item is not
acceptable. Opaque evaluations (NN evals, unexplained blended terms) are out of
scope by design.

## Compiled core (the engine that actually plays) — 2805 Elo single-thread

*(measured 2026-08-17, 3-anchor ML fit, 900 games at **0.3s**, 95% CI [2783, 2827].
The time control is part of the number, not a detail: against the same anchors
this engine scores +95 Elo at 0.3s and +176 at 1.2s, because UCI_Elo-limited
Stockfish barely gains from extra time and this engine gains +40.5 per doubling.
Quote a rating without its TC and it means nothing;
`research/data/elo_history.json` tracks this over time.)*

**At 8 threads: 2920, 95% CI [2885, 2956]** (450 ladder games, anchors on 1
thread, concurrency 2). Measured directly rather than added: against
stockfish:2700 the same engine scores 60.0% at 1 thread and **81.5% at 8**, a
**+188** delta. The **+96 for ten threads** this file used to quote was a
cross-session composite and understates SMP by roughly half — the same class of
arithmetic that produced a phantom −29 Elo elsewhere in s33. Quote the thread
count with the rating, always; they are different configurations of the engine,
not one number with a footnote.

**Ratings by configuration — always quote the thread count AND the time
control; a bare Elo for this engine is underspecified.** It gains +40.5 Elo per
doubling, and 0.3s/move is ~70x faster than CCRL 40/15.

| config | rating |
|---|---|
| 1 thread, 0.3s | **2805** [2783, 2827] |
| 16 threads, 0.3s | ~2930 |
| **16 threads, 1.0s** | **~2983** [2962, 3003] — 47.5% over **500** games vs `stockfish:3000` |

The 16T/1.0s figure was briefly recorded as 3000 from a 200-game run that scored 50.0%. A 500-game run at the identical configuration scores 47.5%. The runs are not independent (the larger subsumes the smaller's openings) so they are not pooled — the larger supersedes, and the engine sits just BELOW 3000.

The 3000 figure is measured against a 1-thread anchor while we use 16, and
`UCI_Elo` is Stockfish's own approximate scale. The single-thread 0.3s number is
the one to improve.

**Ratings by configuration — always quote the thread count:**

| threads | rating | how measured |
|---|---|---|
| 1 | **2805** [2783, 2827] | 3-anchor ladder, 900 games |
| 8 | **~2900** | vs stockfish:2900 49.2%, vs stockfish:3000 37.0% |
| 16 | **~2930** | vs stockfish:3000 40.0%, −70 Elo [−106, −37] |

8→16 threads is worth only **+22 Elo** (sub-linear Lazy SMP). The engine does not
reach 3000 in any available configuration; the shortfall is 70 Elo at full width,
measured against a reference at the target strength.

**Anchored directly at 8 threads: vs stockfish:2900 49.2% (~2895), vs
stockfish:3000 37.0% (~2908).** Two anchors agreeing to 13 points, so ~2900 is a
measured rating rather than a fitted one. Use `--opponent stockfish:2900/3000`
for anything near this strength.

**The ladder cannot certify a rating above its top anchor.** At 8 threads the
implied rating FALLS as the anchor strengthens — ~2941 vs 2600, ~2917 vs 2700,
~2858 vs 2800 (residual −6.2%) — because the engine now sits at or above the
ladder's ceiling and the fit is extrapolating. For any target near or above
2800, add anchors AT the target: `UCI_Elo` runs to 3190, and scoring 50% against
a 3000-rated reference is the only evidence that settles a 3000 claim.

`engine/Engine` searches with a **compiled C core** by default (`engine/core.py`
binds `core/libcengine.dylib` on macOS / `core/libcengine.so` on Linux+WSL2 via
ctypes; ~50× faster than the Python search,
~+380 Elo). The Python search (`engine/search.py`) is the readable reference,
still used with `Engine(use_core=False)` and by its own tests.

**Interpretability is preserved because the C eval is verified identical to the
Python concept eval.** So the fast search optimizes exactly the number the
Python explanation layer (`evaluate_detailed`, the GUI breakdown) reports.

- `core/cengine.c` — board + perft-validated move generator
- `core/ceval.c` — eval, mirroring `engine/concepts/*`; **do not hand-edit its
  constants** — they come from `core/eval_data.h`, generated by
  `core/gen_eval_data.py` from `engine/weights.py` + the PST tables
- `core/csearch.c` — the search (same features as `engine/search.py`)

**Golden rule: any change to the Python eval (weights, concepts, PSTs) requires**
`python core/gen_eval_data.py && sh core/build.sh`, or
`tests/test_core.py::test_c_eval_matches_python` fails by design (it diffs C vs
Python on 500 positions). Validate the core with:
`sh core/build.sh && python core/perft_check.py && python core/eval_check.py`.
Known gap: the contrastive "alternative" explanation needs `use_core=False`
(the C search doesn't export the root ranking yet).

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

## Setup on a new machine (Linux / Windows-WSL2)

The engine is POSIX C (pthreads + clock_gettime), so it builds unchanged on Linux
and inside WSL2; only the shared-library extension differs and `core/build.sh`
handles that automatically. Native Windows (no WSL) is NOT supported — the Lazy
SMP threading would need porting.

```bash
sudo apt update && sudo apt install -y build-essential python3-venv stockfish
git clone https://github.com/joynerwk03/conceptchess.git && cd conceptchess
python3 -m venv .venv && .venv/bin/pip install chess pytest matplotlib
sh core/build.sh                                    # -> core/libcengine.so
PYTHONPATH=. .venv/bin/python core/eval_check.py    # must print 0.000000
.venv/bin/python core/perft_check.py                # must print ALL PERFT PASS
.venv/bin/python -m pytest -q -m 'not slow'         # all green
```

Work on WSL2's own filesystem (`~/conceptchess`), not `/mnt/c/...` — cross-OS
filesystem access is slow enough to distort match timings.

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

**Stockfish must be on `PATH`** — `research.match --opponent stockfish:N`,
`research.abgate` and `research.calibrate` all find it with `shutil.which`, and
without it there is no *external* gate. That matters more than it sounds: s24
measured that self-play does not transfer for evaluation changes, so a machine
without Stockfish can only ever judge search changes honestly. Used for suite
mining, calibration and matches only — never inside the engine.

- macOS: `/opt/homebrew/bin/stockfish` (brew).
- This Linux/WSL2 box: no sudo, so the official static build lives at
  `~/bin/stockfish`, symlinked into `~/.local/bin`. To redo it, fetch the
  `stockfish-ubuntu-x86-64-avx2` asset from the latest GitHub release and drop
  the binary on `PATH`. Verify with `echo uci | stockfish | grep uciok`;
  `UCI_Elo` spans 1320–3190, which covers the 2600/2700/2800 calibration anchors.

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
- **Self-play is not a valid gate, for eval OR search changes.** s24 concluded
  that eval changes don't transfer but search changes do, and that was wrong.
  A time-management fix measured **+17 Elo [+5, +29] over 1600 self-play games**
  and **-14** across two external gates (run in both orders, to rule out
  harness drift). Self-play pits a change against an opponent sharing its exact
  blind spots. Gate against Stockfish, or don't claim Elo.
- **The engine is memory-bound.** Arithmetic micro-optimisations measure ~0
  (distance table +0.10%, ring popcounts +0.08%); memory layout is where the
  speed is (pawn hash +4.0%, prefetch +5.3%, 16-byte TT entry +1.6%, PEXT
  sliders +7.2%). Before optimising anything, ask whether it touches memory.
- **Nothing amortises per node.** This search averages 1.4 legality calls per
  position and cuts on the first move 90.24% of the time, so "precompute once
  per node, reuse across moves" is structurally dead here — it killed both
  legality schemes and lazy move selection. Make the per-move path cheaper.
- **A tree-identical speed change is self-validating.** If fixed-depth node
  counts match to the node, the change cannot have altered play, so NPS is
  sufficient evidence and no game gate is needed (nor could one resolve +7 Elo).
- **Probe before refactoring.** Making a structure *worse* costs minutes and
  tells you the ceiling: padding the Board and doubling the `pat` stride both
  measured ~0, which killed two planned rewrites before they were written.
- **One external gate is not an external gate — require TWO ANCHORS before
  merging.** Cut-node reduction measured **+28.5 Elo [+5.6, +51.4]** against
  stockfish:2700 over 1200 paired slots and was merged. Against stockfish:2600 it
  measured **+1.8 [−24.0, +27.6]**, and a same-day ladder calibration put it at
  **2774 [2752,2795] vs 2789 [2767,2811]** for the code without it. Reverted. A
  single anchor is a single opponent, and ±23 Elo of interval is wide enough for a
  null to clear zero by chance about one time in twenty. The tell was visible in
  the calibration residuals first: it beat expectation against the anchor it was
  gated on (+3.6% vs +2.1% at 2700) and underperformed against 2600.
- **Never compare calibrations across sessions.** The same merge read 2774 against
  a 2803 recorded earlier and looked like −29; re-calibrating the OLD code the
  same day at the same concurrency gave 2789, so most of the gap was between
  sessions. Calibration is an absolute measurement and drifts; a paired gate is
  built to survive drift. Compare like with like.
- **Price the expected effect against the instrument BEFORE gating.** 600 paired
  slots resolve ~±31 Elo, 1200 slots ~±23. If the expectation sits inside the
  interval, the gate cannot answer the question, and running it just produces a
  number that gets over-read in both directions — the same change read as a
  rejection (−5.7) and an acceptance (+28.5) within one day.
- **+40.5 Elo per doubling prices SPEED, never a tree reduction.** Time scaling was
  measured at +95/+113/+176 Elo at 0.3/0.6/1.2s against a pinned anchor. That
  curve applies to searching the same tree faster (NPS), where the extra work is
  free. It does **not** apply to a pruning or reduction change that shrinks the
  tree by discarding information: cut-node reduction cut nodes 30.4%, which this
  rule priced at ≈+21 Elo, and it measured +1.8 against a second anchor. Nodes
  saved by not looking are not nodes saved by looking faster. Consequence: at
  1–7% per memory-layout win, no available speed change reaches the ~35% needed
  for +25 Elo, so a change must be justified by something other than tree size.
- **A loss screen is evidence only against an INDEPENDENT GENERATION RUN.** This
  data is sampled every few plies from self-play games, so a position-level split
  leaves the same game — same opening, same structure, one correlated result — on
  both sides. King-relative piece tables screened **+1.249%** on a position split
  and **−0.925%** on `texel4` (a different run, 0.1% overlap), while the PST
  control transferred in both. The entire gain was the split. `screen_capacity.py`
  defaults `--test-data` to texel4; treat any older position-split screen as an
  upper bound.
- **The evaluation is not the seam, and this is measured, not assumed.**
  `research/eval_room.py`: this engine is −2.96% against Stockfish 11's classical
  eval (same class) and +16.94% against an NNUE, with the NNUE gap spread evenly
  across every bucket (10.8–24.9%, mostly 15–20%). A missing term is a large gap
  in ONE bucket; a uniform deficit is the model class. Nine hand-picked bundles
  measured zero because the model was never term-limited. Adding classical terms
  is closed; so is cheap capacity (1920 parameters of king-relative interaction
  transfer negatively).
- **The reduction axis is CLOSED, bounded on both sides by resolved gates.**
  Reducing less: -2.83 Elo. Reducing much harder (`red = 0.7 + ln(d)*ln(m)/0.80`,
  worth **+1.9 plies** at 0.3s): **-57.2 [-81.4,-33.0]** vs stockfish:2700 and
  **-33.7 [-60.9,-6.5]** vs stockfish:2600. Nominal depth bought by reduction is
  worth strongly negative Elo here. Note this was only settled by moving a LONG
  way -- every +/-1 ply experiment measured neutral, which showed the surface is
  flat nearby, not that it is optimal.
- **Compare engines at equal DEPTH — and at MORE THAN ONE depth.** Equal time
  conflates how big a tree an engine builds with what its nodes are worth
  (`research/depth_match.py`). But the answer reverses with depth, so a single
  reading is worse than none:

  | equal nominal depth | score vs Stockfish 11 |
  |---|---|
  | 9 | **65.0%** (+108 Elo) |
  | 14 | **28.7%** (−158 Elo) |

  A 266-Elo swing. The depth-9 reading was recorded here as "our nodes are the
  better ones"; that was an artefact of measuring where both engines are far
  below strength. At realistic depth SF11 extracts far more from the same
  nominal depth, and **the deficit grows with depth** — which is why it dominates
  at the 1s/move the rating is quoted at. The remaining gap is in DEEP search
  behaviour (extensions and how critical lines are lengthened), not in the
  evaluation and not in move ordering.

  **But a fixed-DEPTH instrument cannot judge anything that changes work per
  nominal depth.** Widened singular extensions took the depth-14 score from
  −158 to −9 Elo and then measured **−12.5 and −16.8** on both anchors at the
  clock: extending more makes a "depth 14" search deeper along the lines that
  matter, so winning there is near-tautological. Use depth_match for evaluation
  and ordering changes, where work per depth is unchanged; never for extensions,
  reductions or pruning. And run the cost check in the regime the effect lives
  in — nodes at depth 12 read −3.5% for a rule that mostly fires at 14+.
- **Superseded (kept for the reasoning): the seam is the reduction schedule.** SF11 is only 1.26x faster and grows its
  tree at the same rate per ply (1.80 vs 1.82), yet reaches the same nominal depth
  in **5.3x fewer nodes** — a uniformly fatter tree, not a faster-growing one.
  Ordering is acquitted: 88.82% of beta cutoffs come on the first move tried,
  98.46% within four, mean cut index 1.347, and quiescence is a normal 44.4% of
  nodes. With cutoffs that early, LMR barely runs at cut nodes; the tree's cost is
  set at ALL-nodes, where the reduction schedule alone decides it.
- **Any tuning number must be scale-invariant.** The Texel loss is
  `sigmoid(eval/(K*400))`. With K held fixed, multiplying the whole evaluation by
  a constant lowers the loss while changing no move — at K=0.6, x1.2 "gains"
  +0.751% of nothing, and de-tunes the search's centipawn margins (futility,
  probcut, delta pruning) which are calibrated to the current scale. Re-fit K for
  every candidate. If K lands on the edge of its grid, the grid is wrong.
- **Price every new eval term in NPS before believing its loss gain.** A loss
  screen cannot see speed. Bundle E screened at +3.8 Elo and cost -4.62% NPS
  (~-4.6 Elo at EBF 1.852) — a net loss the screen called a win. Use interleaved
  A/B runs and a median; single benchmark readings swing ~5%.
- **Measure coefficients through the real `evaluate()`, never derive them.** The
  first linear PST model was wrong by 7.9cp because `evaluate` multiplies the
  concept sum by the opposite-bishop modifier. Perturb, re-evaluate, compare.
- A perturbation applied evenly across a table or a symmetric position **cancels
  between the two colours** and will pass a broken test. Break the symmetry.
- Time-to-depth and NPS are means, not ends; the match is the ground truth.
- Elo error bars are big at 20 games (~±120); use 50+ games before claiming small gains.
- When tactics accuracy saturates (>95%), mine a harder suite (deeper `--depth`,
  bigger `--gap`, add quiet-move filters) and add it beside the old one.
- Keep concepts human-meaningful. Splitting/merging concepts is allowed; adding
  a "misc adjustments" bucket is not.

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
| **16 threads, 1.0s** | **~2992** (est.) — measured 2983 [2962, 3003] at 47.5% over **500** games vs `stockfish:3000`, plus ~+9 for the time-usage fix merged afterwards. Re-measure before quoting. |

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

**Every gate runs at CC_THREADS=1 — so 16-thread faults are invisible to
gating.** `research.abgate` defaults to `--threads 1`, and the rating run is the
only thing that exercises full width. A missing ply cap in `negamax`/`qsearch`
therefore survived every gate and killed a 600-game rating run with SIGSEGV, and
a 60-game reproduction with SIGBUS, while the same games at 1 thread ran clean.
**Before quoting a rating, run at least one long match at the width it is quoted
at.** Related: a bigger buffer is not a bounds check — `path` was enlarged
384→4096 after an identical segfault and still had no guard on the recursive
push.

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
- **The depth-at-fixed-time probe swings ~0.35 plies; do not read differences
  smaller than that.** A single pass read T=10 at 15.58 against T=16 at 15.38 and
  that was reported as a ~7 Elo handicap in the goal configuration. Three
  interleaved passes give **T=10 15.46, T=16 15.46** with a within-config spread
  of 15.25–15.62. There is no strength difference between 10 and 16 threads here.
  SF-style Lazy SMP skip diversification (SKIP_SIZE/SKIP_PHASE) also measured
  neutral, 15.48 vs 15.46 — SMP diversification is closed.
- **Lazy evaluation is dead here: the non-material terms are too big.** A safe
  margin must exceed the largest possible contribution of everything beyond
  material+PST, measured at **max 563.9cp** even after gating out the three
  multiplicative endgame scalings (opposite bishops, both-pawnless, wrong rook
  pawn) — so ~700 with headroom. The lazy test would only fire when the cheap
  value clears beta by more than a queen, which never happens in quiescence.
  Priced with one `evaluate_detailed` sweep instead of a day of C work.
- **Counting calls is not counting cost.** `eval_stm` shows 13.8% self time over
  11.50M calls against 6.35M `eval_core` calls, and a node probes it up to four
  times (RFP, null move, futility, improving). Hoisting to ONE probe per node is
  provably tree-neutral (nodes identical to the node: 50,267,185) and measured
  **zero** NPS. The first probe pulls the entry into L1; the rest are L1 hits at
  ~1ns, so the self time is that first L2/L3 miss, which every node pays anyway.
- **The engine is memory-bound.** Arithmetic micro-optimisations measure ~0
  (distance table +0.10%, ring popcounts +0.08%); memory layout is where the
  speed is (pawn hash +4.0%, prefetch +5.3%, 16-byte TT entry +1.6%, PEXT
  sliders +7.2%). Before optimising anything, ask whether it touches memory.
- **Nothing amortises per node.** This search averages 1.4 legality calls per
  position and cuts on the first move 90.24% of the time, so "precompute once
  per node, reuse across moves" is structurally dead here — it killed both
  legality schemes and lazy move selection. Make the per-move path cheaper.
- **Check the engine actually spends the budget before hunting for Elo inside
  it.** At `movetime=1.0` this engine returned in a mean of **0.775s**, and
  0.533s on one position — a fifth of every rating it has ever been quoted was
  thrown away. Two rules caused it: an interrupted iteration was DISCARDED
  wholesale, so the loop refused to start one past half-time (`opt_time*0.5`),
  which at EBF 1.8 is exactly where the next iteration still fits. Salvaging the
  partial iteration — taking its move only when a later root move outscored the
  standing one at the deeper depth — made the hedge unnecessary: 99% of budget
  and **+10.0 Elo [−12.1, +32.2]** on the counterbalanced gate. (It first read
  +23.4 and +15.0 on the sequential gate, before that instrument's drift defect
  was known; +10.0 is the trustworthy figure and the earlier pair is not. The
  +16.2 priced in advance from the 1.32x ratio was likewise optimistic, though
  it sits inside the interval.) Found by timing `best_move` against its own
  movetime on eight positions. At a fixed movetime, unused time is not banked —
  it is gone.
- **A tree-identical speed change is self-validating.** If fixed-depth node
  counts match to the node, the change cannot have altered play, so NPS is
  sufficient evidence and no game gate is needed (nor could one resolve +7 Elo).
- **Probe before refactoring.** Making a structure *worse* costs minutes and
  tells you the ceiling: padding the Board and doubling the `pat` stride both
  measured ~0, which killed two planned rewrites before they were written.
- **The gate must be COUNTERBALANCED, because it measures the machine
  otherwise.** `abgate` used to play all of A's games and then all of B's,
  justified by "our engine is deterministic at CC_THREADS=1" — false at a fixed
  MOVETIME, where the search is wall-clock limited and its depth depends on what
  else the box is doing (`research/noise_floor.sh` says so outright). Any drift
  between the phases lands entirely in the delta. Depth-scaled LMR read
  **+70.7 [+36.3,+105.1]** on 500 slots and **−7.9 [−27.2,+11.4]** on 1600
  against the SAME anchor — non-overlapping intervals — because the baseline arm
  scored 55.5% in the pilot where identical code scores 65.3–69.2%. Blocks now
  run **A1 B1 B2 A2** so both arms share the same mean position in time. A large
  A1−A2 split in the printed per-block line is the machine, not the change.
  Note also: 1600 games is 800 opening PAIRS (`(offset+g//2) % 1000`), so
  reported CIs are somewhat too narrow; and a worktree carries its own copy of
  the harness, so commit harness fixes and recreate worktrees before gating.
  **A-B-B-A cancels LINEAR drift, not a mid-run dip** — B holds both middle
  slots, so a central slump lands on it. Seen at once: `A1 78.7 B1 75.0 B2 72.2
  A2 74.7` read −28.3 Elo while the same change on a stable anchor (block splits
  under a point) read −3.3. **Read the per-block line before the delta.** The
  real fix is interleaving both arms in one concurrency pool (arm = `(g//2)%2`,
  opening = `g//4`) so they meet every disturbance together.
- **PGO is not worth it here: +2.3% NPS** (node counts bit-identical, so
  self-validating) ≈ +1.3 Elo, inside the ~5% benchmark swing, for a two-stage
  build. The core is already `-O3 -march=native` over one translation unit, so
  neither PGO nor LTO has much to work with.
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
- **Tapering the flat terms was TRIED and screens the wrong way.** The Texel
  tuner, restricted to the 28 untapered prefixes with everything else frozen,
  converged at **+0.134%** loss (W_EG 31 → 51 of 64 keys, eval_check 0.000000)
  — and the independent paired referee screen read **d_mean +0.445 ± 0.628
  (t = +0.71)**, i.e. slightly WORSE. Not gated. A Texel gain that does not
  transfer is this repo's recorded pattern; the ±25% chess-prior bounds mean the
  fit converges after one pass, so more passes do not help.
- **History-modulated LMR points the opposite way to every pruning experiment.**
  Reducing LESS on quiets with good history improves slightly while searching 1%
  FEWER nodes (divisor 8192: d_mean −0.177, t = −1.64, only 42 of 4706 positions
  changed); pushing the divisor down to make it fire harder just grows the tree
  (1.11× at 128) with no fidelity gain. Under |t|=2 so not gated, but the
  direction — spend the search's own knowledge of which moves matter, rather
  than pruning harder — is the one thing that did not measure negative.
- **The remaining interpretable eval capacity is TAPERING.** `weights.py` says
  it outright: every weight is conceptually a middlegame value, strong classical
  engines carry a (MG, EG) pair for every term, and this engine "has roughly half
  the descriptive capacity it could have". `W_EG` holds 31 tapered terms;
  **28 remain untapered**, including the entire `kattack.*` group (king attack is
  a middlegame phenomenon), `space.scale`, `minor.outpost_knight`, the passer
  path terms and `tempo`. `material.*` is excluded by design — SEE reads those
  values. This preserves interpretability exactly: each concept keeps its name
  and gains a phase-dependent value. It is also the only axis the search-side
  work did not close, and the search work's own conclusion was that pruning
  accuracy is bounded by eval accuracy.
- **`W` and `W_EG` are two dicts, not duplicates.** A regex across both reads 31
  keys as "duplicated" and it is a design feature — `pawn.rook_behind_passer` is
  0.1867 in the middlegame and 13.55 in the endgame on purpose. A dedupe of the
  "duplicates" was written, guarded by "W must compare equal and eval_data.h must
  be byte-identical", and the guard failed instantly and reverted it. **Put the
  invariant that would catch you inside the experiment**; this session that guard
  caught a wrong-engine comparison, a self-referential metric, a calibration that
  passed by luck, and this.
- **The referee screen is FIXED-DEPTH: never use it to predict the Elo of a
  change that alters tree SIZE.** It measures move quality at equal depth, so
  for a thinning change it sees the fidelity cost and is blind to the depth
  benefit — the same flaw as `depth_match`, walked into twice in one session.
  `lmr2`+`qs` screened at 0.65× nodes for only +0.925cp and then measured
  **−25.0 and −3.0** on two anchors. Use the screen to reject configurations
  that damage move quality at equal depth, which is what it was calibrated on.
- **Do not re-price a tree reduction with the speed curve, however tempting the
  arithmetic.** Fitting `Elo = 40.5*doublings − b*cp` to one calibrated point
  (rfp25) projected +11 for a change that measured −25/−3. A model fitted on a
  single point does not overturn the standing rule; it launders the same mistake.
- **Changes that SPEND information behave differently from ones that discard
  it.** Every thinning mechanism (six, all null or negative) threw information
  away. The merged stack — history-modulated LMR (reduce *less* on proven-good
  quiets), a king-attack endgame taper, and a wider aspiration window — spends
  or adds information instead, and screened at **0.92× nodes with d_mean
  −0.776**: fewer nodes AND better moves, which no thinner achieved. Gated
  −12.1 / +30.2 / +3.8 on three anchors, **combined +4.4 [−10.5, +19.3]**.
  Merged on a pre-registered two-of-three rule; **the interval includes zero, so
  do not quote it as established.**
- **When two anchors disagree in sign, run a THIRD — and fix the decision rule
  before it starts.** Pick the anchor nearest this engine's strength: score
  closest to 50% carries the most information per game (se 10.6 at
  stockfish:3000 versus 14.1 and 17.1 at 2700/2600 for the same slot count).
- **THINNING IS CLOSED — six mechanisms, all null or negative on two anchors:**
  singular extensions, depth-scaled LMR, the schedule bundle, RFP margin (halved
  the tree, −33 Elo), history pruning (thinned nothing — the cost is not in the
  tail, LMR already reduces late quiets to nothing), and reduction-from-move-2 +
  quiescence quiet checks (−25.0/−3.0). The explanation has survived every test:
  pruning accuracy is bounded by eval accuracy. Thinning this tree and improving
  this eval are one problem, and the search half is done.
- **A missing `libcengine.so` does NOT raise — it silently becomes the Python
  engine.** `core.HAS_CORE` goes false and `Engine` falls back to
  `engine/search.py`, so a failed build in a candidate worktree yields a screen
  that compares the compiled baseline against a DIFFERENT ENGINE under the
  candidate's name. Caught once only because the fallback is ~50× slower. Every
  probe now asserts `HAS_CORE`; check for the `.so` after building, never grep
  compiler output for "error".
- **Ordering is closed.** Continuation history resized to 32KB
  (`[side][prev_to][to]`) removes the depth loss that killed the 590KB version
  (13.29→13.33 vs 11.2→11.1) and still measures **d_mean +0.332, t 0.52** — no
  value. With 88.82% first-move cutoffs there is no room left for a better quiet
  ordering signal.
- **Triage search changes with `research/screen_ref.py` before gating them.**
  A cached referee table (`research/reftable.py`: one MultiPV search per
  position, SF11 depth 13, ~2.5 pos/s, built once) turns "does this change keep
  the answer" into a minutes-long deterministic measurement. The statistic is
  the **share of moves losing more than 20/50/100cp**, never the mean — mate
  scores put the mean's standard error at 89.6, and even clamped it could not
  separate configs spanning 33 Elo. Calibrated against known Elo at 1991
  positions: baseline 27.0±1.0 >20cp, lmr1.75 (−4 Elo) 27.7±1.0, rfp25
  (−33 Elo) 30.5±1.0 — correct order, separates the −33 at 2.5σ, and correctly
  FAILS to separate the −4. Resolution ≈ 1 Elo per 0.1% blunder rate, so ~15 Elo
  at 12k positions. **Use it to order and reject candidates; it is not a merge
  criterion** — two anchors still are. Draw positions with a STRIDE across
  texel6.jsonl, never a block: that data is self-play sampled every few plies,
  so adjacent lines are the same game.
- **Judge a pruning change by CENTIPAWN LOSS, never by move agreement.** A
  deterministic screen — does the pruned search keep the answer? — can see what a
  ±25 Elo gate cannot, and it is the only affordable way to compare pruning
  schemes. But the statistic decides whether it works. Binary root-move
  agreement ranked `RFP_MARGIN 25` as the BEST configuration tested (57% vs the
  baseline's 56%, tree halved, +1.5 plies, tactics 30/30) and it then measured
  **−35.5 and −32.2 Elo** on two anchors. It fails twice over: agreement
  saturates (the baseline already disagrees with SF11 on 44% of positions, so the
  whole range is 52–58%) and it is a ROOT statistic, blind to the fact that
  reverse futility *returns the static eval as the node's value* — lowering its
  margin corrupts scores flowing up the tree while the root move survives.
  Centipawn loss appeared to rank correctly (median 3.0 / 5.5 / 9.0) — but that
  was scored by comparing an unrestricted `analyse` against
  `analyse(root_moves=[m])`, two different searches, and a position where both
  engines played THE SAME MOVE scored 68cp of loss. Rescored on one MultiPV
  search: **14.1 / 13.9 / 14.2 for configs spanning 33 Elo — no discrimination
  at all.** 33 Elo is under 1cp of mean move quality against a per-position SD
  of ~40, so 200 positions is ~50× too few; ~10k would be needed. The referee
  table depends only on the positions, so it could be computed once and cached,
  making every later candidate nearly free — that is the design, and it is not
  built. **Calibrate any screen against changes whose Elo is already known, and
  treat an uncalibrated screen as an opinion.**
- **The pruning schedule is at a local optimum FOR THIS EVAL, and thinning is
  not free.** Measured five ways: depth-scaled LMR −3.3/−9.3/−4.1, SEE capture
  pruning, a halved tree via RFP −35.5/−32.2, and cp-loss rising for every one of
  them. The tree is 3.8–7.4× fatter than SF11's at equal depth because *pruning
  accuracy is bounded by eval accuracy* — SF11 affords a thin tree because its
  eval knows which branches don't matter. Thinning the tree and improving the
  eval are the same problem; do not attack the first in isolation again.
- **The EBF curve is a games-free instrument for tree shape — and use
  `~/bin/stockfish11`, not `shutil.which("stockfish")`, which is Stockfish 18.**
  Cold node counts at fixed depth (fresh process per engine per depth,
  `ucinewgame` per position) give:

  | EBF | 8→10 | 10→12 | nodes vs SF11 |
  |---|---|---|---|
  | ours | 1.80 | **2.11** rising | 3.8× @d10, 7.4× @d12 |
  | SF11 | 1.98 | **1.51** falling | — |

  Ours accelerates where SF11's decelerates, which is why the ratio widens with
  depth and why the strength deficit does too. That is the signature of pruning
  that doesn't scale with depth (LMR capped at 3 plies, RFP ≤6, LMP ≤5, futility
  ≤2) — past remaining-depth 6 this is close to plain alpha-beta. Unlike
  `depth_match`, this instrument is NOT invalidated by changes that alter work
  per nominal depth, because it measures that work. Ruled out by it already:
  check extensions (removing them entirely moved nodes −3%/+9%, tactics still
  30/30) and widening futility (made the tree *bigger*; with SF-shaped margins
  the deeper rule never fires — depth-12 counts identical at limits 4/6/8).
  Measuring against SF18 instead read a bogus 40× — an NNUE search is not the
  reference for a hand-crafted classical eval.
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

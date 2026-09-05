---

# Current state (session close)

**Engine: 3004 [2994, 3014]** at 16 threads / 1.0s vs `stockfish:3000`, 2400
games. Interpretability invariant intact (`eval_check` 0.000000), 93 tests green
including tactics, perft passing.

## Read this before proposing anything

Both halves of the standard program are **measured shut**, not merely untried:

- **Thinning: 7 gated mechanisms, all null or negative.** The decisive one
  isolated the deep region, left the shallow schedule bit-identical, cut the
  depth-14 tree 30.6%, bent the EBF down exactly as designed, and gated
  -16.9/-31.8. The tree being 3.8-7.4x fatter than SF11's is a SYMPTOM of the
  eval ceiling, not a lever.
- **Eval fitting: closed on two independent targets.** A 26-fold better fit
  (SF11 relabelling, +9.007% held out) bought exactly zero move quality.
- **Speed, TT, SMP, ordering, aspiration: closed.** SMP with a hardware
  explanation (10 physical cores).

**And note the honest caveat:** only ONE of 23 candidates was rejected on
evidence excluding zero. Most were **unresolvable** at +/-26 to 40 Elo, not
proven dead. A properly-powered rerun could plausibly find a small gain among
them — capture LMR (screened -0.998) and capture history (-0.657) are the two
that read on the good side and were never given a fair test.

## What would actually move this

1. **More compute.** `se ~ 350/sqrt(N)`, so ~19,400 slots to confirm +5 Elo. This
   is the binding constraint, and it is a resource problem with no constraint
   cost. Fishtest-scale hardware would make the closed-as-unresolvable candidates
   worth revisiting.
2. **The syzygy `tbprobe` port** — the one unexecuted idea, scoped below. Price it
   BELOW the original +3-8: the KPvKP experiment showed per-node probe overhead
   can exceed the value of the knowledge (it gated -16.0 and was abandoned at 200
   slots).
3. **Relaxing interpretability** — see `research/INTERPRETABILITY_COST.md`, which
   argues AGAINST it after correction history (the strongest case) was tested in
   its constraint-preserving form and screened at t 2.22, worse than a known
   -33 Elo config.

## Method rules earned this session

- Test phase-specific changes on a phase-specific book. `endgame_uho.epd` gives
  **10.5x** the resolution for endgame mechanisms. Elo there is inflated by
  ~1/f: it is a DIRECTION test, never a merge magnitude.
- Screen before gating, on `screen_isonode.py`, and require d_mean < -2. Its
  break-even is -1.0, not zero.
- Always include a known-Elo calibration anchor (`rfp25`, -33) and discard the
  whole run if it fails. That caught a false positive at depth 12.
- Check the candidate rule can FIRE under the test conditions before trusting a
  null (`lmrdeep`, `cap6`, and 50-move discounting were all invisible to the
  screen that was about to judge them).
- Verify thread count, book, and that the change actually fires BEFORE a long
  run, not after.

# Research roadmap

Hypothesis backlog, roughly ordered by expected value. Check off with a LOG
entry reference; add new ideas as they come up.

> **Status (s25, 2026-08-01): the measuring instrument, rebuilt.** s24 ended with
> both levers near their ceiling (three neutral eval results, six neutral search
> results) and one hard lesson: **self-play gates do not measure external strength
> for eval changes** — two eval concepts gated at +55/+29 in self-play and
> transferred ~ZERO against Stockfish, while every search gain did transfer. The
> bottleneck was therefore the instrument, not the ideas: gates were too slow and
> too noisy to resolve the +20–30 Elo effects that remain. s25 rebuilt it —
> parallel gating (~8× throughput), a validated-unbiased harness, and
> `research.calibrate` for repeatable external Elo tracked in
> `research/data/elo_history.json`. **Gate eval changes against Stockfish, never
> against ourselves**, and always confirm with an independent second batch.
>
> Frontier: search remains the transferable lever. Untried directions —
> move-ordering quality (capture history), quiescence quality, SMP scaling beyond
> the hardcoded 8-thread cap, real-play time management, endgame knowledge.

## Speed (deeper search = biggest strength lever in pure Python)

- [x] Profile eval + search (`cProfile`); find the top 3 hot spots before optimizing anything
- [x] Replace `board._transposition_key()` with incremental zobrist hashing (C core: s10 exp1, −5% time, byte-identical nodes)
- [ ] Eval hash table in the C core (eval_core recomputed at every qsearch stand-pat / futility probe; cache by Board.hash, validate byte-identical nodes)
- [x] Cache pawn-structure/king-safety by pawn hash (pawn config changes rarely)
- [ ] Faster mobility: reuse attack masks between eval and move ordering, or approximate
- [x] ~~Aspiration windows at the root~~ (tried, REJECTED — see LOG 2026-07-13)
- [x] Principal variation search (PVS / zero-window re-search)
- [x] Late move reductions (LMR) — likely the single biggest depth win
- [x] Futility pruning at shallow depths
- [x] Static exchange evaluation (SEE) for qsearch pruning + ordering (s5: qsearch; s10 exp2: main-search capture ordering, +53 Elo)
- [ ] Evaluate porting the hot loop to a compiled extension **only if** the concept
      design has stabilized (keep concept semantics defined in Python/spec)

## Evaluation accuracy (better judgment per node)

- [x] ~~Tune concept weights via eval-loss vs Stockfish~~ (s2: anti-correlated) →
      **SOLVED in s16–17 via Texel outcome tuning at scale**: +53 (59k samples) then
      +23 (98k flywheel samples). Requirements discovered: outcome target (not
      eval-MSE), balanced starts (UHO labels are confounded), ≥50k quiet samples,
      prior-bounded with a hard envelope vs the ORIGINAL hand priors (relative
      bounds compound across flywheel spins)
- [x] King safety: attack-unit model (session 2, kept)
- [x] Passed pawns: blockade detection (s2), king proximity in endgame (s12:
      **+110 marginal Elo, the project's strongest eval change**) —
      (both connected passers and rook-behind-passer are DONE -- s23/earlier;
      this line was stale)
- [x] ~~Unstoppable passer (square rule) / wrong-bishop draws / endgame
      knowledge generally~~ **(s26: RETIRED as a strength lever.** The
      phase-resolved post-mortem over 200 games vs SF-2800 measured our EXCESS
      centipawn loss at **+0.6/move in endgames** against +5.2 opening and +4.4
      middlegame — we play endgames at parity with a 2800 opponent, and our worst
      move of the game lands in an endgame only 16% of the time in losses while
      30% of our moves are endgame moves. Still fair game as *coach* value, but
      not as Elo.)
- [ ] New concept: threats/hanging pieces (statically detect en prise material)
- [ ] New concept: space (advanced-square control behind pawn chains)
- [ ] Knight outposts (in piece_activity)
- [ ] Endgame knowledge: wrong-bishop draws, KX vs K mop-up term to actually finish games
- [ ] Tempo/initiative refinement
- [x] ~~Threat weight recalibration~~ (s26: REJECTED, x0.7 gated −3 Elo
      [−22,+16] over 800 games. Combined with s24's neutral test of HIGHER
      values, **the threat weights sit on a measured plateau in both
      directions**.) Lesson for the new tooling: `research.blunders`' culprit
      table names the concept that DIFFERS most between our move and the best
      move, which is not the concept that is WRONG — `threats` tops it because it
      is high-variance across candidate moves. Treat it as a place to look, never
      as a diagnosis.
- [ ] Eval headroom, if any, is a NEW CONCEPT rather than a weight — and only
      ~18% of real blunders survive 10x thinking time, so the ceiling on all eval
      work is low. Winning concepts historically are concrete + beyond the search
      horizon + not already handled by search. Gate with `research.abgate`
      (external), never self-play.

## Search quality

- [x] Qsearch: include checks at first ply of quiescence (s5)
- [x] ~~Aggressive log-log LMR reduction table~~ (s11: REJECTED −29 Elo at 46%; 4–5 ply reductions discard too much at depth ~10–12. **s21 re-test:** same table now that ordering is strong (malus/countermove/SEE) → **neutral, 50%, −0 Elo** over 60 games — the s11 loss was ordering-dependent, but fixing it makes aggressive LMR a wash, not a win. Still rejected; lesson reaffirmed: bottleneck is ordering/eval, not per-node work.)
- [x] ~~Internal iterative deepening (IID)~~ (s21: NOT GATED — PV-only is inert under ID+TT (identical node counts); broadened is uneconomic, +49% nodes, same move choice)
- [x] ~~Continuation history~~ (s21: REJECTED — +40% nodes-to-depth in every variant; butterfly+killers+countermove+SEE ordering is already a strong optimum)
- [x] ~~Capture history~~ (s25: REJECTED — pooled 800 games 49.25%, −5 Elo, 95% CI
      [−24,+14]. The last missing learned-ordering table: captures were ordered by
      SEE alone, which returns 0 for every even trade. Made the tree cheaper (+7%
      nps, +0.17 avg depth) but not better — the move it would promote is almost
      always already the TT move, searched first anyway. Fifth ordering experiment
      to land neutral-or-worse; **stop trying to improve move ordering on this
      engine** unless a diagnosis points there specifically)
- [x] ~~Bigger TT (22→24 bits)~~ (s21: REJECTED neutral — cuts nodes but same depth; 384MB cache penalty cancels the hit-rate gain, at play AND deep-analysis TC)
- [x] **Aspiration windows at the root** (s21: ACCEPTED, ~+23 Elo pooled over 120 games — the root had searched a full window every iteration; delta=20)
- [ ] Mate-distance pruning
- [x] ~~50-move-rule detection (plain hm>=100 -> 0)~~ (s12: REJECTED at 48%,
      −12 — suspected TT pollution across clock contexts) — [ ] refined
      variant: same draw scoring but skip TT stores when hm>80, so
      clock-contaminated scores never leak into low-clock contexts
- [x] Repetition detection actually works now (s12: the port had only ever
      scanned opposite-side path entries — dead since s9; fix gated +47)
- [ ] Aspiration windows, third attempt — only after root scores prove stable at C-core depths (failed at depth ~7 twice; the C core reaches 10–12 where swings may be smaller)
- [x] Lazy SMP multithreading (s20: +140/+187 at 4/8 cores — the plateau breaker)
- [ ] SMP tuning: helper diversity beyond staggered depth, depth-preferred TT
      replacement (helps under multi-thread write pressure), thread-count auto-detect
- [x] ~~Singular / TT-move extensions~~ (s19: neutral both TCs; a 40-game 1s
      false-positive was caught by a confirmation batch)
- [ ] Repetition-aware TT (avoid TT cutoffs masking repetition draws)
- [ ] Better time management (spend more on unstable root evals)
- [x] ~~**Concept-aware search control**~~ (s27: **premise NOT SUPPORTED**, killed
      before implementation. `vol = |threats| + |king_attack|` predicts
      `|search(6) − static|` with Spearman **+0.002**, and **+0.005** controlling
      for `|static eval|` — over 216 positions. Pearson looked better (+0.077,
      and +0.333 for the `|static|` null) but the swing distribution is
      heavy-tailed, so those are outliers rather than signal. Diagnosis, which is
      the useful part: *a threat term only predicts instability if it is
      miscalibrated*, and ours already prices in the material the threat wins.
      Items 2 and 3 below rest on the same premise and inherit the verdict.
      Untested variant if ever revisited: sample **interior** nodes at depth ≤6
      rather than suite roots, since that is where RFP actually fires.
      `ccruns/volatility_premise.py`.)
      Every other engine's evaluation is a single number, so its search has to
      *guess* whether a node is sharp or quiet from scalar proxies: the
      `improving` flag, static-eval-versus-beta, whether the last move was a
      capture. Ours is a typed decomposition, and the type tells us directly.
      Split the eval's running sum into a **volatile** part (threats +
      king_attack — worth a lot now, gone in two plies) and a **stable** part
      (pawn structure, placement, mobility). Cost in C is two extra `+=` in
      sections that already exist; the split is exact, so it stays faithful.
      Then spend it, cheapest first:
      1. **Reverse-futility margin scaled by volatility.** RFP's claim is "the
         static eval is so far above beta that a swing of X cannot matter" — and
         X is currently a constant, when the decomposition already says how
         swingy this position is. Uses an eval the node has *already computed*,
         so the experiment costs one formula. Do this one first.
      2. **Reduce less when volatile, more when stable.** A principled version
         of what `improving` approximates.
      3. **Null move gated on the mobility subtotal** rather than piece counts —
         zugzwang is a mobility fact, and we have the number.
      Worth doing even at modest Elo: it inverts the project's usual trade, where
      interpretability is a constraint that costs strength. Here the explanation
      is *why* the search is better. Note the five dead move-ordering experiments
      above — this is not ordering, it is pruning policy, which is where the
      accepted search gains (LMR, RFP, aspiration) have all come from.

## Test/benchmark infrastructure

- [x] Harder tactics suite v2 (s11: 30 pos @ SF depth 22, gap ≥250; gate runs at
      0.25s where baseline is 29/30 — at 1s even v2 is saturated). Next iteration
      needs multi-move quiet tactics, not deeper verification of 1-move wins
- [x] ~~Eval agreement with Stockfish~~ (session 2: built as eval-loss metric; good concept
      screen, bad tuning target) — [ ] move-agreement-at-fixed-nodes metric instead
- [x] Ladder-anchor MLE fit is now a script (research/ladder_anchor.py, reproduces
      all committed anchors) — [x] **automated ladder runner: `research.calibrate`
      (s25)**. Plays the SF anchors, fits by ML with a proper trinomial draw model
      (ladder_anchor treated a 0/0.5/1 score as a binomial — draw-blind), reports a
      profile-likelihood CI *and* a paired bootstrap CI, and appends every run to
      `research/data/elo_history.json`. Estimator is unit-tested against simulated
      ladders (`tests/test_calibrate.py`: recovery + 95% coverage)
- [x] Parallel gating: `research.match --concurrency N` (s25 validated at N=8 on a
      10-core box: 400-game A-vs-identical-A scored 51.0%, paired +7 Elo
      [−19,+33] — no detectable harness bias, 7.75× CPU utilisation)
- [ ] Fold `elo_history.json` into `research/elo_timeline.py` so the forward
      series and the hand-built historical anchors plot on one axis
- [ ] Re-gate the borderline-ACCEPTED search features (singular extensions +29
      CI[−7,+66], null-move R tier +29 CI[−6,+64], LMP +30 CI[+0,+60]) now that
      600–800-game gates cost ~40 min instead of ~5 h — convert "borderline" into
      confirmed or removed
- [ ] Game-phase-specific benchmarks (endgame play is a known weak spot for shallow searchers)
- [ ] Explanation quality checks: does the stated top concept delta actually track the
      move choice? (e.g., ablation: remove top concept, does move change?)


## The tree (s33 onwards) — where the remaining Elo actually is

Measured, not assumed. Against Stockfish 11 head-to-head: **+0 =8 -192 (2.0%,
-676 Elo)** at 0.3s, with an evaluation in SF11's class (-2.96% outcome loss)
and 1.26x of its speed. So the gap is neither knowledge nor NPS. It is the tree:

    nodes to nominal depth 15   2,096,933 vs 394,273    5.3x
    per-ply growth rate         1.82 vs 1.80            the same
    first-move beta cutoffs     88.82%, mean index 1.347
    quiescence share            44.4% of nodes          normal

A uniformly fatter tree at an identical growth rate, with ordering already good
and quiescence already normal, points at one thing: the reduction schedule. Ours
is flat in depth — `if(i>=12) red=3; else if(i>=3) red=2` — so depth 4 move 12
and depth 20 move 30 are reduced identically.

**Why this is worth the effort.** Closing the tree gap entirely is ~2.4 plies
(5.3x at EBF 1.82), and plies at this level are worth roughly 40-60 Elo each
early on. Even capturing half of it is the largest block of Elo this project has
had a credible route to since the RFP/ProbCut/IIR era. It is also the only seam
left with evidence behind it.

Sequence, single hypothesis per gate, external paired gates only:

- [ ] **cut-node reduction** — reduce +2 at nodes the parent expects to fail
      high. Implemented; -30.4% nodes at fixed depth; in gate.
- [ ] **depth-scaled LMR table** — `0.5 + ln(d)*ln(m)/2.25`, replacing the flat
      schedule. Built and validated (`research/worktrees/cl`), stacked on
      cut-node. The previous rejection of a log table predates cut-node
      awareness, and the two interact: cut nodes are where reduction is cheapest.
- [ ] reduction adjustments that need the above first: reduce killers and
      countermoves less, reduce more when the TT move is a capture, less when the
      move gives check
- [ ] re-tune LMP thresholds under the new schedule (they were fitted against the
      old one, so they are now measuring a different tree)
- [ ] revisit razoring and SEE pruning, both previously "neutral, overlaps
      futility" — that overlap changes once the tree is thinner

Closed, with the measurement that closed it:

- [x] ~~new evaluation terms~~ — matches SF11's classical eval; the 16.94% gap is
      to an NNUE and is uniform across all buckets (`research/eval_room.py`)
- [x] ~~evaluation capacity (king-relative / HalfKP-style tables)~~ — +1.249% on
      a position split, **-0.925% on independent games**; the gain was the split
      (`research/screen_capacity.py`)
- [x] ~~move ordering~~ — 88.82% first-move cutoffs, mean cut index 1.347
- [x] ~~eval-hash keying~~ — stripping castling/ep is provably correct and buys
      +0.167pp of hit rate, ~0.06% of runtime


## Interpretability / product

- [ ] Show top alternative moves + why they were rejected (root move scores are nearly free)
- [ ] Per-move "surprise" indicator (eval swing vs previous expectation)
- [ ] Human-tunable personality (slider scales concept weights live in GUI)

## Next phase: where the remaining ~450 Elo actually lives

Stockfish 11 is ~3450 in the same model class this project is restricted to --
hand-crafted, fully interpretable, no neural network. This engine measures
**3003 [2985, 3021]**. That gap is not a mystery and it is not closed; what is
closed is the class of change session 33 attempted (parameter nudges, reduction
schedules, ordering heuristics, redundant-work elimination), every one of which
was worth single-digit Elo at best and most of which measured zero.

Three structural differences explain most of the gap, in dependency order.

### A. Eval CAPACITY: scalars where Stockfish has tables

This engine has **64 scalar weights** plus piece-square tables. SF11's classical
evaluation carries on the order of a thousand tuned values, and the difference is
mostly SHAPE, not count:

    ours                              SF11
    mobility = w_piece * count        Mobility[piece][count]  -- a table per piece
    pawn.passed_scale (one multiplier) PassedRank[rank] x blocked/supported/path
    threat.minor / threat.rook        Threat[attacker][victim] pairs
    king danger: already a table       (this one we already do properly)

A linear term cannot express "a knight's 4th move is worth more than its 8th",
which is the actual shape of mobility. Every one of these stays fully
interpretable as a table -- "a bishop with 7 moves scores +18" is a sentence the
GUI can print, exactly like the fitted king-danger curve already is.

This is the largest single lever and the one most aligned with the project's
constraint. It also has a precedent inside this repo: replacing the forced
`scale * units^2 / 10` king-danger formula with a FITTED CURVE was one of the
few eval changes that paid.

Prerequisite: far more tuning data (see C), because tables have more parameters
than scalars and will overfit 283K positions.

### B. Eval SPEED: incremental and integer

Evaluation is ~46% of runtime (eval_core 31.9%, eval_stm 13.8%), and everything
beyond material is 28.4%. SF11 does MORE eval work per node and is not slower,
because of two structural choices this engine does not make:

  * **material and PST maintained incrementally** in make/unmake, instead of
    recomputed from bitboards every call
  * **packed Score** -- middlegame and endgame in one 32-bit int, so one add does
    both phases -- against this engine's `double` arithmetic throughout

Note the caveat already on record: a probe replacing `TAP` with a single multiply
measured **-2.58%**, because `(MG)==(EG)` is a COMPILE-TIME test that folds half
the terms to constants. So packed Score only pays as part of the incremental
rewrite, not as a drop-in.

Why this matters beyond its own Elo: the blunder classifier puts **75.3% of real
mistakes at search-limited**, i.e. fixed by depth, and depth comes from NPS. And
speed is the BUDGET that direction A has to be paid for -- every new table costs
eval time, and bundle E was already killed by -4.62% NPS against +3.8 Elo of
knowledge.

### C. Tuning DATA and scale

`texel6.jsonl` holds 283K positions. Classical engines of this strength were
tuned on orders of magnitude more, and the fits here have been converging
against that limit for several sessions -- the last one moved the loss +0.134%
and screened WORSE on move quality.

Needed before A can work:
  * generate millions of self-play positions, from an independent run (the LOG
    already records that position-level splits leave the same game on both sides
    and turned -0.9% into +1.2%)
  * a proper train/validation split by GAME, not by position
  * refit K per candidate; the LOG records a boundary-solution K that overstated
    every bundle before it by ~25%

### D. Search parameters, tuned at scale

Every search constant here was set by hand and checked against a gate resolving
+/-25 Elo, which cannot see what a single margin is worth. SPSA over the whole
parameter vector with thousands of games is how engines of this strength tune
them. This is compute-hungry rather than clever, and it is the standard way the
last 30-50 Elo gets found.

### Sequencing

B first (it is self-validating on node counts and buys the budget for A), then C
(A cannot be fitted without it), then A, with D running continuously in the
background once the gate is cheap enough to support it.

### What NOT to retry

Recorded in CLAUDE.md with numbers: tree thinning (six mechanisms, the sharpest
halved the tree and cost 33 Elo), move ordering (continuation history at the
right size, t=0.52), lazy evaluation (safe margin needs >564cp), eval-hash and TT
sizing, SMP diversification, PGO (+2.3%), redundant static-eval probes (provably
zero). And do NOT "fix" the `see()` king selection -- correcting it to match the
Python reference gated at **-22.5 Elo**, because the search is tuned around it.

### C is blocked by TUNER THROUGHPUT, not by data availability

The data exists -- `texel_all.jsonl` holds ~382K positions and more can be
generated. What does not exist is a tuner that can consume it.

`research/texel.py` evaluates every position through the PYTHON evaluation on
every candidate step. Coordinate descent over N parameters costs roughly
`2 * N * passes` full sweeps of the dataset, so:

    66 params, 10K positions      ~10 minutes      (and overfits badly)
    66 params, 80K positions      hours
    66 params, 382K positions     days
    500 params, millions          not reachable at all

That is the actual ceiling on direction A. Mobility alone adds 66 parameters;
doing the same for passed pawns, threats and the piece-square tables is several
hundred, against the millions of positions needed to fit them without
overfitting. The first mobility fit demonstrated the failure mode directly:
**+1.566% loss on 10K positions and a WORSE independent screen** (d_mean +1.242,
t 1.79).

Three ways out, in increasing order of work:

  1. **Analytic gradients.** The Texel loss is a sigmoid over a LINEAR
     combination of concept scores, so the gradient with respect to each weight
     is available in closed form from one sweep. That replaces `2*N*passes`
     sweeps with `passes` sweeps -- a factor of ~130 at N=66, and it improves
     with more parameters rather than degrading.

  2. **Cache the per-position concept vector.** Every weight is a coefficient on
     a quantity that does not depend on the weights (a mobility count, a pawn
     structure feature). Extract that vector ONCE per position and the fit
     becomes linear algebra over a fixed matrix instead of repeated evaluation.
     This is how classical tuners are actually built, and it makes millions of
     positions routine.

  3. Move the evaluation into C for tuning, which conflicts with the weights
     being compile-time `#define`s and would need them made runtime parameters.

(2) subsumes (1) and is the right target. It also does not disturb the engine at
all -- it is a research-harness change, and `eval_check` keeps the compiled eval
honest independently.

**Until the tuner can consume the data, direction A cannot be tested, only
badly fitted.** That is the single most valuable piece of infrastructure work
outstanding, and it gates the largest remaining source of Elo.

### What the shape tests found: capacity is not the missing thing

Direction A assumed the gap to Stockfish is largely SHAPE -- scalars where SF11
has tables. Two tests now say otherwise for this evaluation.

**Mobility.** Converted to a per-count curve, 66 free parameters, fitted with a
held-out split and L2 toward the linear seed. It fits back to a straight line
(knight: -15.7, -11.9, -7.6, -4.2, -0.2, 4.2, 8.1, 11.6, 15.6 -- steps of ~3.9)
and the holdout gain is **+0.008%**. Linear was already right.

**Passed pawns.** Inspected before implementing:

    PASSED_BONUS = [0, 8, 12, 19, 38, 67, 120, 0]

The rank shape is ALREADY strongly non-linear, roughly doubling per rank, and
only its magnitude (`pawn.passed_scale`) is fitted. The curve a table would have
to discover is already there, hand-crafted and sensible.

**The pattern.** Where this evaluation uses a fixed table times a fitted scalar,
the table is usually a reasonable shape and the scalar is the part that was
tuned. King danger is the same -- already a fitted curve, and one of the few eval
changes that ever paid. So the "scalars where SF has tables" framing overstates
the opportunity: the shapes are mostly present, just not individually fitted.

That reprioritises direction A. The remaining capacity is not in re-shaping
terms that already have shapes; it is in TERMS THAT DO NOT EXIST -- SF11 carries
evaluation concepts this engine has no counterpart for at all. Identifying those
is an eval-room question (`research/eval_room.py` measured -2.96% against SF11's
classical eval with the deficit spread EVENLY across every bucket, which is the
signature of a model-class gap rather than a missing term) and it is the honest
open question.

The fitting machinery built for these tests (`research/fastfit.py`,
`research/fitcurve.py`) stands regardless: any term linear in its weights can now
be extracted once and fitted in seconds against a holdout. That is what makes
the next capacity question cheap to ask, whatever it turns out to be.

## In-search tablebase probing — scoped, not started

The last unexecuted idea with plausible size (+3-8 Elo), and the games-needed
scaling makes it worth real hours: at 3007 a decisive rating run is ~4,890 games
and 5 days; at 3013 it is ~1,418 games and 1.5 days, because games needed scale
as 1/margin^2 against the 3000 threshold. Six Elo buys back three and a half days
of measurement.

It is also the only remaining mechanism that thins the tree by ADDING exact
information rather than discarding it on a margin — the class that has not failed
here, unlike the seven thinners that have.

**Measured opportunity** (research/tbcount.py): from book openings at depth 12,
**0.0000%** of 8.94M nodes have <=5 pieces — reaching five pieces needs ~20
captures, which no depth-12 tree performs. From real 7-10 piece endgames at
depth 16, **29.5%** of nodes are <=5 pieces (58.4% at <=7). So the value is
confined to genuine endgames, and narrower still because the ROOT already probes:
in-search probing only adds value for 6-10 piece roots whose search descends
below five. Hence +3-8, not the +10-20 that published figures suggest for engines
without root probing.

**Port scope.** Tables are 3-4-5 man at ~/syzygy345 (confirmed present). Source
to adapt: ~/sf11/src/syzygy/tbprobe.cpp, 60KB / ~1600 lines, with 51 references
to Stockfish internals (Position, Bitboard, MoveList). A WDL-only port narrows
that considerably — in-search probing needs probe_wdl only, not the DTZ path or
root_probe, which is where most of the MoveList dependency lives. Required from
our Board: piece bitboards bb[2][6], side to move, ep square, halfmove clock.

**The risk that decides how to do this.** A subtly wrong prober returns
CONFIDENTLY WRONG scores and corrupts the search worse than having no tablebases
at all. Validate before wiring:

  1. probe every position in a 5-man suite and compare against python-chess
     chess.syzygy (pure Python, slow, but correct). Require exact WDL agreement
     on tens of thousands of positions, not a spot check.
  2. only then wire into negamax, gated on popcount(occ) <= 5 and no castling
     rights.
  3. confirm the tactics suite is unchanged and eval_check is still 0.000000 —
     it must be, since this touches search rather than evaluation, so
     interpretability is structurally unaffected.
  4. two-anchor gate as usual; screen first on research/screen_isonode.py at a
     depth where the rule can fire, which for tablebases means endgame positions,
     NOT the book-opening calibration set where 0.0000% of nodes qualify.

Do this in a fresh session with full context, not at the tail of one. Half a
prober is worse than none.

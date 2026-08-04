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
- [ ] **Concept-aware search control — the one idea only this engine can try.**
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

## Interpretability / product

- [ ] Show top alternative moves + why they were rejected (root move scores are nearly free)
- [ ] Per-move "surprise" indicator (eval swing vs previous expectation)
- [ ] Human-tunable personality (slider scales concept weights live in GUI)

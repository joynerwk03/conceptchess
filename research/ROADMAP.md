# Research roadmap

Hypothesis backlog, roughly ordered by expected value. Check off with a LOG
entry reference; add new ideas as they come up.

## Speed (deeper search = biggest strength lever in pure Python)

- [ ] Profile eval + search (`cProfile`); find the top 3 hot spots before optimizing anything
- [ ] Replace `board._transposition_key()` with incremental zobrist hashing
- [ ] Cache pawn-structure/king-safety by pawn hash (pawn config changes rarely)
- [ ] Faster mobility: reuse attack masks between eval and move ordering, or approximate
- [ ] Aspiration windows at the root
- [ ] Principal variation search (PVS / zero-window re-search)
- [ ] Late move reductions (LMR) — likely the single biggest depth win
- [ ] Futility pruning at shallow depths
- [ ] Static exchange evaluation (SEE) for qsearch pruning + ordering (replaces MVV-LVA blunders)
- [ ] Evaluate porting the hot loop to a compiled extension **only if** the concept
      design has stabilized (keep concept semantics defined in Python/spec)

## Evaluation accuracy (better judgment per node)

- [ ] Tune concept weights systematically (e.g., Texel tuning against game outcomes) —
      weights stay per-concept, so tuning preserves interpretability
- [ ] King safety: attack-unit model (count attackers/weight by piece type near king)
- [ ] Passed pawns: blockade detection, king proximity in endgame, connected passers
- [ ] New concept: threats/hanging pieces (statically detect en prise material)
- [ ] New concept: space (advanced-square control behind pawn chains)
- [ ] Knight outposts (in piece_activity)
- [ ] Endgame knowledge: wrong-bishop draws, KX vs K mop-up term to actually finish games
- [ ] Tempo/initiative refinement

## Search quality

- [ ] Qsearch: include checks at first ply of quiescence
- [ ] Mate-distance pruning
- [ ] Repetition-aware TT (avoid TT cutoffs masking repetition draws)
- [ ] Better time management (spend more on unstable root evals)

## Test/benchmark infrastructure

- [ ] Harder tactics suites: current suite is 96% at 1s (mostly captures). Mine
      quiet-move and deeper suites (`--depth 20+`, exclude bm-is-capture positions)
- [ ] Positional test suite: measure eval agreement with Stockfish eval sign on quiet positions
- [ ] Automated Elo ladder script: current vs last-N-accepted commits, tracked in baselines.json
- [ ] Game-phase-specific benchmarks (endgame play is a known weak spot for shallow searchers)
- [ ] Explanation quality checks: does the stated top concept delta actually track the
      move choice? (e.g., ablation: remove top concept, does move change?)

## Interpretability / product

- [ ] Show top alternative moves + why they were rejected (root move scores are nearly free)
- [ ] Per-move "surprise" indicator (eval swing vs previous expectation)
- [ ] Human-tunable personality (slider scales concept weights live in GUI)

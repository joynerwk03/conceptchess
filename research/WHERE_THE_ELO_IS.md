# Where the remaining Elo is — a bound, not a wish list

Written 2026-08-04, after Phase 3 produced four measured bundles, one measured
external gate, and therefore for the first time a way to *bound* what evaluation
work can still buy. `research/SCHEDULE.md` listed what Stockfish 11 has that we
do not. This asks the harder question: of the ~690 Elo between us and it, how
much is reachable by which kind of work.

## The bound that changes the plan

Two measured facts:

1. **The stack's 2.683% outcome-loss reduction gated +15.0 Elo externally.**
   Net of its own 3.9% NPS cost, that is ≈5.6 Elo per 1% of loss.
2. **Our loss is 0.091, and most of it is irreducible.** The Texel target is
   `(sigmoid(eval/K) − result)²`, and even a *perfect* evaluation — one that
   returns the true win probability — leaves the variance of the game outcome
   around that probability. For positions with win probabilities in the range
   this data covers, that floor is somewhere around 0.07–0.08.

So the total loss available to *any* evaluation, however good, is roughly
12–25%. At 5.6 Elo per 1%:

> **Evaluation work has a ceiling of roughly +70 to +140 Elo from here — and
> that is the ceiling for a perfect evaluation, not an achievable target.**

Phase 3's four bundles delivered 2.7% between them, and two of the four were
worth nothing. Grinding out the rest of Stockfish 11's term list might find
another 2–3%, or ≈+15 Elo. **It cannot find 690.**

**Therefore the remaining gap is search and speed.** This is not a new idea in
this project — it is what its own history already said and what the ROADMAP
status note has said since s25 — but it is now quantitative rather than a hunch.
The two largest gains ever recorded here were the C port (+380) and Lazy SMP
(+96). Both were speed. The five move-ordering experiments that failed were not.

## Where our per-node cost goes, structurally

Stockfish 11 runs several times our NPS *while evaluating far more*. The
difference is not cleverness in the terms, it is arithmetic:

| | Stockfish 11 | ConceptChess |
|---|---|---|
| eval arithmetic | packed `int32` holding (mg, eg) as two `int16` | `double` throughout |
| material + PST | **maintained incrementally** on make/unmake | recomputed by looping all 32 pieces, every leaf |
| phase | incremental | recomputed |
| attack tables | computed once, reused | computed once, reused (we fixed this) |

The `double` choice is load-bearing for this project and should stay: it is what
makes "the C eval equals the Python eval to 0.000000" provable, and that
invariant is the whole point. Packing to int16 would break it.

**But incremental material and PST costs nothing in faithfulness.** The value is
identical; only when it is computed changes. That makes it the rare thing this
project likes most: a change validated by *byte-identical node counts at fixed
depth* plus `eval_check` 0.000000 — **zero games**.

## The experiments, in priority order

## The profile, measured 2026-08-04 — and it changed the plan

Cumulative early-return probes: insert `return s;` before a section, measure
NPS, difference consecutive probes. Shares are of **total search runtime**, not
of eval time. Consecutive rows disagree by up to ~0.8% where they should be
monotone, so read each figure as ±1.

| section | share of runtime |
|---|---|
| **pawn structure** | **~9.0%** |
| piece placement (PST) | ~5.0% |
| piece activity | ~3.5% |
| king safety + king attack | ~3.1% |
| imbalance + space | ~2.6% |
| mobility | ~1.2% |
| tempo, threats, mate drive | ~4.7% |
| **everything except material** | **28.3%** |

And separately, the probe that matters most for the plan below: **growing
`Board` by 96 bytes costs 2.3% NPS on its own**, measured by adding unused
padding. The search is copy-make — `Board c=*b` at every node — so any
incremental scheme pays that before it saves anything.

**That kills experiment 1 as designed.** Incremental material+PST could remove
at most the 5.0% PST costs, minus 2.3% for the bigger struct, minus the
make() update cost — call it 2.5% net, ≈+2 Elo, for a large change touching the
hottest code in the engine and needing ~12 accumulators kept exactly in sync.
Bad trade. *Written before the profile ran, and wrong; the profile is why it
cost twenty minutes instead of a day.*

**The real target is pawn structure, at ~9%** — the single most expensive
section, and the one place where the C core is doing work the Python reference
already knows how to avoid.

## Result: the pawn hash was built, measured, and REJECTED (2026-08-04)

Implemented as designed below — caching sets, not scores; iterated ascending so
the float additions happen in the original order. The validation worked exactly
as intended: `eval_check` 0.000000 and **byte-identical node counts (413621 both
sides)**, proving the evaluation was bit-for-bit unchanged, with no games played.

Then the speed measurement:

| | avg NPS |
|---|---|
| single run, main | 1,241,377 |
| single run, pawn hash | 1,254,503 (**+1.06%**) |
| **three-run mean, main** | **1,253,217** |
| **three-run mean, pawn hash** | **1,240,398 (−1.02%)** |

**One run said +1.06%, three runs said −1.02%.** The truth is zero, and the
first number was noise of exactly the size of the effect. Rejected. (Also
hoisted two `lsb()` king lookups out of the innermost passer loop while there —
free, and still no measurable gain.)

**Why it failed, which is the useful part.** The 9% that section costs is not
*detection* — the passer scan, the backward conditions, the connected tests are
all cheap bitboard work, and caching them buys nothing against the cost of a
hash probe and a 640KB table that pushes real data out of L2. The 9% is the
**double-precision arithmetic**: `TAP()` evaluations and float multiplies, spread
across every passer and every file. That cannot be cached away, because it *is*
the value.

**So the eval-speed direction is much smaller than the section profile implied,
and now has a hard bound.** Deleting every positional term outright gains 28.3%
NPS ≈ +20 Elo. Any real optimisation gets a fraction of that. Stockfish's answer
is packed `int32` (mg, eg) arithmetic instead of doubles — and that is precisely
the thing this project cannot do, because "the compiled eval equals the Python
eval to 0.000000" is the interpretability guarantee and integer rounding would
end it.

**That is a genuine, quantified cost of the project's core premise: roughly 20
Elo of headroom is spent buying provable faithfulness.** Worth it, and worth
knowing the price. Speed work should now go to the *search*, not the eval.

### 1. ~~Incremental material + PST accumulators~~ → ~~pawn hash in the C eval~~ (REJECTED, above)

`engine/concepts/pawn_structure.py` caches its expensive part keyed on the pawn
skeleton, and has since session 1 (it was worth 51.4k→55.1k NPS then).
**`core/ceval.c` has no such cache and recomputes the whole thing every call.**
The existing eval hash in `csearch.c` does not help here: it is keyed on the
full position, so it only hits on transpositions, whereas a pawn skeleton is
shared by enormous numbers of distinct positions — which is exactly why pawn
hashing is standard in every classical engine.

- Cache the pawn-only part (doubled, isolated, backward, connected, passer
  list); apply blockade, king-distance and rook-behind terms outside, exactly
  as the Python does.
- **Key on (white pawns, black pawns, PHASE.)** Phase is not optional: the
  tapered weights made those terms phase-dependent, and leaving phase out of a
  pawn-keyed cache is the 17.7cp bug this session already fixed once, in the
  Python. Do not reintroduce it in C.
- Validation: `eval_check` 0.000000 **and byte-identical fixed-depth node
  counts** — the value is unchanged, only when it is computed. No games.
- No `Board` growth, so no 2.3% penalty; the table is global and thread-local.
- Plausible: most of 9%, so ~6–7% NPS, ≈+5 Elo. Modest, but honestly measured
  and nearly free to validate.

### 1b. (superseded) Incremental material + PST accumulators  (speed; no-op output)
Keep running `(mg, eg)` accumulators on the Board, updated on make/unmake and
on promotion/capture. `eval_core` reads them instead of looping every piece.
The pawn and king tables interpolate by phase, so the pair must be kept
separately and combined at the leaf — exactly what `make_score` does in SF.

- **Validation: fixed-depth node counts must be byte-identical, `eval_check`
  0.000000.** No games needed to prove correctness; a benchmark measures the win.
- Expected: material + PST is the largest single block in `eval_core` and runs
  at every leaf. If it is ~30–40% of eval time and eval is ~half of runtime,
  this is 15–20% NPS, ≈+10–20 Elo.
- **Measure first**: profile `eval_core` before assuming which block dominates.
  This project has been wrong about that before (time-to-depth, the volatility
  premise), and the profile costs minutes.

### 2. Whatever the profile says is next  (speed; no-op output)
Same class, same validation. Candidates if the profile points there: the
per-piece attack loop, the threats double pass, the pawn-structure cache key
(now larger since it includes phase).

### 3. History-scaled LMR reduction  (search shaping)
SF reduces less for moves with good history and more for bad
(`r -= statScore / 20000`). We reduce by a table of depth and move index only.
**This is not move ordering** — five ordering experiments have failed here and
the lesson was "stop trying to improve ordering". It is *pruning policy*, which
is where every accepted search gain has come from (LMR, RFP, aspiration
windows). The history tables already exist; only the reduction formula changes.

### 4. Endgame scale factors  (the one eval dimension still genuinely missing)
`research.firing_rate` reports our single multiplicative modifier,
`ocb.draw_scale`, firing in **0.0%** of real positions. So the whole dimension of
*drawishness independent of who stands better* is nominally present and
practically absent: rook endings a pawn up that are drawn, opposite-coloured
bishops, wrong rook-pawn, insufficient material to convert an advantage.

This is the one remaining candidate my own Phase 3 prior predicts should pay,
because it **adds a dimension** rather than refining a judgement — and A and D,
the two bundles that added dimensions, were worth 8× the two that refined. It is
also multiplicative and highly interpretable ("this ending is drawish: ×0.4"),
and it composes with the Syzygy work already in place.

Screen on loss first, as with B and D. If it comes in under ~0.3%, drop it
without writing a C mirror.

## What not to do

- **More Stockfish 11 term bundles.** B and C measured 0.113% and 0.117%. The
  term list is not the bottleneck and the bound above says it cannot be.
- **More move-ordering work.** Five failures; the ROADMAP already says stop.
- **Anything gated at fewer than ~1600 paired slots.** A gate that cannot
  resolve the effect it is testing returns "neutral" regardless of the truth,
  which is what happened three times before this session measured the
  resolution.

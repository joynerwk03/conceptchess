# What interpretability actually costs, and the smallest useful relaxation

Written because the project has reached a measured wall: the engine sits at
~3000-3002 against `stockfish:3000` and 22 candidates have closed with no
confirmed gain. The remaining options are more compute or relaxing the
interpretability constraint. This document exists so that second option can be
judged on numbers rather than on vibes. **Nothing here is implemented, and the
constraint is not relaxed.**

## The invariant, stated precisely

`evaluate(board)` == `evaluate_detailed(board).total` == the compiled C eval, and
every concept's `details()` sum to its `score()`. The search optimizes exactly
the number the GUI explains. That is the project's defining property.

Note what it does NOT cover, because this matters for costing: **terminal values
returned by the search have always been outside it.** Mate scores, draw scores,
tablebase results, contempt and the KPvK bitbase all bypass `evaluate()` without
violating the invariant, because they replace the evaluation rather than modify
it. That boundary is already established and was used three times this session.

## What the constraint has measurably cost

Two things, both measured rather than asserted.

**1. The eval is at a model-class ceiling.** `research/eval_room.py` puts this
engine at **-2.96%** against Stockfish 11's classical eval and **+16.94%**
against an NNUE, with the NNUE gap spread evenly across every bucket
(10.8-24.9%). A uniform deficit across all buckets is the signature of a model
class limit, not a missing term. Nine hand-picked concept bundles measured zero,
and 1920 parameters of king-relative interaction transferred negatively.

**2. Eval fitting is closed, on two independent targets.** Tapering fitted on
382K positions with a real holdout gained +0.339% and screened WORSE.
Relabelling every position with SF11 lifted the held-out gain to **+9.007%**, a
26-fold improvement, and screened **exactly neutral**. A 26x better fit bought
nothing, which says eval loss does not predict move quality here at all.

Downstream, this is what closed the search side too: seven thinning mechanisms
gated null or negative, and the decisive one isolated the deep region, cut the
depth-14 tree 30.6%, bent the EBF down exactly as designed, and still lost
17-32 Elo. **Pruning accuracy is bounded by eval accuracy**, so the fat tree is a
symptom of the eval ceiling rather than an independent problem.

## The smallest useful relaxation: correction history

Standard in modern engines and worth real Elo. It records, per position feature
(typically pawn-structure hash and material key), the historical difference
between the static eval and what search actually returned, then corrects the
static eval by that running average.

**Why it is excluded today:** the corrected value is what search optimizes, and
the explanation layer reports the uncorrected concept sum. The two diverge, so
`eval_check` fails by construction and the defining property breaks.

**Why it is the *smallest* relaxation:** the correction is a single scalar per
position, derived from the engine's own search history. It adds no opaque terms,
no learned weights over board features, no neural component. Every named concept
keeps its name and its value.

**What it would plausibly buy:** engines that added it report roughly +10 to +20
Elo. That is squarely the size of the gap. It is also the one mechanism that
attacks the measured bottleneck directly -- it improves static eval accuracy
using information the search already generates and currently discards, which is
the class of change that has worked here (contempt, KPvK) rather than the class
that has not (margin tuning, missing standard mechanisms).

**What it costs, honestly:** the GUI could still show the concept breakdown and
additionally report "search-history correction: -18cp", which is arguably an
*honest* explanation of what the engine is doing. But it is no longer true that
the explanation IS the number optimized; it becomes the explanation PLUS a
correction term whose value comes from search statistics rather than from chess
concepts. Whether that is acceptable is a judgement about the project's purpose,
not a technical question, and it is not mine to make.

## A middle option worth considering

Correction history could be applied **only inside the search's pruning decisions**
(reverse futility, null move, futility margins) while the value returned to the
root, stored in the TT, and shown in the GUI stays the pure concept sum. The
search would prune using a better estimate while still *reporting* the
interpretable number.

This preserves the letter of the invariant for everything the user sees. It
weakens the spirit: pruning decisions would be made on a number the explanation
does not report. Given that this session measured eval error at **1.71x** higher
in positions dominated by non-material judgement, a correction that shrinks that
error is exactly where pruning accuracy would improve.

Expected value is lower than full correction history, since the root score and
move choice still come from the uncorrected eval, but it is nonzero and the
interpretability cost is much smaller. Worth pricing before committing to the
full version.

## The alternative: more compute

Purely a resource question, with no constraint cost. Measured: `se ~ 350/sqrt(N)`
Elo, so proving a +5 Elo change needs ~19,400 slots, one to three days per
candidate on this machine. Fishtest uses hundreds of machines for exactly this
reason. With 10-20x this throughput the existing closed candidates would not
reopen -- they are closed on direction, not on precision -- but small genuine
gains could be found and confirmed at a rate that makes stacking several
realistic.

## Recommendation

If the interpretability property is the point of the project, **stop at ~3000**
and record it as a measured ceiling for this architecture. That is a real
result: it quantifies what a fully interpretable concept-sum evaluation costs
against a hand-crafted classical engine of the same era, and the measurement is
unusually well instrumented.

If the 3000 number is the point, the middle option above is the cheapest
credible route, and it should be priced before the full relaxation is
considered.

## Update: the middle option was tested, and it loses

The middle option above -- correction history applied only to pruning decisions,
with the returned score, TT, PV and GUI all keeping the pure concept sum -- was
implemented and screened. `eval_check` stayed 0.000000, so the interpretability
boundary held exactly as designed.

It reads **d_mean +3.835, t 2.22** on the iso-node screen, against a calibration
anchor at +3.122 that corresponds to a known -33 Elo. It is worse than that
anchor, and it is the only |t| above 2 result in the session, so this is a
decisive rejection rather than a null.

That weakens the central argument of this document. Correction history was named
here as the strongest case for relaxing the constraint, worth a reported +10 to
+20 Elo elsewhere. The nearest interpretability-preserving form of it is clearly
negative in this engine. That is not proof the full version would also fail --
the full version corrects the value returned and propagated, not merely the
pruning threshold -- but it removes the easy assumption that the mechanism
transfers here, and it was produced by testing my own recommendation rather than
by argument.

Possible reasons it fails, none tested: the correction is learned from search
results at the same nodes, which is a feedback loop; pawn-structure bucketing may
be too coarse, with 16384 buckets shared across very different positions; or the
exponential moving average may be too aggressive.

**Revised recommendation.** The case for relaxing interpretability is weaker than
this document originally stated. Stopping at ~3000 and recording it as a measured
architectural ceiling is now the better-supported option.

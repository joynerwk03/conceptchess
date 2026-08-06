# The road to 3000

Target set 2026-08-04. Written as a budget rather than a wish list, because
most of the terms can now be bounded from measurements rather than guessed.

## Where we are

| measure | Elo | source |
|---|---|---|
| single thread, 0.3s fixed | ~2750 | anchor arms: +64 and +43 over SF 2700 in two batches |
| **as played, MEASURED** | **2839 [2794, 2889]** | **150 games at 10s+0.1, all 10 cores, concurrency 1, +80 =47 −23 (69.0%) → +139 over the anchor** |

**2026-08-05: the as-played rating is now measured rather than derived.** Every
previous figure was single-thread-at-fixed-movetime plus the +96 that Lazy SMP
measured in s20 — a sum of two numbers taken under conditions the engine never
plays in. This is the engine as it actually plays: a real clock, its own time
management choosing each move's budget, every core. It lands on **2839**, which
is where the derived estimate already sat. Two quite different roads to the same
number is the best evidence available that the anchor-relative scale is sound.

A note on cost, because it governs what can be tested here: **150 clock games at
concurrency 1 took 69 minutes**, and concurrency cannot be raised — the engine
runs one thread per physical core, so parallel games measure contention rather
than strength (the first attempt put 40+ threads on 10 cores). Resolving ±20 Elo
under a clock therefore costs about four hours. Clock-gated work must be
batched accordingly.

**Target 3000 as played ⇒ +148.** (Single-threaded 3000 would be +250 and is not
the right target — the engine plays with all cores.)

All figures are UHO-anchor-relative. The two baseline arms in one session
differed by 21 Elo purely from which openings they drew, so treat ±25 as the
honest uncertainty on any absolute number here. **Paired deltas are what this
project measures well; absolute ratings are a locator.**

## The budget, with bounds where they exist

| lever | realistic | basis |
|---|---|---|
| remaining evaluation terms | **+30 to +50** | *bounded*: a perfect eval is +70–140, and Phase 3 already took 2.7% of the ~12–25% of loss that is reducible at all |
| evaluation speed | **≤ +20, likely ~0** | *bounded*: deleting all positional eval gains 28.3% NPS; the first attempt (pawn hash) measured −1.0% |
| **tablebases inside the search** | **+20 to +40** | currently **zero** TB knowledge below the root — the whole tree is blind to 5-piece ground truth |
| search pruning / reductions | +0 to +40 | historically the productive area (LMR, RFP, aspiration all landed); also the least bounded |
| SMP scaling beyond +96 | +10 to +30 | untouched since s20; helper diversity and depth-preferred TT replacement never tried |
| time management under a real clock | +10 to +30 | invisible to fixed-movetime gates by construction, so never measured; the harness has `--clock` |
| opening book | +10 to +20 | real play only — UHO gates start from a book position and cannot see it |

**Optimistic sum ≈ +80 to +230.** So 3000 is reachable but sits at the upper half
of that range: it needs most levers to pay, not one breakthrough. Anyone claiming
a single change gets there is guessing.

## What this session proved about *how* to spend the effort

1. **Accumulate, then gate once, at a size that can resolve the prediction.**
   Three changes worth ≈+6 to +9 each are invisible to an 800-game gate and
   produced three "neutral" entries in past logs. Stacked and gated over 3200
   slots they measured +12.8 with p = 0.032.
2. **Screen on outcome loss, not games.** Minutes instead of an hour, and it
   resolves 0.1% where a gate resolves 2.2%. Two bundles were killed for free.
3. **Predict before gating.** The +15 forecast was registered in advance and
   confirmed twice; that is what made a 1.5-sigma result trustworthy.
4. **Measure the mechanism's cost before building it.** A 96-byte-bigger `Board`
   costs 2.3% NPS — which killed incremental PST in twenty minutes instead of a
   day.
5. **Three runs, not one.** The pawn hash read +1.06% on one benchmark and
   −1.02% on three.

## The arithmetic is getting tight — and what that implies

Two of the seven budgeted levers are now **closed by measurement**, not by
running out of ideas:

- **Evaluation speed.** Pawn hash byte-identical and −1.0% NPS; incremental PST
  killed by a 2.3% struct-copy cost. Deleting *all* positional evaluation would
  gain 28.3% NPS ≈ +20 Elo, so that is the whole ceiling and the realistic share
  of it is nearly zero.
- **Search pruning parameters.** Eight variants screened: both directions on the
  RFP margin, both on LMP, later LMR onset, deeper null move, history-scaled
  reduction, depth-preferred TT — **every one worse**. The schedule is at a sharp
  local optimum.

Remaining, with honest ranges: tablebases in search +20–40, time management
+10–30, opening book +10–20, SMP +10–30, further evaluation terms +20–35. That
sums to **+80 to +155 against a required +161**. So 3000 is at the very top edge
of what the known levers can deliver, and only if essentially all of them pay.

**Which means reaching 3000 probably needs something structural.** The strongest
candidate, and it is not obviously blocked:

### Integer evaluation, in BOTH languages

The invariant is "the compiled eval equals the Python eval", *not* "the eval is
floating point". If **both** sides move to integer centipawns the invariant holds
exactly as before — and interpretability arguably improves, since integer
centipawns are what a breakdown should show anyway.

What that unlocks is the thing Stockfish actually gets its speed from: packing
the (middlegame, endgame) pair into one `int32` so tapering is a single add
instead of the two multiplies and two adds `TAP()` costs today. With every weight
now tapered after Phase 3, that macro runs on the order of forty times per
evaluation, and evaluation is 28.3% of runtime.

Cost and risk, stated up front: every weight rounds, so the evaluation changes
slightly and the whole thing needs re-gating; and it is a large, invasive edit to
the most safety-critical code in the project. But it is the only identified
change that could move NPS by a large factor rather than a few percent, and the
faithfulness guarantee survives it intact. **Prototype the packed-`TAP` inner
loop first and measure it before committing to the refactor** — the pawn hash is
a fresh reminder that a plausible speed idea can measure zero.

## Progress against the budget

| lever | budgeted | status |
|---|---|---|
| remaining evaluation terms | +30 to +50 | **drawishness: +2.264% loss, gating now** — on its own nearly the size of all of Phase 3 |
| evaluation speed | ≤ +20, likely ~0 | **spent and empty.** Pawn hash byte-identical and −1.0% NPS; incremental PST killed by a 2.3% struct-copy cost. The ~20 Elo is the measured price of the C==Python invariant and is not recoverable without integer eval |
| tablebases inside the search | +20 to +40 | **KPK bitbase built and verified exact** (0 mismatches vs Syzygy on 4000 positions). The rest of the 3–5 piece space remains |
| search pruning / reductions | +0 to +40 | history-scaled LMR screened +13 self-play, gating now |
| SMP beyond +96 | +10 to +30 | untouched |
| time management under a clock | +10 to +30 | untouched |
| opening book | +10 to +20 | untouched |

**A note on how tablebase work should be judged.** KPK is not a heuristic with an
optimum — it is *exact knowledge*, verified against the authority it was derived
from. A change that is provably correct and costs no measurable speed does not
need an Elo gate any more than a bug fix does; the questions are only "is it
right" (verified) and "what does it cost" (measure NPS). Demanding 1600 games to
license a fact is how a project spends its time on ceremony.

## Order of work

1. **History-scaled LMR** (screening now). Search change, so it transfers and
   self-play screening is legitimate.
2. **Syzygy inside the C search.** The largest single bounded item. Needs a C
   probe (the Python `chess.syzygy` cannot be called from the search thread);
   Fathom is the standard public-domain probe and is licence-compatible. Does
   **not** touch the concept sum — a tablebase result is ground truth reported
   as its own authority, exactly as the root probe already is.
3. **Endgame scale factors.** The one eval dimension still genuinely missing:
   `research.firing_rate` shows our only multiplicative modifier firing in
   **0.0%** of positions. Screen on loss first.
4. **Clock-based gating**, then time-management work. Nothing here has ever been
   measured under a real clock, which is also how the engine actually plays.
5. **SMP tuning**, measured at concurrency 1 so contention is not the variable.

Each accumulates on a branch; games are spent on the accumulation, not the part.

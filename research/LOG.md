---

## 2026-08-16 — Session 32: the training data was the bottleneck

**Cut-node reduction: merged on one anchor, REVERTED on three
measurements. The protocol was wrong, not just the result.**

    paired gate vs stockfish:2700, 1200 slots    +28.5 Elo [+5.6, +51.4]
    paired gate vs stockfish:2600, 1200 slots     +1.8 Elo [-24.0, +27.6]
    full ladder (2600/2700/2800), same conditions  2774 [2752,2795]
                                     vs baseline   2789 [2767,2811]  = -15

The first number cleared zero, so it was merged. It does not reproduce. Pooling
the two paired gates by inverse variance gives about +17 +/- 17, whose interval
contains zero, and the ladder -- the number this project actually tracks -- moves
the wrong way. Reverted, with `eval_check` 0.000000, perft ALL PASS and 88 tests
green on the revert.

**The ladder residuals said it before the second gate did.** Against the anchor
the gate used, the merged engine beat expectation by more than the baseline did
(+3.6% vs +2.1% at 2700); against 2600 it did worse (-3.7% vs -1.7%). A change
that outperforms specifically against the opponent it was measured on, and not
against the others, is an over-fitted single-anchor result, and that shape was
visible in the calibration table before another 1200 games were spent
confirming it.

**Three lessons, in order of how much they cost.**

*One external gate is not an external gate.* "Gate against Stockfish, or don't
claim Elo" (s24) has been the rule here, and it is not sufficient. A single
anchor at a single strength is one opponent, and 1200 paired slots against it
still leaves ~+/-23 Elo of interval, which is wide enough for a null to clear
zero by chance perhaps one time in twenty. Two anchors before merging, from now
on. The second gate cost two hours; the merge would have cost a permanently
worse baseline that every later experiment was measured against.

*Absolute calibrations across sessions are not comparable.* The post-merge
calibration read 2774 against 2803 recorded earlier, which looked like the merge
had lost 29 Elo. Re-calibrating the OLD code the same day at the same
concurrency put it at 2789, so most of that difference was between sessions, not
between versions. Compare like with like or do not compare.

*A wide interval that clears zero is still a wide interval.* Earlier today the
same change measured -5.7 [-38.5,+27.2] and was called a rejection; then +28.5
[+5.6,+51.4] and was called an acceptance. Both readings took the point estimate
seriously and both were wrong. The instrument resolves about +/-23 at 1200
slots, and effects of the size this engine can still produce sit inside that
band. That is the fact to design around, not to argue with.

**Where this leaves the search.** Cut-node reduction genuinely shrinks the tree
30.4% and time scaling is genuinely +40.5 Elo per doubling, so the theory that
predicted ~+21 was sound; the effect is simply smaller than the noise and not
worth a permanent change on this evidence. It can be re-tested at several
thousand games per anchor if a reason appears. The reduction schedule stays
where it was.


**Cut-node IIR: -1.5 Elo [-23.4, +20.3], REJECTED -- and this null means
something.** With cut-node reduction merged, the obvious follow-up was
Stockfish's second use of the node type: reduce an extra ply at a cut node that
has no TT move. The argument is good on paper. Internal iterative reduction
exists because a node with no TT move cannot order itself; at a cut node the
parent additionally expects a fail-high, so the exact value matters less. Two
independent reasons the subtree is worth less than its nominal depth, over a
large population -- 71.6% of this engine's cut nodes have no TT move.

    if(!excl && !ttm && cutnode && depth>=7) depth--;

The cheap proxies were ambiguous and honest about it: nodes at fixed depth went
UP 3.6% while depth at 3s went up by 2 plies across four positions, which is
what happens when a change alters what "depth" MEANS -- internal iterative
reduction moves the goalposts, so neither proxy is a measurement. The gate
settled it at -1.5 Elo over 1200 paired slots.

**The interval is the point.** +/-22 Elo would have caught a +21-class effect --
which is exactly the size of the cut-node reduction it sits next to. So unlike
this session's two earlier nulls, this one is evidence: cut-node IIR is not
worth having here, and it is not a power problem.

**Cut-node bonus +2 -> +3: not gated, because the proxies said there was nothing
to gate.** The +2 came straight from Stockfish and had never been swept. At +3
the tree is unchanged (2,311,362 -> 2,334,867 nodes, +1%) and depth moves by one
ply across four positions. A deeper reduction is being paid back in re-searches
at almost exactly the rate it saves, so +2 is already at the flat part of the
curve. Spending two hours of gate time to measure zero would have been the
mistake; the node count cost four minutes and said the same thing.


**Time scaling: +40.5 Elo per doubling, which is normal -- and it means two
"rejected" changes were never measurable in the first place.** Two gates came
back null this session while both changes demonstrably delivered what they
promised in search terms (cut-node: 30.4% smaller tree; time budget: +2 plies).
That pair is hard to explain one at a time and easy to explain together, if
extra search simply does not pay for this engine. So the payoff curve was
measured directly, with the anchor pinned at 0.3s and only this engine's clock
moving:

    0.3s   63.4%   +95 Elo   [+67, +125]
    0.6s   65.8%  +113 Elo   [+87, +141]     +18 per doubling
    1.2s   73.4%  +176 Elo   [+145, +210]    +63 per doubling

**+40.5 Elo per doubling averaged over both steps: entirely healthy.** The +18
first step was noise -- its interval overlaps the baseline's almost completely --
and reading a slope off two points was the mistake. Depth converts to strength
here at the normal rate.

Which re-prices everything that was rejected:

    cut-node reduction   30.4% fewer nodes = 1.44x = 0.52 doublings = ~+21 Elo
    time budget fix      ~15% more time    = 0.20 doublings = ~+8 Elo

Both were measured with a paired gate resolving about +/-31 Elo. **Neither
result was evidence of anything.** The changes were not failures; the instrument
could not see effects of that size, and "not distinguishable from zero" was
being read as "zero".

**The instrument was the fixable part.** Concurrency had been validated at 8 on a
ten-core box; this box has 20. Holding the book, anchor, move time and game count
fixed and varying only concurrency:

    concurrency  8    64.1%   +101 Elo   [+74, +130]
    concurrency 16    63.5%    +96 Elo   [+67, +127]

Unbiased, and it halves the wall-clock cost of every future gate. (The first
attempt at this measured +40 Elo for concurrency 16 and would have condemned it:
that run omitted the UHO book that abgate passes by default, so it was comparing
book games with bookless ones. Two variables, one conclusion, nearly banked.)

Cut-node reduction is therefore being re-gated at 1200 paired slots with
concurrency 16, which resolves roughly +/-15 Elo -- enough to see +21 if it is
there.


**Unspent time budget: found, fixed, and worth nothing measurable
(-13.0 Elo [-44.3, +18.3]).** At a fixed 3.0s move time the engine returned
after 2.19s; at 0.5s after 0.437s. It was handing back 13-27% of every move's
budget, at every move of every calibration game, and no NPS measurement could
see it because they all report nodes per second rather than seconds used.

The cause was structural. At the root, `if(SS.stopped) break;` discarded
everything the current iteration had found, so an iteration that could not be
finished was worth exactly nothing -- and given that, refusing to start one past
half the budget was the right call. Fixing the cause (keep the partial
iteration's best move when a root move completed, beat the previous score and
sat above the aspiration window's lower bound) allowed the soft limit to go from
0.5 to 0.85 of the budget. The engine then used **100.0-100.4%** of its time and
gained up to **+2 plies at 3s** (depths 15/13/16 -> 15/15/17).

Two more plies of depth, and the gate says nothing: 63.7% -> 61.9%, **-13.0
Elo**. REJECTED.

**The session's real finding is the measurement wall.** Two changes were gated
this session -- cut-node reduction (-5.7 [-38.5,+27.2]) and this (-13.0
[-44.3,+18.3]). Both CIs are ~30-45 Elo wide at 600 paired slots, and every
remaining candidate is worth less than that. **Changes are now being produced
below the resolution of the instrument that judges them.** 600 paired slots
resolves about +/-31 Elo; resolving +10 needs roughly 6,000 games, which is
about 7 hours per experiment on this box. Accepting anything on a point estimate
would just be accumulating noise, which is the one mistake that would undo the
work already banked.

**A motivation checked before it was built, and found false.** Bounded history
with gravity was next: `order()` scores killers at 80000/79000 and the
countermove at 78000, while a quiet gets its RAW history value, and history
accumulates depth*depth per cutoff with no bound -- so a hot from/to pair should
eventually outrank the killers and silently replace the designed ordering.
Instrumenting the update site over a full game's worth of searches:

    history updates        711,919
    largest value reached   41,360
    updates above 78,000         0

**The inversion never happens.** The bound is real but never reached, so the
argument for the change evaporated before any code was written. Third time this
session that pricing the prize first saved the work -- the eval-hash key (+0.167
percentage points of hit rate), the king-relative tables (the gain was the
split), and now this.


**Cut-node reduction: -5.7 Elo [-38.5, +27.2], and with it the whole reduction
seam closes.** The search knew about PV nodes but had no notion of a CUT NODE --
a node the parent expects to fail high -- which Stockfish has used as a major
reduction term for a decade. Threading `cutnode` through negamax with
Stockfish's propagation and adding `if(cutnode) red += 2` made the tree **30.4%
smaller** at fixed depth (3.32M -> 2.31M nodes over four positions) and moved
depth at 3s by +1, +1, +2, -1. Paired external gate over 600 shared slots
against stockfish:2700: 64.3% -> 63.6%, **-5.7 Elo, not distinguishable from
zero**.

A 30% smaller tree bought nothing, and that completes a pattern rather than
being an isolated failure:

    log-log LMR table         bounded under +25, never resolved
    history-scaled LMR        -2.61 [-4.66, -0.56]
    LMR onset 3rd -> 4th      -2.83 [-4.86, -0.80]
    cut-node reduction        -5.7  [-38.5, +27.2]

**Neutral-to-negative in BOTH directions is what a local optimum looks like.**
Reducing harder gains nothing; reducing less loses. So the 5.3x tree-size gap to
Stockfish 11 is not sitting there waiting to be collected by reducing more.

The reduction statistics say why, and they say something surprising. The
re-search rate -- how often a reduced search fails high and must be repeated --
is **1.08%** (3,479 of 322,201), against 5-10% in strong engines, and it falls
as the reduction grows (1.62% at red=2, 1.00% at red=3, 0.26% at red=4). A low
re-search rate has two readings: the reductions are very safe, or they are so
deep that the reduced search can no longer discover anything and always fails
low. The second reading is the right one, and the earlier -2.83 for reducing
LESS is what distinguishes them: if reductions were merely safe, backing off
would be free.

Ordering is not the explanation either. The best move is found on the first try
88.29% of the time and within four 97.68%, so the tail this engine reduces is
ordered about as well as the head.

**One measurement was worth re-doing.** Outcome loss says this evaluation
matches SF11's, which sits badly next to losing 98% of games to it, so the
metric was checked against the question a search actually asks -- not "predict
the result of this position" but "of these thirty siblings, which is best".
`research/move_rank.py` compares each static evaluation's preferred move against
a depth-12 search:

    this engine    20.00%
    stockfish 11   13.17%

The evaluation ranks moves at least as well as SF11's on top of predicting
outcomes as well. It is closed on both metrics, and this project has now checked
both. (The first run of this returned 1.75% and 1.25% -- both far too low for
any static evaluation. `b.turn` was being read after the matching `pop`, which
returns the mover rather than the opponent, so both engines were being asked for
their WORST move. The implausibility of the numbers is what caught it.)


**King-relative evaluation capacity: REJECTED, and the way it failed is worth
more than the result.** If the evaluation is limited by model class rather than
by missing terms, the fix is capacity, and the cheapest large block of real
capacity is the one thing NNUE has that a piece-square table does not: piece
placement conditioned on a king. HalfKP indexes every piece by (piece, square,
own-king-square); kept interpretable and data-efficient that becomes a table over
the RELATIVE offset from a king, folded left-right, tapered mg/eg -- 960
parameters per king, each one readable as a sentence.

Screened against the standard held-out split it looked like the best evaluation
result this project has ever produced:

    both kings   +1.249%   (~+5.9 Elo)     1920 parameters
    enemy king   +0.700%
    own king     +0.442%
    PST control  +0.343%   <- re-fitting the tables that already exist

3.6x the control. Then two things did not add up. The fitted tables were not
chess: adjacent offsets swung +34 / -24 for positions that are nearly the same
chess fact, and a pre-registered expectation (that rooks should care LESS about
king proximity than knights, working at range as they do) came out backwards.
And the split was by POSITION, on data sampled every few plies from self-play
games -- so positions from the same game, sharing an opening, a structure and
one correlated result, sat on both sides of it.

`texel4.jsonl` was generated in a different run and overlaps `texel_all` by
0.1%: genuinely independent games. Re-screened against it:

    both kings   -0.925%       (was +1.249%)
    band (coarse) -0.831%      384 parameters, cannot fit the oscillation
    enemy king   -0.365%       (was +0.700%)
    PST control  +0.411%       (was +0.343%)   <- the ONLY one that transfers

**The entire gain was the split.** Every king-relative variant makes the
evaluation WORSE on independent games, including the coarse one whose 24 cells
per piece cannot encode noise. The control meanwhile behaves exactly as a
healthy fit should -- it early-stops at step 225, its largest adjustment is 9
centipawns, and it transfers slightly BETTER on independent data than it did on
the contaminated split. The control working while the candidate inverts is what
makes this a real answer rather than a broken harness.

**The methodology bug, which is the part that generalises.** Every loss screen
in this project has used a position-level split of self-play data, and that
inflates any model with enough parameters to notice the correlation. It cost
nothing where the number was small and the change was then game-gated (the PST
re-fit's +4.8 Elo was measured in games and stands), but it means a screen result
is evidence only when the test set is a different GENERATION RUN. `--test-data`
now defaults to texel4 for exactly this reason, and screens quoted against a
position split should be treated as upper bounds.

So the evaluation is closed from both directions: not term-limited (it matches
Stockfish 11's classical eval) and not cheaply capacity-limited (1920 parameters
of genuine interaction capacity transfer negatively). What is left is the search.


**The evaluation is not the problem, and here is the measurement that settles
it.** Nine hand-picked knowledge bundles had measured ~zero, and the conclusion
drawn was "the knowledge seam is closed". That conclusion was reached by running
out of ideas, which is not evidence. `research/eval_room.py` scores the same
80,000 positions with three evaluators and compares decisive-game outcome loss,
each at its OWN best K:

    this engine            0.098681
    stockfish 11 classical 0.101598    -2.96%   <- WE ARE AHEAD
    stockfish (NNUE)       0.081968   +16.94%

**This engine's concept sum predicts game outcomes slightly BETTER than
Stockfish 11's classical evaluation**, and the whole 16.94% deficit is against an
NNUE. That is not a pool of chess knowledge waiting to be written down as terms;
it is the gap between any hand-crafted concept sum and a neural network.

The bucket breakdown says the same thing from the other side. Splitting by
phase, material, pawn count, queens, passers, bishop pair, piece mix and king
exposure, the NNUE gap sits between 10.8% and 24.9% with almost everything
clustered at 15-20%. **A missing TERM looks like a large gap in the one bucket
where it fires and nothing anywhere else. A uniform deficit everywhere is a
statement about the model class, not about chess knowledge.** Nine zero bundles
were not nine unlucky guesses; they were nine terms added to a model that was
not term-limited.

Confound, stated because it cuts against the conclusion: the positions are this
engine's own self-play and the labels are results of games this engine played,
which favours its own evaluation. The -2.96% should not be read as "better than
Stockfish 11". It should be read as "in the same class", which is all the
argument needs.

**What that implies is the useful part.** Stockfish 11 is a ~3300-Elo engine
whose evaluation is in this one's class. So its advantage is not knowledge -- it
is search and speed. Measuring those:

    raw speed          2.08M NPS vs 1.65M      1.26x  -> worth only ~17 Elo
    depth at 3s        22-28 vs 14-20
    nodes at depth 15  394,273 vs 2,096,933    5.3x MORE for the same depth
    per-ply growth     1.80 vs 1.82            nearly identical

Same growth rate, same speed class, five times the tree. Not a faster-growing
tree -- a uniformly fatter one, which is what a uniformly lighter reduction
schedule produces. (Nominal depth is not comparable between engines, and part of
SF11's thinner tree is simply that it reduces harder, so the 5.3x is not a pure
deficiency. It is still where the difference lives.)

**So the seam is search, and specifically reduction, not knowledge and not
ordering.** Ordering was the first suspect and the statistics acquitted it:
88.82% of main-search beta cutoffs come on the first move tried, 95.64% within
two, 98.46% within four, mean cut index 1.347. Quiescence is 44.4% of nodes,
which is normal. With cutoffs that early, LMR hardly runs at cut nodes at all --
the tree's size is set at ALL-nodes, where every move is searched and the
reduction schedule alone decides the cost.

Tooling kept: `research/eval_room.py` (three-way evaluator comparison, bucketed),
`research/speed_gap.py`, `research/ebf.py`, and a Stockfish 11 build at
`~/bin/stockfish11` used purely as a measuring instrument, as `stockfish`
already is for calibration and suite mining. No Stockfish code enters this repo.


**Eval-hash key stripped of castling and ep: correct, tree-identical, REJECTED.**

`eval_core(bb, side)` takes the piece bitboards and the side to move and nothing
else -- it cannot read castling rights or the en-passant square. But the eval
hash was keyed on the full Zobrist `b->hash`, so two positions with identical
placement differing only in castling or ep occupied different slots despite
having provably identical evaluations. Zobrist is XOR-based, so the offending
components come straight back out:

    h = hash ^ Z_CASTLE[castle] ^ (ep >= 0 ? Z_EP[ep & 7] : 0)

Everything about it checked out. `eval_check` 0.000000, perft ALL PASS, and
fixed-depth node counts identical to the node across six positions -- a pure
speed change by the self-validating rule. Then it measured **-3.36% NPS** over 8
interleaved pairs.

Instrumenting the probe explains it, and the explanation is the useful part:

    main   probes 330,245   hits 186,443   rate 56.456%
    ehk    probes 330,245   hits 186,993   rate 56.623%

**+0.167 percentage points -- 550 extra hits out of 330,245 probes.** At 36.7% of
runtime in `eval_core`, 0.17% of probes skipping it is worth ~0.06% of runtime,
and that is the *entire* prize, collected by paying two lookups and two XORs on
every one of the other 329,695 probes.

This is worth writing down because the cost could have been engineered away --
maintain the stripped key incrementally in make/unmake and the probe path goes
back to zero overhead. It would not have mattered. **The measurement to take
first was the size of the prize, not the size of the cost.** Positions reaching
identical placement while differing only in castling or ep are rare in a real
tree: ep squares survive one ply, castling rights change only on king and rook
moves, and the TT already absorbs most transpositions upstream of the eval hash.

Same shape as the arithmetic micro-optimisations: a real inefficiency, correctly
identified and correctly fixed, whose ceiling was below the noise floor before
any code was written.


**Pawn islands and candidate passers: +0.2 Elo. The last structural idea, and
it closes the knowledge seam.**

These were chosen to fit the one pattern that had worked: long-horizon and
structural, not tactical. Pawn islands are the most long-horizon fact in chess
-- the count barely moves for twenty plies -- and nothing in the evaluation
could express the SHAPE of the skeleton, only single pawns (doubled, isolated,
backward) and adjacent pairs (connected). A candidate passer is literally the
state one push before the thing the evaluation already scores most highly. Both
depend on the pawn bitboards alone, so they ride free inside the pawn hash.

Verified firing on a constructed position (White b/f/g/h = 2 islands, Black
c/f/h = 3, and g5 a genuine candidate with two sentries and two helpers), then
screened on 41k fresh decisive positions: **+0.034%, both weights collapsing,
8.0 -> 2.8 and 4.0 -> 1.0.**

That is **nine consecutive new-term bundles at or below +0.2 Elo**. The four
things that DID pay were passer path safety, endgame drawishness, and re-fitting
two assumed SHAPES (king danger, threat values) -- none of them a new feature,
three of them a better use of features already present.

**The knowledge seam is closed.** The evaluation's 90 weights, 512 fitted table
entries and fitted curves already span what hand-designed chess features can
express over this data. Adding another term does not add information; it adds a
linear combination of terms already present, and the fit correctly prices it at
zero.


**Search-score distillation: rejected, twice, by its own honesty check.**

The standing objective regresses on the result of the game a position came from
-- one bit summarising forty subsequent moves. That is why ~100k positions are
needed to resolve anything, and why three weights drifted into nonsense where
the label carries no information at all. A search score is a far lower-variance
target for the same position, so 185,733 positions were labelled with the
engine's own 0.2s search score and the piece-square tables fitted towards them
in win-probability space.

The fitter reports two numbers, and the second is the one that decides:

    36k positions    search distance +1.358%    OUTCOME loss  +0.013%
    185k positions   search distance +1.989%    OUTCOME loss  -0.113%

**Matching the search better does not make the evaluation better, and at volume
it makes it worse.** A blend sweep (1.0 / 0.7 / 0.4 / 0.2 / 0.0 on the search
target) found no mixture that helped either: outcome loss fell monotonically as
the outcome label was given more weight, because at 36k positions the outcome
label is simply too noisy to fit on at all.

**Why, and this is the useful part.** The search's advantage over the static
evaluation is TACTICAL -- it sees things past the horizon that no arrangement of
concept weights can represent. That information is outside the model's span, so
fitting towards it does not transfer knowledge; it drags the parameters that DO
carry positional signal into compensating for something they cannot express.

That is the same wall as everywhere else this session. Six tactical knowledge
bundles returned zero (safe pawn pushes, king storms, escape squares, connected
rooks, wing majorities, outside passers) while the two long-horizon ones paid
(passer path safety, endgame drawishness). Tactics do not compress into a static
concept sum, whether they are hand-written as terms or distilled from a search.

**What this rules out and what it leaves.** It rules out the whole family of
"better label" ideas that do not add representational capacity: the ceiling is
set by what the features can express, not by the objective or the sample size.
What it leaves is an outside label -- another engine's evaluation -- which would
be a genuinely different signal rather than this engine's own opinion, at the
cost of the knowledge no longer being self-discovered. That is a decision about
what the project is for, not a research step, and is left for William.

Tooling kept: `research/label_search.py` and `research/fit_to_search.py`, the
latter carrying the two-number check that caught this.


**The calibration did NOT confirm the +11 Elo. Recorded as it stands.**

    2026-08-15   2811   [2789, 2833]   900 games
    2026-08-16   2803   [2781, 2825]   900 games, after the fresh-data re-fits

**-8 Elo on the point estimate**, where the held-out loss predicted +11. The
intervals overlap almost completely -- the difference of two independent fits
carries about +-31 -- so this neither confirms nor refutes the change. What it
does do is fail to deliver it, and that is the second time in three sessions
that a cheap metric has over-promised against an external measurement:

    partial-iteration   self-play  +17 [+5, +29]   external gates  ~-14
    fresh-data re-fits  loss       ~+11            calibration     -8 (n.s.)

**Kept, on balance, and the reasoning is worth writing down rather than
asserting.** For: the gains are held-out and scale-invariant on 3.9x the data;
the material values moved toward textbook values unaided, which is evidence the
loss cannot manufacture; and three chess-sense guards were applied on top.
Against: the only measurement that matters moved the wrong way.

**The specific risk this block carries is self-distillation.** The training data
is now generated by the engine playing ITSELF, so fitting the evaluation to
predict the outcomes of its own games can make it better at scoring the
positions it already steers into without making it better at chess. texel5 had
the same provenance, so the engine has now been fitted twice on its own
preferences. A genuinely independent label -- deep search scores, or games
against a different opponent -- would break that loop, and is the obvious thing
to try before generating a third self-play set.

**What would settle it** is ~8000 paired games rather than 900, which is a day
of machine time for one bit of information. Worth doing once several such
uncertain blocks have accumulated, not per block.


Six knowledge bundles had returned nothing and the shape-fitting seam was
running dry, so the question became what else every fit had in common. The
answer was the data. **`texel5.jsonl` -- 98k positions, ~70k decisive -- was
generated on 1 August by an engine that measured 2743**, and every piece-square
table, weight and curve in this evaluation had been fitted on the positions THAT
engine steered into. The engine now measures 2811 with a materially different
evaluation.

16,000 fresh self-play games produced **283,751 positions, 190,471 decisive** --
2.7x the old decisive sample alone, 3.9x combined. Re-fitting on the union, with
nothing new added to the evaluation at all:

    piece-square tables   +1.013% held-out   ~+4.8 Elo   (scale-invariant)
    the 90 weights        +0.660%            ~+3.1 Elo   (after two reverts)
    threat table          +0.645%            ~+3.0 Elo
    king-danger curve     +0.048%            ~+0.2 Elo   (not applied)

**About +11 Elo from better data and not one new term.** That is more than the
last eight knowledge experiments produced between them, and it says the fits
that pay are the HIGH-CAPACITY ones -- 512 table entries, 90 weights -- because
capacity is exactly what a small sample cannot support. The king-danger curve
gained almost nothing, and it is the one that was fitted recently and has only
86 live parameters.

**Independent evidence that the new data is better, invisible to the loss.**
Material values, in pawn units:

                   old     refit    textbook
      knight      3.51      3.02       ~3.2
      bishop      3.72      3.26       ~3.3
      rook        6.09      5.35       ~5.0
      queen      12.18     10.32       ~9.5

A queen worth 12.2 pawns was the classic Texel artefact, flagged in session 29
and not fixable by tightening bounds. The fresh data pulled all four back toward
orthodoxy on its own. It also explains the 8% drop in evaluation scale: the old
evaluation was inflated, so the search's centipawn margins were mis-calibrated
BEFORE this change rather than after it.

**Three separate drifts into chess nonsense, and what caught each.**

  * `ocb.draw_scale` fitted to **1.157**. It multiplies the evaluation in pure
    opposite-bishop endings, which are drawish, so it must be below one -- above
    one it says opposite bishops make a position more decisive. Caught by
    `tests/test_eval.py::TestModifiers`.
  * `mate_drive.king_prox` 8.2 -> 14.4, which **inverted the mating gradient**:
    with king and rook against a lone king, a cornered defender scored 128
    against 144 for a centred one. Caught by `tests/test_endgame.py`.
  * the unconstrained threat fit priced **attacking a bishop with a pawn at
    -15.7**, and made a hanging queen worth less than a hanging rook. Caught by
    reading the numbers.

All three share a cause: **the objective cannot see them.** Mate-drive fires
only in positions already won, where the label is 1.0 whatever the engine does;
opposite-bishop endings are drawn, so the decisive-only filter discards them;
threats fire in tactical positions the search resolves. Where the loss has no
signal, the weights drift, and only chess knowledge can say they are wrong. The
first two are now bounded in TUNABLE and the third is fixed by projecting each
threat row onto non-negative, non-decreasing values -- which costs 0.09 points
of the gain and removes every nonsensical entry.

**And what the freedom bought, once constrained:** a MINOR attacking a ROOK is
worth 39.4 against 9.0 for a minor attacking a bishop -- 4.4x, where material
proportionality says 1.5x -- because that threat wins the exchange. The old
`weight * VALUE[victim]` form could not express it at any setting of its four
parameters.

---

## 2026-08-15 — Session 31: asking the games instead of guessing

**Fitting the SHAPES the evaluation had been assuming.**

Six knowledge bundles had gone 0-for-6 by adding new terms. A different question
turns out to pay: not "what is missing" but **"what is being assumed"**. Several
terms carried one free parameter and a functional form taken on faith, and a
table can replace the form without adding any work at all.

  * **King danger** was `scale * units^2 / 10`. One parameter, and a quadratic
    nobody measured. Fitted monotonically (more pressure cannot be worth less,
    which is also what stops the rare tail being fitted from a handful of
    positions): **+0.237% held-out, ~+1.1 Elo**, and the curve is a different
    animal from the quadratic --

        units        4     8    12    16    20    24    28    32
        fitted     -36   -12    29    29    29    57   114   292
        quadratic    4    14    32    58    90   130   176   230

    flat and slightly NEGATIVE while an attack is only notional, then steep past
    ~28 units. Two pieces vaguely pointing at a king is not an attack, and the
    quadratic had been paying for it at every node.

  * **Threats** were `weight * VALUE[victim]`, forcing a threat on a queen to be
    worth nine times one on a pawn. Fitted by (kind, victim): **+0.088%, ~+0.4
    Elo**, and again the shape is the finding -- a hanging bishop (9.3 -> 15.3)
    outweighs a hanging knight (9.0 -> 3.1), while hanging rooks (14.1 -> 8.1)
    and queens (25.3 -> 19.3) are worth much LESS than proportionality claimed.
    Big pieces are usually defended, so a bare attack on one is more often
    illusory. The blunder classification had already named `threats` as the
    concept most often favouring the worse move in eval-limited positions.

**The rule that makes this affordable: REPLACE work, do not ADD it.** Both
tables substitute a lookup for a multiply that was already being done, and both
measured ~free (-0.15% and nil). The per-count mobility tables added a lookup on
top of existing work and cost 3% NPS, which is why +1.8 Elo of genuine knowledge
was rejected there and +1.1 accepted here. Same technique, opposite verdict,
decided entirely by whether the capacity displaced something.

**Also rejected this block:** endgame tables for knight/bishop/rook/queen
(+0.2 Elo against -0.51% NPS -- `pst.*` are already phase-tapered scalars, so
per-square deltas only add the non-uniform remainder, and there is little of
it); and a 4-way bucketed transposition table (0.00 ply at one thread, -0.17 at
ten), which closes the last open TT idea.

**And a correction to an earlier framing.** Ten threads buying +96 Elo was
called "40% of linear scaling" and treated as a deficiency. That yardstick is
wrong: Lazy SMP never scales linearly in threads, and typical engines get
+50-70 Elo from eight. +96 from ten is good, not deficient, so SMP is not the
lever it looked like.


**Endgame tables for the four piece types: +0.2 Elo, rejected.**

Pawns and kings have had a middlegame and an endgame piece-square table since
v0; knight, bishop, rook and queen have had ONE table each, so nothing could say
that a knight on the rim is a different mistake in an opening than in a pawn
ending. That looked like 256 parameters of missing capacity in the one place
where per-square fitting has already paid +9.3 Elo.

Added as an endgame DELTA (value = TABLE[sq] + (1-phase)*EGD[sq], all deltas
zero) so the mechanism shipped as an exact no-op -- node counts identical -- and
was priced before being believed: **-0.51% NPS** for the extra multiply-add per
piece. Fitting the 128 mirror-tied parameters then returned **+0.045%
held-out, about +0.2 Elo**, with the largest delta only 8cp. Net negative.
Rejected.

The reason is worth keeping: , ,  and
 are ALREADY phase-tapered scalars, so the dominant phase effect --
how much placement matters at all as material leaves -- was captured long ago.
Per-square deltas can only add the non-uniform remainder, and there is very
little of it. **Before adding capacity, check what the existing parameters
already span.**


**Re-calibrated after the speed block: 2811, 95% CI [2789, 2833].**

Same protocol as the previous fit -- three anchors, 900 games at 0.3s,
single-threaded, BayesElo draw model -- so the two are directly comparable:

    2026-08-01   2743   [2717, 2769]   600 games
    2026-08-14   2777   [2756, 2799]   900 games
    2026-08-15   2811   [2789, 2833]   900 games

**+34 Elo measured**, on a block whose only surviving changes were pure speed:
the eval-hash entry halved, the hash-slot prefetch, the 16-byte transposition
entry and PEXT slider indexing, together +15% NPS. The depth model predicts
about +14 from that (+0.24 ply at EBF 1.852 and 60 Elo a ply), so the measured
+34 is generous against it -- but each fit carries +-22, so their difference
carries about +-31 and the two are not in conflict. The honest reading is "+14
to +34, and certainly positive".

Profile and bootstrap intervals agree (+-22 and +-20) and the residuals are
+1.3%, +1.0%, -3.4%, so the model still fits. The engine remains weakest
relative to the fit against the strongest anchor, as it has been all along.

At full thread width that is about **2907**, adding the separately measured +96
for ten threads, leaving roughly **93 to 3000**.


**The engine is memory-bound, and that one fact organised the whole block.**

The blunder classification put 75.3% of real mistakes at search-limited, so
nodes per second is what is worth buying. Nine experiments later the pattern is
unambiguous:

    ARITHMETIC changes measured nothing
      precomputed Chebyshev distance table            +0.10%
      proximity gradient as exact ring popcounts      +0.08%
      Board struct 64 bytes larger (a probe)          +0.31%  (i.e. no cost)
      `pat` array stride doubled (a probe)            -0.17%  (i.e. no cost)

    MEMORY changes gave everything
      pawn hash (earlier this session)                +4.0%
      eval-hash entry 16 -> 8 bytes                   +0.7%
      prefetch the hash slots, AFTER pruning          +5.3%
      transposition entry 24 -> 16 bytes              +1.6%
      PEXT slider indexing instead of magic multiply  +7.2%

    NPS 1,311,000 -> 1,511,701 over the block, about +15%, or ~+0.24 ply at the
    measured EBF of 1.852.

Three of these are worth keeping as lessons rather than as numbers.

**Placement was the entire prefetch experiment.** Prefetching immediately after
make(), where the child's hash first exists, measured **-0.72%**. Futility and
late-move pruning discard a large share of children after make() but before
anything reads a table, so that version fetched two cache lines per move for
children that were then thrown away. Moving the same two instructions below
those tests turned -0.72% into +5.3%.

**PEXT is worth it for the dependency chain, not the arithmetic.** Removing a
multiply is worth nothing here on its own -- see the arithmetic column. It is
worth 7.2% because the multiply sits in front of a slow load, and the processor
cannot begin fetching until the address exists. Both paths are compiled: PEXT is
~3 cycles on Intel Haswell+ and AMD Zen 3+, but MICROCODED at ~18 cycles on Zen
1 and 2, where this would be a bad regression. Build with -DCC_NO_PEXT there.

**Cheap probes beat refactors.** Two invasive rewrites were avoided by first
asking whether the thing was expensive at all: doubling the `pat` array stride
and padding the Board both cost nothing, so packing `pat` densely and shrinking
Board -- each a day's careful work -- would have bought nothing.

Every change in the memory column leaves the search tree IDENTICAL, verified by
fixed-depth node counts matching to the node across six positions. That makes
them self-validating: a game gate cannot resolve +7 Elo anyway, and a change
that provably does not alter the tree can only be a speed change.

**Also priced, having been shipped without pricing: the endgame-scale modifier
costs 0.54% NPS**, which the earlier entry should have measured and did not.
Bundle H is therefore about -0.7 Elo all in, kept for the interpretability
reason recorded there -- the engine no longer claims +3.3 in a dead-drawn
ending. Gating it behind a cheap shape test recovered only 0.13%, so it was left
alone.


**Self-play overstated a SEARCH change by about 30 Elo. Reverted.**

Accepting a proven improvement from an interrupted iteration measured **+17 Elo,
95% [+5, +29], over 1600 self-play games** -- a significant result, on a change
whose logic is hard to argue with: the incumbent move is searched first at every
root, so a later move that outscores it has refuted it at the same depth, and
playing the incumbent anyway plays a move just proven inferior.

Two external paired gates disagree, and agree with each other:

    600 slots, old first:   new - old = -20.6 Elo   95% [-53.3, +12.1]
    600 slots, new first:   new - old =  -6.6 Elo   95% [-37.6, +24.4]
    combined                new - old ~ -13.6

The second run exists because abgate plays A to completion and then B, so drift
over two and a half hours penalises whichever side runs second -- and the first
gate had put the new code second. Swapping the order was meant to separate a
real effect from a harness artefact, and it did: **both orderings put the new
code behind**, so this is not run-order drift, and the direction is stable even
though neither interval alone excludes zero.

**Reverted**, under the standing rule that only an outside opponent is
trustworthy.

The methodological point is larger than the change. Session 24 concluded that
eval changes do not transfer from self-play while SEARCH changes do, and that
has been load-bearing ever since -- it is why search work has been gated cheaply
with self-play SPRT all session, including the three continuation-history tests.
This is a counterexample: a pure search change, significant at +17 over 1600
self-play games, that two external gates put near -14.

**Self-play cannot be trusted for search changes either.** It measures a change
against an opponent that shares its exact blind spots, and for TIME MANAGEMENT
-- which is what this change really is -- both sides being interrupted the same
way at the same moments is precisely the condition that cannot hold against
anybody else.

Kept: the 8-byte eval-hash entry, a pure memory-layout change with no
behavioural component.


Six knowledge bundles in a row screened at zero. `research/blunders.py` was
built for precisely this situation and its docstring already said why it keeps
happening -- "guessing concepts has gone 0-for-4" -- which this session made
0-for-6 before finally using the tool. It needs games, and the 900-game
calibration had been run without `--pgn-out`, so 400 more were played against
the 2800 anchor (48.9%, the anchor the fit says we underperform).

**319 blunders mined; 150 re-examined at ten times the thinking time.**

    search-limited     113  (75.3%)   -- more depth fixes it
    eval-limited        37  (24.7%)   -- we genuinely prefer the worse move

    by phase (search / eval)
      opening        10 / 1
      middlegame     69 / 17
      endgame        34 / 19

**Three quarters of what this engine actually gets wrong is DEPTH, not
knowledge.** That is the opposite of where the last two sessions went. Search
was declared closed after seventeen experiments -- but every one of them was a
TECHNIQUE variant (pruning parameters, ordering heuristics, a reduction
formula). None of them made the engine deeper, and depth is what the mistakes
are made of. Meanwhile six eval bundles were screened, merged or rejected on a
metric that, it turns out, addresses a quarter of the problem.

Two subtleties in the numbers, both worth keeping:

  * **Endgames are relatively more eval-limited**: 19 of 53 endgame blunders
    versus 17 of 86 in middlegames. Eval work that is worth doing is
    disproportionately endgame work -- which is where bundle H already landed,
    and where the screen is blind (drawn games are filtered out).
  * **Move choice at 0.3s is unstable.** A fresh 0.3s search avoided the
    blunder in 102 of the 150. Some of that is a warm transposition table
    flattering the re-search, but it says the engine is partly playing a
    randomised strategy, and variance at fixed time is a cost nobody has priced.

The concepts favouring the worse move, in the eval-limited quarter, are
`material` (+1682cp over 4 positions), `threats` (+1153cp over 8) and
`placement` (+245cp over 9) -- material and threats being the two that show up
when a sacrifice was right and the evaluation would not pay for it.

Suite kept at `research/suites/blunders_s30.epd`; games at
`research/data/vs2800_s30.pgn`.

**Depth work, and the reason a whole family of optimisations cannot pay here.**

With three quarters of real blunders search-limited, nodes per second is the
thing worth buying, and legality testing looked like the target: 6.4% of runtime
over 97 MILLION calls, each rebuilding the occupancy and scanning the king
square with two magic lookups. Two attempts, both rejected:

  * **alignment shortcut** -- a piece not on a queen-line from its own king
    cannot be pinned, so its move is legal. Fired on **28.3%** of calls,
    **-1.54% NPS**. The estimate had been ~57%; in real positions pieces cluster
    around their own king (pawns in front of it, rooks on the back rank), so
    alignment is the common case rather than the rare one.
  * **real pin masks**, computed once per position and hoisted out of both legal
    move generators: **-3.61% NPS**, worse still, despite a 50.5% hit rate.

The instrumentation on the second explains both, and generalises far beyond
them: the pin mask was computed 29.9M times for 41.2M legality calls -- **1.4
calls per mask**. There is nothing to amortise. The capture generator runs at
every quiescence node and usually yields one or two moves, and the main loop
cuts on the first move 90.24% of the time, so the effective moves-per-node in
this search is tiny.

**Any optimisation shaped as "precompute once per node, reuse across the moves"
is therefore structurally dead here** -- which also explains the earlier lazy
move-selection failure (-4.19%), which rested on the same assumption. Speed work
has to make the PER-MOVE path cheaper; it cannot hoist work out of it.

---

## 2026-08-14 — Session 30: a real rating at last, and the SMP question answered

**External Elo: 2777, 95% CI [2756, 2799].** Three anchors (2600/2700/2800),
900 games at 0.3s, single-threaded, maximum-likelihood fit with the BayesElo
draw model. The profile interval (+-22) and the paired bootstrap (+-20) agree,
and the residuals are small (+1.0%, +0.0%, -2.1%), so the model fits the data.

    2026-08-01   2743   [2717, 2769]   600 games
    2026-08-14   2777   [2756, 2799]   900 games

**+34 Elo, measured** -- the first honest reading since 1 August. Everything in
between was estimated. At full thread width the engine is around **2873**,
adding the separately measured +96 for ten threads, which leaves about **127 to
3000**.

**The SMP question, finally asked properly.** Ten threads are worth +96 Elo,
which looked poor against the ~70 Elo per doubling Lazy SMP usually gives. The
first measurement looked alarming -- NPS is FLAT across thread counts, 1.02x
from one thread to eight -- but it is an artefact: `research.benchmark` reports
the main thread's node count only. Depth tells the true story, and it rises
**10.17 -> 11.67 ply at ten threads**. That +1.5 ply is +90 Elo at 60 Elo/ply,
which is the +96 that was measured independently. The two agree.

+1.5 ply is about 40% of what linear scaling would give (3.74 ply at EBF 1.852).
That is low but not pathological for 0.3s searches, where thread startup is a
large fraction of the search. Three follow-ups all failed:

  * **Depth-preferred TT replacement: -0.50 ply at T=1, -0.67 at T=10.** The
    store is unconditional always-replace, so a one-ply node can evict a
    twelve-ply result -- which should hurt ten threads especially, since Lazy
    SMP's entire mechanism is helpers sharing work through the table. It does
    not, and the reason is structural: this table is SINGLE-PROBE. Refusing to
    overwrite a deeper entry belonging to a DIFFERENT position locks the slot
    for the whole search and starves the table. Depth-preferred replacement
    needs buckets; with one entry per slot, always-replace is correct.
  * **A four times larger table: -0.67 ply at T=1, -0.33 at T=10.** So the
    table is not under capacity pressure either -- 4M entries is already past
    the point where locality matters more than hit rate, and bucketing would
    not have helped.
  * **MVV-LVA instead of SEE for capture ordering: -0.34 ply at T=1, 0.00 at
    T=10.** gprof puts `see` at 7.4% of runtime over 12.65M calls, essentially
    all of it sorting captures, so this looked like free speed. The ordering
    quality it buys is worth more than the time it costs.

**Standing state.** Search, move ordering, transposition sizing and replacement,
eval speed structure, eval knowledge breadth and weight tuning have now all been
measured and all sit at or near a local optimum. The last six knowledge bundles
returned +0.65, 0, +0.1, 0, 0 and 0 Elo. Progress is real but the per-experiment
yield is now well under a point, against 127 still to find.

---

## 2026-08-14 — Session 29: the search is done, and the measurement that says so

Went looking for Stockfish 11's search gains and did not find them here. Four
experiments, one diagnostic, and a plan revision.

**Continuation history: three tests, worth nothing.** Indexed (prev piece, prev
to) -> (piece, to), the statistic SF gets so much from.
  * ordering only, paired screen: **+0.44 points, 95% [-1.58, +2.47]**;
  * ordering + threshold-gated LMR adjustment, self-play SPRT: **+5 [-15, +25]**;
  * ordering + PROPORTIONAL LMR adjustment, self-play SPRT: **-5 [-24, +15]**.

The middle result was nearly a false negative worth recording. Its reduction
rule fired only when |history| exceeded 3000, and instrumenting it showed the
gate firing on **591 of 359,355 reductions -- 0.16% -- with the increase branch
never firing once** (observed |history| peaks near 5000). A 600-game SPRT had
been spent measuring a rule that was switched off. Always instrument that a new
rule FIRES before concluding anything about whether it helps.

**log(depth) x log(moveCount) reductions: -33 Elo [-63, -4]**, SPRT stopped
early at 147 pairs. The fixed three-tier rule this replaced cannot express
"reduce more when deeper", and every strong engine does, so this was expected to
be the largest single search win available. It is decisively worse at the
constants tried. The shape is not automatically better than the tiers; the
constants carry it, and ours are apparently well placed.

**Why: ordering has almost no headroom left.** Instrumented the real thing --
**1,689,976 beta cutoffs, 90.24% of them on the first move searched**. Strong
engines run ~92-95%. That is the ceiling any ordering heuristic is competing
for, and it explains three neutral continuation-history results better than any
implementation detail could. **Move ordering is not where this engine's Elo is,
and no further ordering work is planned.**

With the 13 pruning variants from earlier sessions, that is ~17 search
experiments at or below zero. **Phase A is closed: the search is at a strong
local optimum.** The plan budgeted +30-60 Elo there on the strength of what SF11
gains from search; that budget is withdrawn and moved to knowledge and speed.

**The measurement that reopened knowledge.** Bundle E's king danger cost 4.62%
NPS ungated, and it was assumed the piece-attack union was the expensive part.
It is not: a full attack union per side, computed every evaluation, measures
**-0.64% NPS**. The cost was the magic slider lookups from the king square and
the popcounts. That single number decides several SF11 terms at once --
passed-pawn path safety, ungated king danger, the threat refinements all need
exactly that mask and can now afford it. Priced before designing, which is the
rule that killed the mobility tables and should have been applied to bundle E
first.

**Bundles K and L: the long-horizon theory only half survives.**

Session 29's rule -- knowledge pays only when its horizon exceeds the search's --
predicted that structural pawn facts would pay where tactics did not. Two more
tests say the rule is necessary but nowhere near sufficient.

  * **Bundle K -- wing majority and outside passer.** A majority is a passed
    pawn that has not happened yet; an outside passer drags the enemy king off
    the other wing. Both are decided over more moves than any search here can
    see. **+0.000%. Both weights tuned to exactly 0.000.**
  * **Bundle L -- opposite bishops with the rooks still on, and a pawn up in a
    rook ending.** Judged on drawn positions, the instrument bundle H showed was
    the right one: **+3.9% on drawn games for -0.273% on decisive** at priors,
    and no setting of the two weights beat that ratio.

L is rejected on a distinction worth keeping: **bundle H's cases are THEORETICAL
draws, L's are STATISTICAL tendencies.** King and knight against a bare king
cannot be won by anybody; a rook ending a pawn up is often drawn and frequently
won. Damping the second by a quarter throws away real wins, and the decisive
metric -- the one calibrated to Elo -- prices that at about -1.3 Elo. A scale
factor is the right tool only for endings that are drawn as a matter of fact.

K is the more interesting failure. `screen_loss` tunes IN SAMPLE, with no
held-out set, so a term that reaches exactly 0.000 has failed with every freedom
to overfit available to it. That is not a resolution problem and more data would
not rescue it: a wing majority is already implied by the pawn counts and the
tuned piece-square tables, and an outside passer is already scored as a passer.

**The eval is saturated.** Five of the last six bundles -- safe pawn pushes,
connected rooks, rook on the seventh with the king cut off, pawn storms, king
escape squares, wing majorities, outside passers -- screened at or below +0.1
Elo, each verified FIRING before being believed. Ninety-three weights and 512
fitted piece-square entries have absorbed essentially everything the terms a
human would think to add can express. The one that did pay, passer path safety,
was orthogonal to all of them: nothing else in the evaluation looks at what
stands between a pawn and the queening square.

**Four knowledge bundles, one worth having, and the rule that separates them.**

  * **Bundle F -- can the passer actually run?** Path clear of enemy control,
    path covered by our own pieces, square in front attacked. **+0.328%
    decisive loss (~+1.5 Elo) against -0.87% NPS, net ~+0.65. MERGED.**
  * **Bundle G -- a safe pawn push that would attack a piece.** One of
    Stockfish's cheapest terms. Tuned to **exactly 0.000**. Verified FIRING
    first, on a position where e4-e5 forks two knights, so this is not a
    switched-off rule mistaken for a useless one.
  * **Bundle I -- connected rooks, and a rook on the seventh with the enemy king
    cut off on the eighth.** Relational facts that no piece-square table can
    hold, so they looked like clear gaps. **+0.013%, ~+0.1 Elo.** Both weights
    collapsed (12 -> 5.4, 14 -> 1.4).
  * **Bundle J -- pawn storms and king escape squares.** Two inputs to
    Stockfish's king danger, its largest term, with no version here at all.
    **+0.000%.** storm 3.0 -> 0.3, no_escape 8.0 -> 0.0.

The pattern is worth more than any of the terms. **The bundle that paid is about
a LONG-HORIZON fact; the three that paid nothing are about TACTICS.** Whether a
passed pawn's road is covered is a property of the next ten moves and the search
cannot see to the end of it. Whether a pawn push forks two knights, whether the
king has an escape square, whether a storm is coming -- an eleven-ply search
finds all of that by itself, so saying it again statically adds no information.
That also explains bundle E (safe checks) coming in at only +0.809% despite
being the largest single idea in Stockfish's king safety.

**Corollary for the remaining road: stop porting Stockfish's tactical terms.**
They are worth far less here than they are there, because they duplicate what
this search already does. What is worth trying is knowledge whose horizon
exceeds the search's: endgame drawishness, fortresses, structural pawn features,
long-term piece placement.

**Also rejected: dropping tablebase-solved positions from the tuning set.**
15-17% of the data has seven men or fewer, which Syzygy decides at the root, so
the evaluation's accuracy there cannot affect play and fitting it spends
capacity on nothing. Refitting all 93 weights on the >=8-men subset and scoring
on a held-out >=8-men sample gained **0.023%**. The distortion was real but not
worth anything. `--min-men` kept in linfit_tr.py.

The tuning data itself is not the constraint, incidentally: the decisive sample
is 22% endgame, 27% late, 15% middlegame, 26% opening, so it can resolve
knowledge at any phase. The middlegame terms above failed on their merits.

**Knowledge, priced properly this time.** Bundle F (can the passed pawn actually
run? -- path clear of enemy control, path covered by our pieces, front square
attacked) screens at **+0.328% decisive loss, ~+1.5 Elo**, converged in 61
passes. Against the -0.64% attack union that is about **+0.9 Elo net**. Python
done in `research/worktrees/f`; C port still owed.

Bundle G (a SAFE pawn push that would attack a piece -- pressure that exists
before the pawn arrives, and one of Stockfish's cheapest terms) tuned to
**exactly 0.000**. The term was verified FIRING first, on a constructed position
where e4-e5 forks two knights, so this is not the conthist mistake again: the
data simply says a static safe-push bonus predicts nothing that an eleven-ply
search does not already find.

**The bundle screener was rewarding scale.** `screen_loss.py` fitted K once with
the bundle off and then held it, on the stated reasoning that one fixed scale
keeps the comparison honest. That is backwards, and the comment said so in the
file for months: with K held, inflating the evaluation lowers the loss for free,
and a bundle of pure bonuses inflates it by construction. Its grid also started
at 0.6 and picked 0.6 every time -- a boundary solution. Now refits K per
candidate over a grid reaching down to 0.30 (the real optimum here is ~0.42).
Bundle F fell from +2.0 to +1.5 Elo under the corrected harness. **Every bundle
number in this LOG measured before this fix is overstated by roughly a quarter.**

**The first actual profile of the search.** The evaluation was known to be ~29%
of runtime; the other 71% had never been looked at. gprof on a standalone driver
(4 positions, 3s each, 15.6M nodes, single-threaded):

    eval_core  31.9%   6.35M calls
    eval_stm   13.8%  11.50M calls   <- SELF time: the eval-hash probe alone
    negamax    12.5%
    order      12.2%   3.74M calls
    see         7.4%  12.65M calls
    is_legal    6.4%  97.0M calls
    make        5.3%  29.3M calls
    attacked    2.9%  61.1M calls

Three things that closes:

  * **Move generation is not the bottleneck.** perft runs at **86-124 M
    nodes/s**, which is competitive; the gap to Stockfish is not there.
  * **The eval hash is already the right size.** eval_stm's 13.8% is self time
    at ~90ns a call, which looks exactly like a cache miss on a 16MB table, so
    shrinking it looked obvious. Measured: EH_BITS 14/16/18 are **-5.71 /
    -3.84 / -1.62%**, and 22/23 are +0.21 / -1.20%. Twenty is the optimum. The
    probe cost is real and it is worth paying.
  * **Deferring the taper -- Stockfish's packed Score -- would LOSE here.** A
    probe replacing TAP with a single multiply measured **-2.58%**, because
    `(MG)==(EG)` compares two #define constants and is therefore a COMPILE-TIME
    test: about half the terms have no distinct endgame value and fold to a
    constant with no runtime arithmetic at all. Packing would destroy that.

**Lazy move selection: -4.19%, rejected.** `order` fully sorts every list, and
90.24% of cutoffs come on the first move, so sorting thirty-odd moves to use one
looked like obvious waste. Implemented with a rotate (not a swap) so the stable
insertion sort's exact sequence is preserved -- proved by fixed-depth node counts
matching to the node across six positions. It is still slower, because the 90.24%
is a statistic about CUT-nodes, and the sorting cost is dominated by ALL-nodes,
where every move is searched: there lazy selection does n scans plus n rotations
against insertion sort's single pass over a nearly-sorted list.

**Where this leaves the road to 3000.** Search, move ordering, eval-hash sizing,
the taper structure, move generation and sort strategy are now all measured and
all at or near their local optimum. Speed work has yielded exactly one win (the
pawn hash, +3.8) out of five attempts. What remains is eval knowledge breadth,
where Stockfish 11 genuinely has an order of magnitude more terms than this
engine -- and each one here is worth +1 to +2 Elo net after its NPS is paid.
**At that rate +135 Elo is 70-100 successful terms, and that is the honest
shape of the remaining gap.**

---

## 2026-08-13 — Session 28: the tuner was buying scale, and PSTs are linear

Two piece-square fits, a king-danger bundle, a joint refit of every weight, and
one methodological defect that had been quietly inflating every tuning number in
the project. Predicted stack: **+20.4 Elo** over `b72feda`, at gate.

**1. Piece-square tables are LINEAR, so stop evaluating chess to tune them.**
Every tuner here re-ran the evaluation for each trial step, which is why
`tune_pst.py` could afford only 48 parameters (6 ranks x 8 tables) on a 24k
window. But a table entry enters the evaluation multiplied by a coefficient that
does not depend on the table:

    eval(T) = eval(T0) + sum_f coef_f * (T_f - T0_f)

Collect the coefficients once and scoring a candidate set of tables is a dot
product. Fitting all 512 entries became cheaper than fitting 48 ranks had been,
which bought the whole 98k dataset and real gradient descent.
`126e4ac`: **+1.982% held-out, ~+9.3 Elo**, the largest eval gain in the project.
Mirror squares tied so the tables stay symmetric and readable; the two KING
tables left free, and the fit independently found that castling is asymmetric
(+38 on g1 against +23 on b1 in the middlegame, king to the centre at +61 on e4
in the endgame). Knights still worst in the corners and on a3/h3.

**2. The objective was rewarding SCALE, not skill.** The Texel loss is
`sigmoid(eval/(K*400))`. Every fit in this project chose K from a grid whose
smallest entry was 0.6, and chose 0.6 every time — a boundary solution, i.e. a
parameter that was never actually optimised. The true optimum on this data is
0.46-0.50. At a fixed K=0.6, **multiplying the whole evaluation by 1.2 "improves"
the loss by +0.751%** while changing no move the search would ever make — and
worse, it would silently de-tune the search's centipawn margins (futility
150/300, probcut, delta pruning), which are calibrated to the current scale.
The first run of the joint fitter found the exploit and drove `material.queen`
to its bound. The fix is to re-optimise K for every candidate, which makes a
pure rescale worth exactly zero. **Every future tuning number in this project
must be scale-invariant or it is not a number about strength.**
Re-scored the already-committed PST fit under the corrected objective to check
it was not the same illusion: +1.982% with eval scale moving +1.0%. Genuine.

**3. A harness that passed on broken code, again.** The first linear model was
wrong by 7.9cp: `evaluate` multiplies the concept sum by the opposite-bishop
modifier, so every coefficient needed that factor. The per-block diagnostic
PASSED on the broken model, because a perturbation applied evenly across one
table cancels between the two colours — the same cancellation trap as the
phase-cache test in session 27. What caught it was perturbing the REAL tables and
demanding the model reproduce the REAL evaluator (`research/check_pst_linear.py`).
Derive nothing that can be measured through the thing itself.

**4. Knowledge is not free, and only a stopwatch can tell you.** Bundle E (king
danger: safe checks, queenless discount, weak squares) screened at +0.809%
decisive loss, ~+3.8 Elo. It also cost **-4.62% NPS** over 8 interleaved pairs —
about -0.077 ply at EBF 1.852, so ~-4.6 Elo of lost depth. **A net loss, and
completely invisible to the loss screen that approved it.** Gating the scan on an
attack actually existing (`attackers>=2`) — chess-sensible and cheap — halved the
cost to -2.17%. Any new eval term must be priced in NPS before it is believed.

**5. Coordinate descent leaves correlated weights where they started.**
`linfit_tr.py` measures each weight's coefficient through the real `evaluate()`,
fits all 90 jointly inside a trust region, then re-scores with the real evaluator
and keeps the round only if held-out loss actually fell. Rounds 5-9 rejected with
a collapsing trust region, which is what converged looks like.
`6933fef`: **+1.362% held-out, ~+6.4 Elo, scale-invariant.**
An earlier variant demanding exact GLOBAL linearity reached only 27 of 84 weights
(+0.227%); local linearity plus a trust region reaches all 90.

**Open question, recorded rather than hidden:** material carries +2.7 of that
+6.4 and wants `pawn` 100 -> 88 with `queen` 900 -> 1008, i.e. a queen worth
11.45 pawns against a textbook ~9.5. SEE is unaffected (`csearch.c` uses a
hardcoded `{100,320,330,500,900}`), so this is eval-only, but an inflated queen
is the classic Texel artefact and the loss cannot see trade quality. Games decide.

**Rejected: per-count mobility tables.** Mobility is four slopes -- one
multiplier per piece type -- so the eval believes the 8th square a knight gains
is worth what the 1st was. Replaced with per-count tables (~130 parameters,
initialised to exactly the old line: eval unchanged to 2e-13 and the depth-8
node count byte-identical at 586,319, so the conversion itself was provably a
no-op). Fitted monotonically (PAVA projection, since more squares must never be
worth less) at **+0.392% held-out, ~+1.8 Elo**.

The fitted curve is genuinely, strongly non-linear and confirms the hypothesis:
a rook with ZERO safe squares scores **-81.9 in the endgame against -6.2 at one
square**, a queen with none -103.4. The old line priced a trapped rook as merely
below average. But the table costs 1.27% NPS as pure mechanism (measured with
identical trees) and 3.0% for the whole change, i.e. -1.2 to -3.0 Elo of depth
against +1.8 of knowledge. **Net somewhere between +0.6 and -1.2, which is not a
demonstrated gain, so it is not shipped.**

Worth recording why the cheap version does not exist: gating the table to low
counts and reverting to the line above is WORSE THAN DOING NOTHING (-2.8 Elo at
n<=2). The fitted table sits at a different absolute level than the line, so
splicing them puts a backwards step in the middle of the curve. The shape only
pays as a coherent whole. Fitted curve kept in .

**The binding constraint has changed.** Two of this session's three eval ideas
were killed by NPS, not by knowledge. At EBF 1.852 a 1% NPS loss is about 1 Elo,
so eval speed is now worth double: it is Elo directly, and it is the budget that
any new term has to be bought with.

**Rejected:** continuation history in `csearch.c` (indexed (prev piece, prev to)
-> (piece, to), with the same bonus/gravity scheme as the butterfly table).
Paired screen: **+0.44 points, 95% [-1.58, +2.47]** — unresolved, and mean depth
fell 11.2 -> 11.1, consistent with the 590KB table costing cache. Parked, not
merged. Also not shipped: a coordinate retune of the bundle A/D weights, worth
only +0.153% in-sample over its priors and superseded by the joint fit.

## 2026-08-04 — Session 27: what Phase 2 found before it found any Elo

Phase 2 of `research/SCHEDULE.md` was meant to be a tuning run. Filling `W_EG`
for the first time instead exposed **three latent defects in the Phase 1
machinery that a no-op change is structurally incapable of testing**, plus a
research-harness rule that let a broken variant reach a gate. All four are
fixed and committed. Worth its own entry, because the pattern generalises.

**The pattern: a no-op proof only exercises the no-op.** Phase 1 was validated
exactly as the standing rules ask — `eval_check` 0.000000, fixed-depth node
counts byte-identical (2,666,298). That proof was real, and it was worthless
for everything the feature exists to do, because every code path it exercised
had `mg == eg`. Three separate bugs were sitting behind that condition.

**1. `TAP` in a `static` initialiser (build break).** `#define TAP(MG,EG)
((MG)==(EG) ? (MG) : phase*(MG)+(1-phase)*(EG))` reads `phase`, a runtime local.
With equal arguments gcc folds the ternary to a constant, so
`static const double PSTSCALE[6] = {TAP(...), ...}` compiled. With one distinct
endgame value it does not fold, and the file stops compiling — six
"initializer element is not constant" errors, before a single game. `PSTSCALE`
is now a plain local; node count 455,507 before and after.

**2. Phase-blind concept caches (17.7cp, and the interesting one).**
`eval_check` went 0.000000 → **17.702383 on 101 of 6204 positions**. The endgame
values were not at fault: checked one position at a time, C and Python agreed to
5e-5. The fault was experiment 3 from the very first session — the pawn-keyed
caches in `PawnStructure` and `KingSafety`, worth 51.4k → 55.1k NPS at the time,
keyed on `(white_pawns, black_pawns[, king squares])`. The cached part was
genuinely phase-free *until tapering*; doubled, isolated, backward, connected,
shield_gap and open_file all read the phase once a weight has two values. So a
position could inherit a score computed at someone else's phase.

**Why it hid, and why that matters more than the bug:** a position never
collides with itself. Every single-position check said the eval was fine. Only a
6204-position sweep in one process disagreed — and my first instinct was to
distrust the sweep, because the isolated re-check "proved" it wrong. *A bug
whose reproduction depends on evaluation order will always look like a flaky
harness.* `tests/test_taper_cache.py` now reproduces it deliberately: same pawns,
same kings, two phases, and an **asymmetric** skeleton — the first version of
that test passed on the broken code because a symmetric structure makes every
tapered term cancel between the colours. It fails by 39.7cp on the old keys.

Phase belongs in the key: it is `ph/24` for integer `ph` in 0..24, so this costs
at most 25 buckets. The C eval never had the bug — it recomputes every call — so
the fix was to make Python agree with C, not the reverse.

**3. The generator quietly rounded (9e-5).** Weights crossed into C via `%g`:
six *significant digits*. Every weight the engine has ever shipped was a short
decimal, so this was exact and the invariant looked airtight. The tuner emits six
*decimal places*, and `3.481958` lost its last digit. Now `.17g`, which
round-trips an IEEE double exactly. On today's weights it only respells them
(`0.5125` → `0.51249999999999996` is the same double); node count 455,507
unchanged.

**4. `screen.sh` played 800 games on a variant it knew was unfaithful.** It
printed a warning and continued. That is the wrong default for this project:
if the C eval and the Python eval disagree, the variant's explanation is a lie
and its Elo is not worth measuring. It now exits before the first game. It also
grepped for a literal `"0.000000"` instead of reading `eval_check`'s exit
status, and so rejected a variant that was correct to 9e-5 — it now defers to
the exit code, which already encodes the project's 0.05cp tolerance.

**Rule added, and it is the durable output of this session:** *a change
validated as a no-op has not been validated. Before shipping capacity that
nothing uses yet, run one throwaway build with the capacity actually used.* Ten
minutes of that would have caught all three of the above; instead they surfaced
one at a time across four failed gate launches.

**Phase 3 bundle A — minor-piece placement. Untuned −14, tuned +17: the terms
were fine, the numbers were not.** Five terms this eval never had, ideas from
SF 11, reimplemented in both languages: knight/bishop outposts, minor behind a
pawn, bad bishop (own pawns on its colour, amplified by a blocked centre),
bishop on a long diagonal raking the centre. `eval_check` 0.000000 over 6204
positions on the first build, 88 tests green, every sub-term firing between 5.6%
and 72.7% on the blunder suite.

Priors were Stockfish 11's own middlegame values scaled by pawn ratio (its pawn
is 128, ours 100). **Screened −14 Elo, 95% [−40, +12]** — SPRT rejected H1 at 358
games.

The instinct was that the terms double-count what mobility and the PSTs already
say. **Wrong, and worth checking before acting on it:** correlating each new
sub-term against all twelve existing concepts over 216 positions gave a maximum
|r| of 0.33 (behind-pawn vs mobility, which is just true — a minor behind a pawn
has fewer squares). The terms carry independent information.

So it was calibration. Tuning **only** the five new weights, everything settled
frozen, bounds reaching **zero** so the tuner could answer "worth nothing":

| weight | prior | tuned |
|---|---|---|
| `minor.outpost_knight` | 24.0 | 26.4 |
| `minor.outpost_bishop` | 12.0 | **0.0 — term deleted** |
| `minor.behind_pawn` | 14.0 | 6.3 |
| `minor.bishop_pawns` | 2.5 | 2.25 |
| `minor.long_diagonal` | 35.0 | 15.75 |

Loss 0.090537 → 0.090287 (0.276%) on five parameters over 20k samples — far too
few parameters to overfit that much data. Two lessons:

1. **Six passes was not convergence.** The first run stopped with
   `long_diagonal` at 24.5 and `behind_pawn` at 9.8, each having fallen by
   *exactly* the maximum the 5%-per-pass step allows in six passes. They were
   still moving. Thirty passes took them to 15.75 and 6.3, and drove
   `outpost_bishop` to zero. A tuner that stops while every changed weight is
   still travelling in one direction has reported a step limit, not an optimum.
2. **Borrowed weights do not transfer even when borrowed terms do.** SF's
   numbers are calibrated against SF's mobility and SF's PSTs. Rescaling by the
   pawn ratio is not enough.

The tuner's verdict on bishop outposts is also just good chess: a knight needs a
permanent square because it is short-range; a bishop already radiates down a
diagonal from anywhere safe. Term removed from both languages.

**Re-screened tuned: +240 =358 −202 (52.4%), paired +17 Elo, 95% [−0, +33]** over
the full 800 games. Calibration alone moved the bundle **+31 Elo**.

**External verdict: +7.2 Elo, 95% [−31.6, +46.1] — not distinguishable from
zero.** 400 paired slots against Stockfish 2700, identical openings and colours:

| | score vs SF 2700 | Elo vs anchor |
|---|---|---|
| baseline | 59.1% (+181 =111 −108) | **+64 [+35, +94]** |
| bundle A | 60.1% (+186 =109 −105) | +71 [+42, +101] |
| paired delta | — | **+7.2 [−31.6, +46.1]** |

Self-play said +17, external says +7. That is s24's finding reproducing exactly:
self-play flatters eval changes. And the bundle costs **−3.2% NPS** (1,292,536 →
1,251,440) and −0.16 average depth, so a +7 evaluation gain is roughly paying for
its own speed. Net: a wash, with an interval spanning both signs.

**Not accepted — and not discarded either.** SCHEDULE.md predicted this exact
outcome in its opening argument: an 800-game gate resolves ±19 Elo, SF 11's
individual terms are worth 5–20 each, so *a single bundle is below the
measurement floor by construction*. Rejecting everything under the floor means
never accumulating anything; merging on a non-significant positive is precisely
the s24 mistake. So bundle A now lives on a long-lived **`phase3` branch** that
accumulates bundles, to be gated externally **once**, with enough games to
resolve the sum. Main stays measured.

**Caveat on every Elo number in this project, worth stating once and loudly.**
All of them — screens, abgates, the anchor — come from `uho_1000.epd`, 1000
*unbalanced* openings played as colour-swapped pairs with a pentanomial paired
estimator. That is the right instrument and it is why the paired intervals are as
tight as they are: unbalanced books cut the draw rate, and draws carry no
information. But it means **the absolute ratings are soft**. An unbalanced book
does not produce a rating comparable to balanced play, and Stockfish's `UCI_Elo`
is itself calibrated on normal play, so "≈2764" is an anchor-relative figure with
a book-shaped bias in it, not a CCRL-style rating. **The paired deltas are what
this project should believe and quote; the absolute number is a rough locator.**

**Free by-product: the first external anchor ever measured on this machine.**
The baseline arm puts the engine at **+64 [+35, +94] over Stockfish 2700 ≈ 2764
single-threaded** — which independently corroborates the inherited MacBook figure
of 2743 [2717, 2769] on different hardware and a different Stockfish (18 vs
whatever brew had). Worth having: the standing number had been an assumption
since the machine move, and it turns out to have been a sound one.

**Stockfish was not installed on the PC.** Every external number this project
owns — 2743 single-thread [2717,2769], ~2840 as played — was measured on the
MacBook, and `research.abgate` / `research.calibrate` both resolve the binary
with `shutil.which`. So since the machine move, *every* gate has been forced to
be self-play, which is precisely the instrument s24 proved does not transfer for
evaluation work. No sudo here, so the official static build now lives in
`~/bin/stockfish` (`CLAUDE.md` records it). This was a silent capability loss:
nothing failed, the gates just quietly stopped meaning what they used to.

## 2026-08-05 — a screen for SEARCH changes, and what it says about the pruning schedule

Evaluation changes have had a minutes-long screen since the decisive-loss work.
Search changes had none, so each cost an hour of games — and history-scaled LMR
spent that hour to return +13 [−5, +30], which resolves nothing.

**`research/search_screen.py`.** Ground truth is our own engine at 3s over 1800
positions (mean depth 15.6); a variant is scored on how often it finds that move
at 0.1s, compared **paired** (McNemar — positions both builds get right carry no
information, and comparing raw percentages throws that away).

Explicitly **not** nodes-to-depth. That is a cost measure, and this project has
been burned by it before: LOG 2692 records a variant at −7% nodes-to-depth that
gated at **46%, −26 Elo**, because a change can reach depth N precisely by
pruning away the lines that mattered.

**Noise floor, measured before trusting anything:** identical code three times
gives 2 and 6 discordant positions of 400, paired difference +0.00, ±0.7 and
±1.2 points.

**Validated with controls, because the first batch looked like an artefact.**
Seven pruning variants all landed between −2.3 and −2.8, which is exactly what a
screen biased toward its own baseline would produce. Running the baseline at
other time limits — heavy perturbation, known direction of strength:

| control | discordant | paired difference |
|---|---|---|
| 0.2s (2× time, stronger) | 11.2% | **+4.56 [+3.01, +6.10]** |
| 0.05s (½ time, weaker) | 12.3% | **−5.06 [−6.67, −3.44]** |

Stronger positive, weaker negative, at comparable discordance. The bias
hypothesis is refuted and the readings are real. Doubling or halving time is
worth roughly ±60 Elo here, giving a rough **12–13 Elo per agreement point**.

**The result: every perturbation of the pruning schedule is worse.**

| variant | paired difference | verdict |
|---|---|---|
| LMR onset 3rd → 4th quiet | −2.83 [−4.86, −0.80] | killed |
| LMP `2 + d²` (prune more) | −2.78 [−4.86, −0.69] | killed |
| RFP margin 90 → 120 | −2.67 [−4.59, −0.74] | killed |
| null-move R +1 at every tier | −2.61 [−4.64, −0.58] | killed |
| **history-scaled LMR** | **−2.61 [−4.66, −0.56]** | **killed** |
| LMP `4 + d²` (prune less) | −2.33 [−4.36, −0.31] | killed |
| RFP margin 90 → 70 | −1.50 [−3.49, +0.49] | unresolved, negative |
| RFP depth 6 → 8 | −0.22 [−0.93, +0.48] | inert |

Both directions on the RFP margin, both directions on LMP, later LMR onset,
deeper null move — all worse. **The search's pruning schedule sits at a sharp
local optimum**, which the ROADMAP has asserted since s21 and which is now
measured across eight variants in under an hour rather than assumed.

**history-scaled LMR is REJECTED**, and the manner of it is the point: 800
self-play games said +13 [−5, +30] and cost fifty minutes; the screen said
−2.61 [−4.66, −0.56] and cost three.

Practical consequence for the road to 3000: **stop spending time on pruning
parameters.** They are tuned. The remaining levers are elsewhere.

**Depth-preferred TT replacement — REJECTED, and it exposes the screen's limit.**
The table is always-replace, which is fine on one thread and looks wasteful on
ten: every helper writes to the same shared TT, so a shallow entry routinely
clobbers a deep one. The ROADMAP has listed depth-preferred replacement as
untried since s21. Implemented (keep the deeper entry for the same position; a
different position always replaces, so no slot pins and no ageing field is
needed; an exact score counts for two ply).

| | paired difference |
|---|---|
| 1 thread | **−2.72 [−4.43, −1.02]** — clearly worse |
| 10 threads | −0.11 [−2.14, +1.92] — unresolvable |

Clearly worse where it can be measured, unmeasurable where it was supposed to
help. Rejected. Always-replace evidently earns its keep by keeping the table
full of recently-visited positions, which an iterative-deepening search revisits
constantly.

## 2026-08-13 — the search is saturated, and the price of faithfulness is now itemised

**Effective branching factor is 1.852**, measured across five time controls
(8.9 ply at 0.05s to 13.4 at 0.8s). Strong engines run 1.60–1.75, and closing
that gap would be worth **+61 to +187 Elo at no NPS cost** — far more than any
speed work available. That reframed the earlier "3000 needs 5–6× NPS" as too
narrow: depth is NPS *times* branching factor, and the 2026-08-05 conclusion
that "pruning is at a sharp optimum" had only tested eight single-PARAMETER
perturbations, which is a different claim from structural completeness.

So: what is the search missing? Razoring — **absent entirely**. SEE pruning of
losing captures in the main search — absent, they were searched at *full width*.
History pruning of refuted quiets — absent.

All three implemented, then swept, eleven configurations in total:

| variant | depth | paired |
|---|---|---|
| razor margin 120 (most aggressive) | 10.3 | −1.89 |
| razor 240 | 10.2 | −1.33 |
| razor 500 (barely fires) | 10.0 | −0.67 |
| SEE margin 30 | 10.1 | **−3.44 [−5.41, −1.48]** |
| SEE 90 | 10.1 | −1.56 |
| SEE 180 | 10.0 | −2.33 |
| history pruning | 10.0 | −0.33 (inert) |
| **TT-refined RFP/null-move estimate** | 10.0 | **−2.33 [−4.20, −0.47]** |

**Razoring and SEE pruning do exactly what they promise — depth rises 10.0 →
10.3 — and agreement falls anyway.** The extra depth is bought by pruning away
lines that mattered. And the readings are *monotone*: the harder each prunes,
the worse it reads, with the best configuration being the one that barely fires.

The TT-refinement result is the one that explains the rest. Feeding the pruning
decisions a strictly better estimate (the transposition score, where its bound
permits) made things **worse**, because a refinement upward makes RFP fire more
often. "Better information" became "more pruning", and this engine cannot afford
more pruning by *any* mechanism — parameter, technique, or better-informed.

> **Conclusion: the search is saturated. It prunes exactly as hard as its
> evaluation supports, and EBF 1.852 is eval-limited, not technique-limited.**

That corrects an error in my own earlier bound. The "+70–140 for a perfect
evaluation" ceiling counted only the *direct* Elo of a better evaluation and
ignored that a sharper evaluation licenses harder pruning, which buys depth at
60 Elo/ply. Evaluation gains compound; the ceiling is higher than stated. It is
also, unfortunately, no easier to reach — `blame.py` says no concept is biased at
the decision margin.

**Correction history — REJECTED, and it was the best remaining idea.** If EBF is
eval-limited, the lever is not pruning harder but making the number the pruning
decisions rest on more accurate. Correction history learns the systematic gap
between static eval and search result for a given pawn structure, and applies it
to the pruning estimate. Unlike the TT refinement it is **symmetric** — it lowers
the estimate where the evaluation is habitually optimistic, which is exactly
where over-pruning costs material.

Designed to leave interpretability untouched, and it does: the correction reaches
the *decisions* only, never a returned score, never qsearch stand-pat, never the
displayed evaluation. `eval_check` stays 0.000000 and the search still optimises
precisely the number the breakdown shows.

| | paired |
|---|---|
| first version | −3.83 [−5.96, −1.70] |
| **with the update rule fixed** | **−2.39 [−4.41, −0.37]** |

The first version had a real bug — it trained the table on `best` at every node,
but `best` is usually a *bound*: a fail-high means "at least this much". Feeding
bounds in as though they were scores teaches numbers wrong in a known direction.
Guarding the update (skip a fail-high below the static eval, a fail-low above it,
and any node whose best move is a capture) recovered 1.4 points — so the fix was
real, and the idea still loses.

> **Thirteen search variants this session, every one ≤ 0**: eight parameter
> perturbations, three missing techniques across eleven configurations, strictly
> better information from the TT, and a learned correction. Parameters,
> structure, information, and learning have each been tried. **The search is at
> a robust local optimum**, and I have no further hypothesis that the evidence
> supports.

### The price of the interpretability invariant, itemised

Three separate speed routes are now closed *specifically* by the requirement
that the search optimise exactly the number the breakdown displays:

1. **Packed integer evaluation** — prototyped at 1.77× on the tapering
   arithmetic, but only in accumulate-once form, and that arithmetic is a
   fraction of 28.3% of runtime: **+4 to +8 Elo** for rewriting the most
   safety-critical code in the project.
2. **Lazy evaluation** — skip the positional terms when a cheap partial score is
   already far outside the window. Measured over 20,000 real positions, the
   positional contribution reaches **702cp**, so a *provably* safe margin is
   702cp, at which point it never fires in a real window. (A 500cp margin would
   be unsafe in 0.1% of positions; most engines would take that trade. This one
   cannot.)
3. **Eval-speed generally** — deleting all positional terms gains 28.3% NPS
   ≈ 0.33 ply ≈ **+20 Elo**, and that is the entire ceiling.

**Roughly 25–30 Elo, and the lazy-eval route outright, is what provable
faithfulness costs.** That is the honest price of the thing that makes this
engine worth building, and it is now a measured number rather than an
assumption.

## 2026-08-06 — asking which concepts drive wrong MOVES, and getting a clean no

Three neutral results in a row (drawishness, KPK, king shelter) established the
rule: **an evaluation error only costs Elo if it changes which move you pick.**
So `research/blame.py` stops hunting for positions the evaluation scores wrongly
and hunts for positions where its error *flips the decision*: take every position
where a 0.1s search differs from the 3s reference, evaluate after each move, and
diff the two breakdowns **concept by concept**. A concept that consistently
scores the wrong move higher is the one doing the misleading.

Only this engine can run that. Every other evaluation is a single number, so it
can tell you a move was wrong but never which of its own judgements caused it.

**629 disagreements of 1800 positions. Unfiltered, one thing stands out:**

| concept | mean | median | >0 |
|---|---|---|---|
| material | **+4.8** | +0.0 | **10%** |
| everything else | within ±1.7 | 0.0 | — |

Material's mean comes from 10% of cases with a median of zero — the shallow
search grabs something the deep search rejects. That is the **horizon effect**, a
search-depth problem, and not an evaluation bias at all.

**Filtered to the 510 disagreements where neither move is a capture or
promotion — which is what isolates positional judgement — every concept is
neutral.** The largest bias in the table is `king_attack` at +1.2cp mean, median
zero, and nothing else exceeds ±0.8.

**Verdict: at the decision margin, the evaluation is unbiased.** No concept is
systematically talking the engine into the wrong quiet move. That closes
"find the miscalibrated concept" as a direction — with data, rather than by
running out of ideas — and it is consistent with everything else measured over
these two days: the remaining move-choice errors are search depth, not judgement.

**The engine diagnosed its own evaluation error — and the fix was worth nothing.**
Inspecting book exits (`research/book_probe.py`) showed the Berlin scored **+107**
on a position theory calls balanced. Asking the engine *why* — which is the
entire point of a concept-sum evaluation — named the culprit immediately:

| concept | |
|---|---|
| **king_safety** | **+52.2** |
| activity | −44.9 |
| placement | +31.6 |

Black was penalised for empty d7 and e7 in front of a king on e8 that **still had
both castling rights**. The shelter calculation had no notion of castling at all:
it judged every king on the pawns in front of wherever it happened to stand.

Fixed by taking the best shelter over the squares the king can reach — where it
stands plus any castled square still available, which is what a player does and
what Stockfish does. Berlin: **+107.1 → +54.9**, king safety out of the top
contributors.

**Then measured: −0.018% decisive-game loss, about −0.1 Elo.** Neutral. The
reason is worth keeping: the error is *symmetric* in most positions — both sides
are uncastled early, the penalties cancel, and move choice barely moves. It bites
only where castling status is asymmetric, as in the Berlin, and those are a
minority of positions.

**Third time this session that being more right turned out to be worth nothing**
(drawishness, KPK, this). That is a real pattern and worth stating: *an
evaluation error only costs Elo if it changes which move you pick.* A symmetric
error, or a correct assessment of a position whose result was never in doubt,
changes nothing.

Banked on the `kingshelter` branch, **not merged**: `eval_core` takes bitboards
and side to move, not castling rights, so shipping it needs a signature change
to the hottest function in the engine for zero measured gain. The
interpretability case is real and separate — an engine whose claim is that its
explanation is trustworthy should not tell the user a balanced position is +107 —
so it is kept, documented, and trivially resumable.

Two bugs caught inside the fix, both familiar shapes: `details()` duplicated
`_compute()`'s arithmetic and broke faithfulness on the first build (now both
route through one helper, as `minor_pieces` does by design); and the cache key
needed castling rights added, the same shape as the phase-blind key this very
cache carried earlier in the session.

**Time management, measured for the first time.** Every gate in this LOG is
fixed movetime, which bypasses the time manager entirely — so nothing here has
ever tested it. Driving the real UCI interface with real `go wtime/winc`
commands, 20 positions × 4 clocks:

| | mean | median | p90 | max |
|---|---|---|---|---|
| baseline | 0.91× | **0.54×** | 2.87× | **5.01×** |

**The engine typically spends half its optimum budget, and occasionally five
times it.** The cause is structural: the soft budget is only checked *between*
iterations, so the search starts an iteration whenever any budget remains,
however long that iteration is about to take. At fixed movetime the hard stop
equals the budget and clips the overrun — which is precisely why no gate ever
showed this. In clock play the hard cap is 5× the optimum and nothing clips it.

Implemented the standard fix (each iteration costs roughly twice the last, so
predict it and start only if the prediction fits) → mean 1.05×, median 0.74×,
**p90 and max unchanged**. It spends closer to the intended budget but does *not*
fix the tail, because an iteration already running is only stopped by the hard
cap.

**Gated: +3 Elo, 95% [−23, +30]** — 300 games at 10s+0.1, concurrency 1, full
thread width. The first clock-gated change in this project's history, and it is
neutral. **Not accepted.** Spending the clock more evenly is not worth anything
measurable; the engine was apparently not losing much to the unevenness in the
first place.

The diagnostic is kept (`research/clock_usage.py`) — the *characterisation* is
the durable part: median 0.54× of budget with a 5.01× tail, and the structural
reason fixed-movetime gates can never show it.

**A near-miss worth recording.** The first version of that diagnostic used one
position at eight clocks, and reported the baseline at mean 1.30×, then a variant
at 0.61×, then the *same* variant at 1.03× minutes later. I nearly tuned the
budget constant on that. Eighty samples were needed before the mean meant
anything — the same lesson as the pawn hash reading +1.06% on one benchmark run
and −1.02% on three.

**Lazy SMP helper diversity — REJECTED at −89 Elo [−137, −43].** The helpers
stagger only their *first* depth (`2 + id%3`), which wears off within a few
iterations, so past depth ~6 all ten threads grind the same depth simultaneously
and differ only in how TT races resolve. The textbook fix is a persistent skip
pattern so each helper sits on its own depth schedule. Implemented exactly that
(main thread never skips; single-threaded play provably unchanged at +0.17
points [−0.44, +0.77] on the search screen).

**SPRT killed it after 69 games: +8 =36 −25, 37.7%, paired −89 Elo.** Not
marginal — one of the largest negatives ever recorded here.

The mechanism is in the arithmetic: with that pattern each helper skips **half**
its iterations, so nine helpers do the work of four and a half. Evidently what
the helpers are actually worth in this engine is *filling the shared TT at the
depths the main thread is about to search* — and spreading them across depths
destroys exactly that, buying diversity nobody needed at the cost of half the
helper search. A gentler pattern would presumably be less bad; the direction is
not in doubt.

Worth noting what made this cheap: **SPRT stopped in 69 games (~35 minutes)**
because the effect was large. A gate sized for +25 Elo finds −89 almost
immediately.

**And the limit: at 10 threads the screen's noise floor is ±2 points.** Identical
code disagrees with itself by up to 1.56 points, because Lazy SMP makes the
search nondeterministic — the same size as the effects worth finding. Against a
single-threaded floor of ±0.7 to ±1.2. **So the screen is a single-thread
instrument, and multi-thread hypotheses still cost games.**

A useful side-reading, and a caution about the calibration: 1 thread → 10 moves
agreement 65.2% → 68.9%, about +3.7 points, against the +96 Elo that Lazy SMP
measured in s20 — which implies ~26 Elo per point, where the time-doubling
control implied ~13. **The two anchors disagree by a factor of two**, so a point
total is not an Elo figure. Sign and ordering only.

---

## phase4 REJECTED at +1.1 Elo — and the diagnosis rewrites the screen

Drawishness + history-scaled LMR, gated over 1600 paired slots: **+1.1 Elo, 95%
[−17.8, +20.1]**, against a predicted **+28**. The largest prediction failure of
the session, and worth far more than the +28 would have been.

**The Texel outcome loss is a FORECASTING metric. Elo is a DECISION metric.**
They coincide only for changes that alter move choice in contested positions.
Splitting the same 30,000 positions by the result of the game they came from:

| positions from games that were | loss change | share of total gain |
|---|---|---|
| **drawn** | **+27.16%** | **123%** |
| **decisive** | **−0.615%** | **−23%** |

Every bit of the drawishness gain — more than all of it — came from games that
were **drawn anyway**. Scoring a dead-drawn rook-versus-bishop as 0.00 instead of
+170 is an enormous improvement in *prediction* and no improvement whatsoever in
*result*. On the games that were actually decided, the modifier made the
evaluation slightly worse.

**Recalibrated against the two changes with real external numbers:**

| change | all-games loss | decisive-games loss | measured Elo | Elo per 1% (all) | Elo per 1% (decisive) |
|---|---|---|---|---|---|
| phase3 stack | +2.472% | **+2.737%** | **+12.8** | 5.2 | **4.7** |
| phase4 | +2.376% | **−0.615%** | **+1.1** | 0.5 | — |

The all-games rate is inconsistent by a factor of ten and predicted +11 for a
change worth +1. The decisive-games rate predicts the phase3 stack at **+12.9
against a measured +12.8**, and correctly calls phase4 as nothing.
**`research/screen_loss.py` now measures decisive-game loss.** Draws carry no
decision information; screening on them was measuring forecasting skill and
calling it strength.

**The chess lesson underneath, which is not obvious.** Every configuration of
the drawishness rules is negative on decisive games — including the ones that are
*factually correct*. Re-tuned against decisive-game loss, the optimum for all
four weights is **1.00: no damping at all.** Evaluating a theoretically drawn
position as exactly zero removes the gradient that makes the engine keep
pressing, and *"theoretically drawn" is not the same claim as "worth nothing
against an opponent who can still go wrong."* The tuner drove `no_pawns` to 0.05
because it was asked to minimise forecast error, which is precisely the wrong
objective. **Correct knowledge that does not change your choices is worth zero;
correct knowledge that removes a reason to try is worth less than zero.**

Rejected: the four drawishness rules, and phase4 as a whole. Retained: the KPK
bitbase, on interpretability grounds rather than strength — see below.

---

**Endgame scale factors — +2.264% outcome loss, and +29% in real endgames.
Impressive on the wrong metric; see the phase4 entry above for why it bought
nothing.** Four rules, four
weights, in the multiplicative modifier framework: an extra piece with no pawns
and too little material to force a win; two knights, which cannot mate; a bishop
that does not control the promotion square of its own rook pawns; a lone pawn.

These answer a question nothing else in the evaluation asks. Every other term
says *who is better and by how much*; these say **whether it can be converted**.
A rook against a bishop with no pawns is +170 of material and a dead draw, and
no amount of tuning an additive term expresses that, because the correction
scales whatever the rest of the evaluation concluded.

| positions | loss before | after | change |
|---|---|---|---|
| all | 0.088399 | 0.086469 | **+2.183%** |
| ≤12 pieces | 0.033719 | 0.028566 | **+15.28%** |
| ≤8 pieces (real endgames) | 0.029966 | 0.021226 | **+29.17%** |

Those are the **hand-set priors**, never fitted to this data — an out-of-sample
measurement. Tuning moved it only to +2.264%, which is the strongest evidence
available that the rules are chess and not curve-fitting: the tuner pushed the
theoretically-drawn cases harder (`no_pawns` 0.2 → 0.05, `wrong_rook_pawn`
0.1 → 0.05) and left opposite bishops exactly where chess knowledge put it.

**Verified against endgame theory before being believed.** Fifteen named
classical cases: KB/KN/KNN/KR-vs-KB/KR-vs-KN damped, KBN/KBB/KQ/KQ-vs-KR/KR-vs-K
untouched, wrong-colour rook-pawn bishop damped and the right-colour one not.
**0 disagreements.** Two of the three initial flags were errors in *my test's
labels* (a bishop on g1 is dark, not light); the third was a real gap — two
knights cannot force mate — and is now handled.

**The methodological finding, which matters beyond this term.**
`research.firing_rate` reported the new modifier at **0.0%** — the same reading
it gives the dead `ocb` modifier — and the standing rule says kill anything under
2%. That reading was an artefact: the tool reads one blunder suite, which is
middlegame-heavy, and **an endgame term cannot fire on middlegame positions**.
Measured on real game positions instead, it fires in **5.24% overall, 16.85% of
positions with ≤8 pieces, and 22.76% with ≤6**. *A firing-rate floor computed on
the wrong distribution kills exactly the terms that specialise.* The same applies
to the loss screen: this term is diluted roughly six-fold by middlegames, so
endgame ideas must be reported per-bucket, not just overall.

It also **supersedes and deletes** `opposite_bishops`: that modifier demanded a
*pure* bishops-and-pawns ending and fired in 0.0% of real positions. The
broadened rule covers it as a strict subset.

C mirror written, `eval_check` 0.000000 over 6204 positions on the first build,
91 tests green including five new ones that pin the behaviour on won versus drawn
endings — because the one way this modifier could do real harm is damping a win.

**Phase 3 bundle B — threat pressure. +0.113%, killed on loss, no games and no C
port.** The four SF 11 threats this eval lacks, and the ones that are about
*constraint* rather than material, which the existing `threats` concept already
covers: restricted squares (enemy squares we cover that no enemy pawn holds), a
safe pawn push that would attack a piece, and squares a knight or slider could
move to from which it would hit the queen. Screened **against the phase3 stack**,
which is the honest baseline — the question is what it adds to what we now have.

Tuned to convergence in 55 passes, bounds through zero: `restricted` 3.0→0.9,
`pawn_push` 12.0→4.2, `slider_on_queen` unmoved, and `knight_on_queen`
**5.0→18.5** — the one term with real signal, which is chess (a queen with
several knight-fork squares available is genuinely tied down). But the bundle
totals 0.113%, ≈+1 Elo.

**The pattern across four bundles is now clean and worth stating:**

| bundle | loss vs its baseline |
|---|---|
| D, imbalance & space | 0.967% |
| A, minor-piece placement | 0.820% |
| B, threat pressure | 0.113% |
| C, king safety | 0.117% |

**A and D are the ones that add a dimension the eval did not have** — material
mix, and where a piece is *permanently* well placed. B and C refine judgements
the eval already makes (threats; king danger), and refinements of an existing
term are worth an order of magnitude less than a term that was missing. Useful
prior for whatever comes after Phase 3: *ask what the evaluation cannot express
at all, not what it expresses roughly.*

**Phase 3 bundle D — material imbalance and space. +0.967% loss, the best single
bundle, and the control that nearly killed it was worth running.** Kaufman's
result, which `material.*` cannot express because it is a per-piece constant that
SEE also reads: a knight gains value as pawns stay on, a rook loses value as
pawns stay on, and a second rook duplicates the first's work. Plus space —
safe central squares to manoeuvre into, weighted by how many pieces still need
somewhere to go.

**Python only, deliberately.** With loss as the screen, a bundle needs no C
mirror to be measured, and earns one by clearing the screen first. Bundle C cost
a full two-language implementation to discover it was worth 0.117%.

First screen gave +0.738%, and the weights were pinned at their bounds, so the
bounds were widened (and made **symmetric about zero** — for a new term the sign
is exactly what is unknown, and a "penalty" prior that is really a bonus cannot
be found in a one-sided interval). That gave +0.839% with `rook_pawns` at 12.0
and `rook_pair` at 24.6, both still climbing — **roughly double the literature
values**, which is the signature of a tuner exploiting something rather than
learning chess.

The suspicion: `rook_pawns × (pawns − 5)` has a *constant* component whenever the
mean pawn count is not five, so a tuner with no other way to reprice a rook —
`material.*` is frozen — could drive it large simply because the rook is
mispriced at a flat 500, and it would look like it had rediscovered Kaufman. Two
runs settled it:

| | loss vs baseline |
|---|---|
| bundle D, no flat-rook control | +0.839% |
| bundle D **+ flat-rook control** | **+0.967%** |
| **flat rook adjustment ALONE** | **+0.029%** |

The control **cleared** the bundle instead of condemning it. A flat rook
correction on its own is worth nothing (+0.029%, converged at −11cp), so the gain
really is the *interactions*. And giving the tuner the honest flat term pulled
`rook_pair` from 24.6 down to **10.2** — right on Kaufman's ~12, arrived at
independently. That is the strongest evidence in this whole session that the
tuner is learning chess rather than fitting noise.

---

## **The stack: 2.683%, and finally above the measurement floor**

Three things this session each measured as real but individually invisible.
Assembled on the `phase3` branch and measured together against untouched main,
same 20k sample, K fitted on the baseline and held for both:

| | loss reduction |
|---|---|
| converged taper (Phase 2b) | 1.072% |
| bundle A, minor-piece placement | 0.820% |
| bundle D, imbalance + space | 0.950% |
| *sum if independent* | *2.842%* |
| **stack, measured together** | **2.683%** |

**Only 6% of the effect is shared** — they really are describing different
things. At ~8.5 Elo per 1% that is **≈ +23 Elo**, and an 800-game gate resolves
±19. **This is the first Phase 3 artefact big enough for games to see**, and it
exists only because three individually-unmeasurable results were accumulated
instead of each being gated and shrugged at. That is the session's thesis,
confirmed.

C mirror completed for all three (`eval_check` 0.000000 over 6204 positions, 88
tests green), cost **−3.9% NPS / −0.33 average depth** — barely more than bundle
A alone, so the taper and the imbalance terms are close to free.

### The gate: +15.0 Elo, 95% [−4.1, +34.1]

1600 paired slots against Stockfish 2700 — **four times bundle A's gate**,
because a CI scales as 1/√n and resolving +23 needed it. Running gates too small
to see the effect under test is what produced the last three "neutral" verdicts.

| | score vs SF 2700 | Elo vs anchor |
|---|---|---|
| baseline (main) | 55.6% (+668 =444 −488) | +39 [+25, +54] |
| **phase3 stack** | **57.8%** (+681 =486 −433) | +54 [+40, +69] |
| **paired delta** | — | **+15.0 [−4.1, +34.1]** |

**The prediction was made before the gate and it held.** 2.683% loss at ~8.5
Elo/% predicted ≈+23 from the evaluation alone; the 3.9% NPS cost is worth
roughly −8; +23 − 8 ≈ **+15**, which is what came back. A quantitative
prediction made in advance and confirmed is much better evidence for the
loss→Elo heuristic than the single calibration point it was built from.

### Confirmed and ACCEPTED: pooled +12.8 Elo over 3200 slots

A second 1600-slot batch on shifted openings, independent of the first:

| | delta | 95% CI |
|---|---|---|
| batch 1 (offset 0) | +15.0 | [−4.1, +34.1] |
| batch 2 (offset 500) | +10.6 | [−8.6, +29.8] |
| **pooled, 3200 slots / 6400 games** | **+12.8** | **[−0.7, +26.4]** |

one-sided p = **0.032**, P(effect > 0) = **96.8%**.

**Stated plainly: the two-sided interval still grazes zero.** The one-sided test
is the honest one here, and not by convenience — the hypothesis was directional
*and quantitative* and was registered before the first batch ran. 2.683% loss at
the 8.5 Elo/% bundle A established, minus ~8 for the 3.9% NPS cost, predicted
+15. Two independent batches returned +15.0 and +10.6, pooling to +12.8. A
pre-registered point prediction confirmed twice is a stronger evidential case
than this project has previously accepted anything on.

**Merged.** `eval_check` 0.000000, perft all-pass, 93/93 tests including the slow
tactics suite. Largest evaluation gain in the project's history and the first
result since Lazy SMP to clear +10.

**The method is the result.** Every part of this is individually invisible to an
800-game gate — 1.072%, 0.820%, 0.950%, or ≈+6 to +9 Elo each against ±19
resolution. Gating them separately would have produced three more "neutral"
entries in this log, which is exactly what the previous three sessions produced.
Accumulating them and gating once, at a size chosen to resolve the predicted
effect, is the only reason there is a number here. Two further bundles were
killed for free on outcome loss alone (0.113%, 0.117%) without a game or a line
of C between them.

**Phase 2b — the taper tune, run to convergence. The neutral verdict was on a
truncated tune.** Same data, same 20k sample, same parameterisation as Phase 2;
the only change is 40 passes instead of 5.

| | loss | vs baseline 0.091031 |
|---|---|---|
| Phase 2 (5 passes) | 0.090336 | 0.763% |
| **Phase 2b (converged)** | **0.090055** | **1.072%** |

**Convergence alone bought 40% more loss reduction**, and at ~8.5 Elo per 1%
that is ≈+9 Elo rather than ≈+6.5 — the largest single item measured this
session. Phase 2 gated +12 self-play [−5, +29] on the truncated weights; the
converged ones have not been gated, and on the new policy they should not be
gated alone, because +9 is still under half of what 800 games can resolve.

The endgame ratios read as chess, which is the main reason to believe the fit
rather than suspect it: queen mobility **2.67×** its middlegame value in the
endgame, rook mobility 1.85×, rook-on-semi-open-file 2.00×, hanging pieces
2.12×, passed-pawn blockade 1.88×. A few look like noise and are worth
distrusting individually — threat-by-minor at 3.33× and threat-by-rook at 0.27×
move in opposite directions with no chess reason.

**The general lesson, which cost this project a gate:** *a coordinate-descent
tune that stops while weights are still travelling has reported its step size,
not an optimum.* Both the 5-pass Phase 2 run and bundle A's 6-pass run did
exactly that, and both were read as results. `research/bundle_worth.py` and the
loss screen now print an explicit **NOT CONVERGED** warning naming the weights
still moving on the last pass.

**Phase 3 bundle C — king safety. Killed by the tuner before any games, and the
kill is worth more than the bundle would have been.** Three sources fed into the
existing king-danger `units` accumulator rather than added beside it (s24
rejected safe checks as a standalone additive term twice; inside a `units**2`
accumulator the same contribution is amplified by every attacker already there),
plus an endgame-linear term because the quadratic one is multiplied by `phase`
and so vanishes with the queens off. Built in both languages, `eval_check`
0.000000, 88 tests green.

Measured *before* screening — bundle A's lesson applied. Tuned alone, bounds
reaching zero, 40 passes:

| weight | prior | tuned |
|---|---|---|
| `kattack.safe_check` | 3.0 | 3.0 (never moved) |
| `kattack.weak_ring` | 2.0 | 0.4 |
| `kattack.pawnless_flank` | 6.0 | **0.0** |
| `kattack.eg_linear` | 1.0 | **0.0** |

The tune reported a 0.325% improvement, which is misleading and worth flagging:
its baseline was the eval with my guesses already active and *making things
worse*, so most of that number is the tuner undoing me. The comparison the tune
never makes is bundle-off versus bundle-tuned, on the same positions and K:

| setting | loss | vs off |
|---|---|---|
| bundle C **off** (the pre-bundle engine) | 0.091031 | — |
| at my guessed priors | 0.091220 | **−0.208%** (actively harmful) |
| **tuned** | 0.090924 | **+0.117%** |
| `safe_check` alone | 0.090931 | +0.110% |

So the whole bundle is worth 0.117%, and safe checks are essentially all of it —
weak ring contributes 0.007%, the other two nothing. **Not gated.** *A tune that
reports a number against its own bad starting point is measuring the starting
point. Always compare against the term switched off.*

The one positive: safe checks *do* work inside the accumulator where they failed
twice outside it. The mechanism hypothesis was right. It is just small.

---

**The number that reframes Phase 3, and the most useful thing this session
produced.** Two bundles now have both a loss figure and an external Elo, against
the same baseline (loss 0.091031):

| | loss reduction | external Elo |
|---|---|---|
| bundle A (tuned) | **0.82%** | **+7.2** [−31.6, +46.1] |
| bundle C (tuned) | 0.117% | not gated; ~+1 by the same rate |

That is roughly **8–9 Elo per 1% of outcome-loss reduction**. It is n=1 with a
huge interval and must not be quoted as a law — but as a planning heuristic it
settles a question this project has been paying for in game-hours:

**An 800-game gate resolves ±19 Elo, so a bundle needs ≈2.5% loss reduction to be
measurable at all.** SF 11-style term bundles deliver 0.1–0.8% each. SCHEDULE.md
already argued that single terms are below the floor and that the answer was
four-term bundles; the measurement says *four-term bundles are also below the
floor*, by a factor of three. Stacking every remaining Phase 3 bundle might reach
2%, and might not.

The practical consequence is a change of instrument, not of ambition: **loss on
held-out outcomes is now the screen, and games are spent only on accumulations
big enough to see.** A tune costs minutes and resolves 0.1%; a gate costs an hour
and resolves 19 Elo ≈ 2.2%. Using games to evaluate a 0.1% change was always
going to return "neutral", however good the change.

**Concept-aware search control: premise tested, NOT SUPPORTED — killed for one
script instead of an 800-game gate.** The idea worth the most if it had worked:
every other engine's eval is a single number, so its search guesses whether a
node is sharp from scalar proxies (`improving`, static-vs-beta). Ours is a typed
decomposition, so it could *know* — scale the reverse-futility margin by how much
of the score is threats + king attack, the parts a few plies can erase, versus
pawn structure and placement, which stay put.

That rests on one empirical claim, testable with no games: does
`vol = |threats| + |king_attack|` predict `|search(6) − static|`? Over 216
blunder-suite positions:

| predictor | Pearson | Spearman |
|---|---|---|
| volatile (threats + king attack) | +0.077 | **+0.002** |
| stable (pawns + placement + mobility) | +0.174 | — |
| `\|static eval\|` (free to the search already) | +0.333 | +0.046 |
| volatile, controlling for `\|static\|` | −0.060 | **+0.005** |

**The rank column is the real one.** The swing distribution is heavy-tailed, so
the Pearson figures — including the +0.333 that made `|static|` look like a
strong null — are a handful of large swings, not a relationship. On ranks
*nothing* predicts the swing, volatility least of all, and controlling for
`|static|` leaves +0.005.

One slice did look positive: inside a matched `|static| ∈ [50,300]` band, the
high-volatility third swung 84.5cp against the low third's 38.4, a +46.0cp gap,
95% [+2.2, +81.9]. That is a post-hoc slice with an interval grazing zero, after
looking at several — the exact shape of the s25 `scale_win` false positive
(screened +68 [+29,+109], confirmed +6). Not evidence.

**Why it fails is more interesting than that it fails, and it is a compliment to
the eval:** a threat term only predicts instability if it is *mis*calibrated. Ours
already prices in the material a threat will win, so by the time qsearch resolves
it the score has not moved. The decomposition is not a volatility signal because
the volatile part is already correctly valued.

Caveat kept honestly: this measured root positions of a tactical suite, and RFP
fires at interior nodes at depth ≤6. A test sampling interior nodes could come
out differently. But an idea whose first honest test returns +0.005 does not earn
an 800-game gate ahead of things that have not been tested at all.
`research/ROADMAP.md` keeps the entry with this result attached — items 2 and 3
there (reductions, null-move gating) rest on the same premise and inherit the
same verdict.

**Phase 2 verdict: NEUTRAL, not accepted.** The tuned bundle (31 middlegame
values + 29 endgame partners) against main, 800 games, 0.3s, UHO openings:

| | |
|---|---|
| score | +242 =344 −214 (51.8%) |
| paired Elo | **+12, 95% CI [−5, +29]**, 400 pairs |
| SPRT | ran the full 800 without reaching either boundary |

`eval_check` 0.000000 this time, which is the cache and precision fixes doing
their job. But the result straddles zero, and — the part that decides it — **this
is a self-play measurement of an evaluation change**, which s24 measured as
*overstating* eval gains badly (two concepts gated +55 and +29 in self-play and
transferred ~zero against Stockfish; every *search* gain transferred). So the
instrument that inflates eval results found +12±17. The external number is
plausibly zero.

Not rejected outright either, because the capacity is demonstrably real (54% of
the loss reduction came from tapering, with chess-sensible ratios). The honest
statement is: **the doubled parameter set buys descriptive capacity that this
tuning run could not convert into measurable strength.** Retained as
infrastructure; the weights themselves are not applied. Third consecutive
re-tune to land neutral (s23 +3, this +12) — which is the clearest signal yet
that *re-tuning the existing terms is exhausted* and the remaining eval Elo, if
any, is in terms that do not exist yet. That is Phase 3, and it is where the
effort goes now.

**Tuner (committed).** `research.texel` now fits endgame partners alongside
middlegame values — one flat `("mg"|"eg", key)` parameter list, partners
initialised equal so the fit strictly extends the old one, wide endgame envelope
(0.4×–2.0×) because the point of tapering is that phases differ a lot, and only
partners that actually moved are written. On 20k positions from `texel5.jsonl`,
5 passes:

| parameterisation | loss | vs baseline |
|---|---|---|
| baseline (untuned) | 0.091031 | — |
| middlegame only | 0.090711 | 0.351% |
| middlegame + endgame | **0.090336** | **0.763%** |

Tapering supplied **54%** of the total reduction, and **29 of 31** weights wanted
a different endgame value, with ratios that read like chess rather than noise:
queen mobility 1.67× in the endgame, passed pawns 1.63×, hanging 2.12×, doubled
pawns 0.62×. Loss is not Elo — s23's full retune improved loss 0.57% and gated
NEUTRAL (+3) — so this earns the bundle a gate, it does not settle it.

---

## 2026-08-02 — Session 26: use the cores you have; instruments for finding the leak

**Lazy SMP thread default: physical cores, not a hardcoded 8 — ACCEPTED.**
`play_threads()` returned `min(os.cpu_count(), 8)`, which is wrong twice on a
modern box: `os.cpu_count()` counts *logical* CPUs (20 here), and the cap of 8
left two physical cores idle on a 10-core machine. Replaced with a physical-core
count (Linux: unique `thread_siblings_list` entries; macOS: `hw.physicalcpu`),
capped at `MAX_THREADS`, which went 8 → 16 in `core/csearch.c`.

Measured the scaling curve first, and **the two standard SMP metrics disagreed —
worth recording, because one of them is a trap:**

| threads | depth @ 2.0s (avg of 2) | time to depth 14 (avg of 3) |
|---|---|---|
| 1  | 16.50 | 7.90s |
| 4  | 17.67 | 2.88s |
| 8  | 17.50 | 2.48s |
| **10** | **18.25** | 2.41s |
| 12 | 18.08 | 2.43s |
| 16 | 18.08 | **1.97s** |
| 20 | 17.50 | 1.99s |

Time-to-depth keeps "improving" past the physical core count and picks T=16 —
but T=16 reaches depth 14 on **1.98M nodes where T=1 needs 11.78M**. It is not
6× faster; the parallel search simply *arrives at the label "depth 14" having
examined far less*. Time-to-depth flatters Lazy SMP and should not be used to
choose a thread count. Depth-at-fixed-time peaks at T=10 = the physical core
count, which is also what the hardware predicts (helper threads are compute-bound,
so hyperthread siblings contend rather than search).

Gate (T=10 vs T=8, each side on its own built-in default, 160 games, 0.3s,
**concurrency 1** — only one side thinks at a time, so a game needs at most 10
cores; two concurrent games would put ~18 threads on 10 physical cores and
measure contention instead): **54.4% (+53 =68 −39), paired +30 Elo, 95% CI
[−8, +70]**.

Honest read: **positive but imprecise — the interval grazes zero, so "+30" is not
a claim, and the defensible statement is "a regression is excluded and both
independent metrics point the same way."** Accepted anyway, on grounds the
borderline search features did not have: the mechanism is not a heuristic that
might backfire, it is *using two more cores*, and the depth benchmark agreed
before the match did. On a machine without hyperthreading this is a no-op except
that boxes with 8–16 physical cores now use them all. The coach's verdict path
stays at T=1, so determinism and the C==Python invariant are untouched.

Harness note: gating a change to the *default* thread count needed a new
`research.match --threads default`, which leaves `CC_THREADS` unset so each side
picks its own — both engines inherit one environment, so there was previously no
way to pit two defaults against each other.

**New instruments (not yet findings): `research.postmortem` and
`research.abgate`.** Seven straight guessed techniques came back neutral, so
rather than guess an eighth, two tools to aim the next experiment:

- **`research.postmortem`** — phase-resolved centipawn-loss analysis of real
  games against Stockfish. Analyses every position once at fixed depth and asks
  which phase we bleed in, with the opponent's loss on the *same games* as the
  control (raw cp/move is meaningless without it — endgame positions are sharper
  for both sides). Also reports where our worst move of the game falls, split by
  result, since games are decided by the worst move and the mean dilutes it.
- **`research.abgate`** — the missing eval gate. s24 proved self-play Elo does
  not transfer for eval changes, but differencing two independent
  runs-vs-Stockfish was too imprecise to be practical. This plays BOTH builds
  against the same strength-limited Stockfish over the **same openings in the
  same colours**, so opening difficulty cancels in the per-slot difference
  (common random numbers). Unit-tested, including the property the design exists
  for: the paired interval is tighter than the unpaired one.

**DIAGNOSIS 1 — the endgame is not the leak; the middlegame is.** 200 games vs
SF-2800 (42.8%), every position scored at depth 14, our centipawn loss compared
against *the opponent's loss on the same games* (raw cp/move is meaningless
without that control — endgame positions are sharper for both sides):

| phase | our cp/move | SF cp/move | **excess** |
|---|---|---|---|
| opening | 23.3 | 18.1 | **+5.2** |
| middlegame | 23.4 | 19.0 | **+4.4** |
| endgame | 12.8 | 12.2 | **+0.6** |

**We play endgames at parity with a 2800-rated opponent.** That kills a standing
ROADMAP direction: hand-built endgame knowledge (unstoppable passer, wrong-bishop
draws) is not where the strength is, and would have been a session's work to find
that out. Our worst move of the game also lands in the endgame only 16% of the
time in games we lose, against 30% of our moves being endgame moves — the phase
is under-represented in disasters, not over. The deficit is concentrated where
material is high: most pieces, highest branching factor, shallowest search.

**DIAGNOSIS 2 — 82% of our real blunders are fixed by more thinking time.**
`research.blunders` mined 216 real blunders (≥150cp given up) out of those games
and re-searched each at 10x the time it was played at: **123 search-limited (82%)
vs 27 eval-limited (18%)**. Mined suite kept at `research/suites/blunders_v1.epd`
for reuse. Among the 18% that survive more depth, the concepts most often
favouring our worse move are **threats (9 positions), material (4, but +1330cp of
mass — poisoned-material grabs) and king_attack (4)**. That is the first
diagnosis-pointed eval target the project has had since the king-race work, and
`abgate` can now test it externally.

**METHOD — two traps found and disarmed, both of which had been silently
distorting things:**

1. *A first version of the blunder classifier said 65% of blunders "did not
   reproduce" on a fresh short search.* That looked like a spectacular finding
   about in-game state. It was an artifact: **the search stops on WALL CLOCK, so
   move choice at 0.3s is unstable.** Two 0.3s searches of the same position pick
   different moves **18%** of the time, and replaying a whole game through one
   engine reproduces only **71%** of its own moves. Any classifier resting on a
   short re-search is mostly reading timing jitter, so the tool now keys off the
   long search alone. Worth stating plainly: **at fixed TIME the engine is not
   deterministic even at one thread** — the byte-identical guarantee is a
   fixed-DEPTH property.
2. *Does gating at `--concurrency 8` weaken the engines it measures?* If a 0.3s
   search got fewer nodes under load, every parallel gate and the 2743 calibration
   would be measuring a weaker engine. Checked directly: solo **374,971** nodes
   per 0.3s search vs **~363,000** under 8-way load — a 3% difference, with
   identical depth (11.08 vs 11.17). **Parallel gating is sound**, which retires
   the last doubt about the s25 instrument.

**Log-log LMR table, re-tested at 40x the power — REJECTED, and this time the
bound means something.** The standing LMR scheme keys off the move INDEX alone
(2 plies from move 3, 3 from move 12, capped there) with **no depth term at
all** — a late quiet at depth 20 is reduced exactly as much as one at depth 4,
which no modern engine does. s21 tried the standard `0.85 + ln(d)·ln(m)/2.20`
table and measured "exactly 50%, −0 Elo (95% −90..+90)" over 60 games. That
interval is wide enough to hide a +30 Elo effect completely, and the technique
buys real plies, so it was the best re-test candidate in the log.

Re-implemented (build-once table, `red` clamped to leave a ply; eval untouched →
C==Python 0.000000, perft, 77 tests, tactics 24/24). Gate vs HEAD:
- batch A (400g, openings 0–199): 48.8% (+119 =152 −129), **−9** Elo [−34, +16]
- batch B (400g, openings 200–399): 53.0% (+143 =138 −119), **+21** Elo [−5, +47]
- **pooled 800g: 50.88% (+262 =290 −248), +6 Elo, 95% CI [−13, +25]**

Reverted. s21's verdict stands, but the useful part is the new bound: the modern
LMR table is worth **less than +25 Elo** on this engine, where before we only
knew "somewhere in ±90". Two footnotes worth keeping. First, the benchmark did
NOT reproduce s21's "+1–2 plies deeper" claim (16.33 vs 16.50 avg) — with LMP,
RFP and probcut now doing the shallow-node pruning, there is little left for a
more aggressive LMR table to save. Second, **batch A −9 and batch B +21 is a
30-Elo swing between two 400-game batches**: the confirmation rule matters at
every sample size, not just small ones.

**The three borderline-accepted search features, audited by REMOVAL — CONFIRMED,
collectively +44 Elo.** Singular extensions (+29, CI [−7,+66]), the null-move R
tier (+29, CI [−6,+64]) and LMP (+30, CI [+0,+60]) were each accepted on an
interval that grazed or crossed zero. Three features sitting in the tree on
evidence that would not survive the current instrument is exactly the debt the
"provably stronger" goal is about, so rather than re-gate each addition, gate
their **removal** — one experiment that asks whether the bundle earns its place:

- batch A (400g): 41.9% (+101 =133 −166), **−57** Elo [−82, −32]
- batch B (400g): 45.6% (+121 =123 −156), **−30** Elo [−57, −4]
- **pooled 800g: 43.75%, −44 Elo, 95% CI [−64, −24]**
- → **the three are collectively worth +44 Elo [+24, +64]**. Kept, now on an
  interval that clears zero by a wide margin.

Note the arithmetic: individually they claimed +29/+29/+30 ≈ **+88**, and
measured together they are **+44** — the single-batch estimates *were* inflated
roughly 2×, exactly as the winner's-curse pattern predicts, but the features are
real. Both things are true at once, which is why removal-auditing is worth doing
rather than trusting either the optimistic sum or the pessimistic "borderline".

**Threat weights x0.7, the first diagnosis-pointed eval test — REJECTED (−3 Elo),
and it teaches something about the new tool.** `research.blunders` named `threats`
as the concept most often favouring our worse move (9 of 27 eval-limited
blunders). Threat weights were *guessed* in s22; s23's Texel tuner drove them
into their upper bounds and s24 tested HIGHER and got neutral. Nobody had tested
lower. Scaled the four threat magnitudes by 0.7 (hanging .0562→.0393, pawn
.10→.07, minor .06→.042, rook .04→.028; `initiative` left alone as a separate
hypothesis). Faithful: `gen_eval_data` + rebuild, C==Python 0.000000, perft, 77
tests, tactics 24/24. Gate vs HEAD: batch A 49.9% (−1), batch B 49.4% (−4),
**pooled 800g 49.62%, −3 Elo, 95% CI [−22, +16]**. Reverted.

Two things worth keeping from this. First, **the threat weights sit on a
plateau**: higher does nothing (s24), 30% lower does nothing (now), both measured.
Second, and more useful: **concept attribution names the concept that DIFFERS
between our move and the best move, not the concept that is WRONG.** Those are
not the same claim, and the natural reading of a "top culprit" table is the wrong
one. `threats` shows up most often because it is a high-variance term that moves
a lot between candidate moves — not because its weight is miscalibrated. Future
sessions should treat that table as a place to look, never as a diagnosis.

*(Method note: the first attempt at this change silently shipped a Python eval
that the C core did not mirror — a `&&` chain failed to run `gen_eval_data.py`,
so weights.py and eval_data.h disagreed. `eval_check` caught it immediately with
max |C−Python| = 114.5 over 4286 positions. The sacred invariant did exactly its
job.)*

**Where the remaining time actually goes (cycle-profiled), and two refactors
declined on the evidence.** No `perf` on this box, so the C core was temporarily
instrumented with `__rdtsc` counters. Over five 1.0s searches:

| region | share of search | notes |
|---|---|---|
| `eval_core` | **29.0%** | confirms s16's 32–34% "faithfulness tax" |
| `order()` | **18.4%** | of which `see()` is 6.8% of total (6.8M calls, 155 cyc each) |
| qsearch first-ply check scan | **10.2%** | 517k nodes, finds only **0.56** checking moves each |
| everything else | ~42% | movegen, make, TT probes, recursion — diffuse |

*Deferred move ordering — NOT DONE, and the measurement is why.* `order()` runs
BEFORE any move is searched, so a node that cuts on its TT move paid to score
(with SEE) and sort ~35 moves it never looked at. The obvious fix is to try the
TT move first and only order if it fails to cut. Counted how often that would
help: 58.6% of ordered nodes cut on their first move, but only **26.0%** cut on
the TT move specifically — so deferring saves 26% of 18.4% = **~4.8% of search
time, worth ~+5 Elo**. That is below what even an 800-game gate resolves (±19),
and it would break byte-identity (the TT subtree updates history before the
remaining moves get ordered), so it could only be validated by a match it is too
small to win. Declined. Full staged generation (captures before quiets) tops out
around 8–10% by the same arithmetic, and is blocked anyway by the history table
being unbounded, which breaks the score bands staging relies on.

*Bigger eval hash — NOT DONE.* EH_BITS 20→22 cut `eval_core` calls 13.5% and
looked like a 7% win in the profiler, with **byte-identical node counts**
(635,444 and 2,459,264 at fixed depth, both builds) confirming the search shape
is untouched. But on a fair wall-clock basis it is only **+1–2% nps at 2.0s and
~0 at 0.3s** — the extra cache pressure eats the hit-rate gain, the same
mechanism that sank the bigger-TT experiments twice before. Not worth 48MB for an
unmeasurable gain. (EH_BITS 24 is actively worse.)

**Quiescence first-ply quiet checks: audited by removal — KEPT, and the reason is
a TIME-CONTROL FLIP that a blitz gate alone would have got wrong.** This block is
10.2% of search time and finds 0.56 checking moves per node, so most of it is
scanning quiets that give no check — a fat target. Gated its removal:
- batch A (400g): 52.4% (+137 =145 −118), **+17** Elo [−8, +41]
- batch B (400g): 50.4% (+139 =125 −136), **+3** Elo [−24, +29]
- **pooled 800g: 51.38%, +10 Elo, 95% CI [−10, +29]** — neutral, but with a
  positive point estimate and 10% of the search time freed.

By the usual rule ("a neutral change doesn't earn its complexity", applied in
reverse to a removal) that argues for deleting it. So before deciding, an
independent quality measure on the 216 REAL positions the engine got wrong in
games (`research/suites/blunders_v1.epd`, Stockfish-verified best moves):

| | 0.3s (gate TC) | 1.0s (nearer real use) |
|---|---|---|
| without the checks | 42/216 (19.4%) | 52/216 (24.1%) |
| **with them** | 37/216 (17.1%) | **57/216 (26.4%)** |

**The sign flips with time control**: at blitz the 10% speed saving wins, with
more thinking time the tactical vision wins. The analysis board — the actual
product — runs long thinks, and every gate this project runs is at 0.3s. Kept.
The general lesson is uncomfortable and worth carrying: **a 0.3s gate is not
neutral evidence about a feature whose value grows with depth**, and the mined
blunder suite is a cheap second instrument for exactly that question.

**RFP_MARGIN 90→130 — REJECTED at 1.0s, and it calibrates the suite screen.**
The long-TC parameter sweep (below) nominated this one: it led the mined blunder
suite by +8 positions at 1.0s against a ±2 noise floor, and s24's 0.3s sweep had
already seen margin 110 come in at "+12, noise" on an underpowered gate — same
direction, twice. Gated at **1.0s** (where the signal was, and the project's
first long-TC Elo gate at scale): batch A 49.0% (−7), batch B 49.8% (−2),
**pooled 800g 49.38%, −4 Elo, 95% CI [−23, +14]**. Reverted.

The useful part is what it says about the suite: **that screen is trustworthy in
one direction only.** `blunders_v1.epd` is built from positions the BASELINE got
wrong, so every variant enjoys a free decorrelation bonus. Baseline-wins is
therefore strong evidence (it overcame a handicap) — which is why the quiescence
-check decision above stands — while variant-wins is weak, as this +8 → −4
demonstrates. The bias was flagged when the suite was built; now it is measured.

**FIXING THE LOOP ITSELF (the session's most valuable output).** The research
cycle had a throughput problem worth naming: every gate ran a fixed 800 games
(~50 min at 0.3s, 2.4h at 1.0s), so ~6 hypotheses could be tested in a 12-hour
block. Three specific defects, all mine:

1. **SPRT was implemented, self-tested, wired into the harness — and never
   used.** Every gate played all 800 games even when the verdict was obvious by
   game 200.
2. **No tiering.** Screening and confirmation got the same expensive treatment.
3. **Worst: hypotheses were chosen without regard to validation cost.** A change
   that leaves the search tree byte-identical is validated by node counts and
   nps in *minutes, with zero games*. That class was available and mostly ignored.

Built `research/screen.sh`: the variant lives in **its own worktree** (main never
leaves the baseline — no build/revert churn, no risk of gating a dirty tree), the
eval invariant is checked before any game is played, and SPRT stops the run as
soon as it is decisive. Also added `research.match --ours-cwd` to make that
possible. Measured speedup: a known-bad control (null-move disabled) is rejected
in **76 games / 5 min** instead of 800 / 50 min; a mildly-bad change in ~300
games / 10 min. **The screen nominates; it never accepts.**

**LMR for late captures — ACCEPTED (+9 Elo), the session's one real gain.** LMR
only ever reduced QUIET moves. Bad captures sort last (score −1e6+SEE), so a
capture appearing late in the list is almost always a losing one, and searching
it at full depth is waste. One line. It had never been tried because
"LMR for quiets" reads as "LMR is done" — precisely the sort of gap that only
turns up when screening is cheap enough to try things on spec.

The screen is EXCLUDED from the estimate: it read **+24 Elo, 95% CI [+6, +43]**
over 754 games — an interval that excludes zero — but this change was selected
as the best of five candidates, so that interval is not a real 95% interval.
Independent evidence only:

| batch | score | Elo |
|---|---|---|
| 0.3s, openings 400–599 | 52.4% | +17 [−10, +44] |
| 0.3s, openings 600–799 | 48.9% | −8 [−35, +19] |
| 0.3s, openings 800–999 | 52.4% | +17 [−10, +44] |
| 1.0s, openings 400–599 | 51.5% | +10 [−15, +36] |
| **pooled, 1600 games** | **51.28%** | **+9, 95% [−4, +22]** |

Accepted on the balance of three things rather than on significance: it
replicated in three of four independent batches, held at two time controls, and
the mechanism is a missing CASE in an existing heuristic rather than a new
heuristic that might backfire. Benchmark agrees (avg depth 16.50 → 16.83). The
1.0s tie-breaker was **pre-registered** — its decision rule fixed before the
result was seen — because by that point the analysis had accumulated enough
forks to manufacture whichever answer was wanted.

**Thirteen techniques screened, one accepted.** Batches 2 and 3 went 0-for-8:

| technique | result | games |
|---|---|---|
| SEE-filtered quiescence checks | −2 | 643 |
| eval-scaled null-move R | −2 | 665 |
| reduce killers/countermoves less | −23 | 239 |
| ProbCut margin 180→120 | +4 | 800 |
| exempt checking quiets from LMR | −12 | 363 |
| singular extension from depth 6 | −17 | 320 |
| qsearch delta margin 200→100 | −11 | 430 |
| aspiration delta 20→10 | −13 | 370 |

Two of these are worth noting. *Exempting checking moves from LMR* is standard
everywhere else and lost here — because a checking move already gets the check
extension at the child, so declining to reduce it double-counts. And four of the
eight are first-guess constants behind large accepted features (probcut margin,
qsearch delta, aspiration width, singular depth) that had never been swept
against actual games; **all four turn out to be at or near their optimum
already**, which is the same verdict the long-TC sweep reached from the other
direction.

**EVAL: two new multiplicative modifiers — both REJECTED, and one of them is the
session's cleanest lesson about its own instrument.** (William: "have you
considered adding any other nonlinear features? … we need to get more creative
with making the evaluation function better.") The modifier framework from s24
existed to express what a concept SUM cannot, and had sat with exactly one term
in it — opposite-coloured bishops, whose condition (one bishop each and *no
other pieces at all*) is so narrow it essentially never fires, which is why it
originally gated as noise.

*Broadened OCB* — allow the rooks-on case at a milder factor (0.8), queens still
excluded because queens make opposite bishops sharper, not drawer. Faithful
(C==Python 0.000000). **−19 Elo, rejected.** Opposite-bishops-with-rooks is not
as drawish at this engine's level as the folklore says.

*Winning difficulty* — a pawnless leader whose non-pawn edge is under a rook
cannot convert (K+B vs K, K+2N vs K are dead draws; R vs minor and R+B vs R are
book draws). Integer piece counts only, so the C mirror is exact by construction.
This produced the strongest screen of the entire session: **SPRT accepted H1 at
176 games, +68 Elo [+29, +109]**. Then, on independent openings: **+28, then
−16 — pooled +6 [−14, +26]**.

The 44-Elo gap between those batches looked like a real defect in the rule, and
there IS one: with N=B=3, R=5, Q=9, "edge below a rook" also catches **Q vs R
(edge 4)** and **Q vs B+N (edge 3)**, which are theoretical WINS being damped by
0.65. So v2 additionally required equal queen counts, removing every
queen-vs-lesser case. v2 screened **−8** — *worse than v1 on the same openings*.

That kills the diagnosis and gives the real explanation: **v1's +68 was a false
positive.** ~20 SPRT screens were run this session at alpha=0.05, so roughly one
spurious H1 was expected, and this was it. The lesson is not that the modifier
idea is bad — the framework worked mechanically throughout, C==Python held at
0.000000 for every variant — but that **an SPRT screen accepting H1 means
"worth confirming", never "true"**, and at this volume of screening a rule for
handling multiplicity is not optional. The standing "screen nominates,
confirmation decides" discipline caught it without ever putting it in the tree.

*Bishop pair scaled by pawn count (Kaufman)* — the pair is worth little with the
board full of pawns and a great deal once it opens, an INTERACTION between
material and pawn structure that a sum of independent terms cannot express.
Deliberately **centered on 12 pawns** (roughly the average in the positions the
weight was fitted on) so the mean value of the term is unchanged and only its
spread is new — this is what makes it a test of the shape rather than of a
rescaling, and it is exactly the discipline the concave-mobility failure taught.
Faithful (C==Python 0.000000). **+7 Elo [−11, +25]** over the full 800 games.

Weakly positive and unresolved — as is `iir_shallow` (+7) from the search batch.
Neither is evidence: across 24 screens with ±19 intervals, several landing near
±7 by chance is exactly what a null predicts, and the lmrcap precedent says a +7
screen is worth ~+3 after selection is accounted for. Both are recorded as open,
neither is in the tree.

**METHOD TEST (running): are eval effects systematically under-measured at
0.3s?** This is the most valuable open question in the project, and it follows
from this session's own diagnosis. `research.blunders` measured that **82% of
real blunders at 0.3s are fixed by more thinking time** — at blitz, SEARCH error
dominates and eval error is a small residual. If that is right, an eval
improvement should be *systematically under-measured at 0.3s and grow with the
clock*, which would mean every eval result this project has ever gated is an
underestimate, and would explain three sessions of barren eval work far better
than "the eval is at its ceiling" does.

First probe: `bpair_pawns`, re-run on the **same 800 games and same openings** at
1.0s so that only the clock differs. Result: **+7 [−11, +25] at 0.3s → −10
[−27, +6] at 1.0s.** No amplification.

**But that probe was too weak to answer the question, and saying so matters more
than the number.** A probe whose true effect is ~0 cannot demonstrate
amplification — three times nothing is still nothing. Both intervals span zero,
so all this really established is that bishop-pair-by-pawn-count is neutral at
both time controls. The test needs a probe with a *real, measured* 0.3s effect.

Second probe (running): **remove backward pawns and connected pawns.** Those were
accepted in s24 on 0.3s self-play at +55 and +29 — a large, real, well-documented
blitz effect, which is exactly what the first probe lacked. Gating their removal
at 0.3s and then over the identical 800 games at 1.0s asks the question directly:

- removal costs **more** at 1.0s → eval knowledge is worth more with the clock,
  and every eval gate this project runs at 0.3s is an underestimate;
- removal costs **the same** → three sessions of barren eval results are real,
  not an artifact of measuring at blitz.

**RESULT — the same at both, and it answers two questions at once:**

| removing backward + connected pawns | score | Elo |
|---|---|---|
| at 0.3s (771 games) | 49.8% | **−1 [−20, +18]** |
| at 1.0s, same openings (800 games) | 49.5% | **−3 [−21, +14]** |

1. **The time-control hypothesis is dead.** A probe with a large documented 0.3s
   self-play effect shows no amplification whatsoever when the clock triples. Eval
   effects are *not* systematically under-measured at blitz, so the barren eval
   results of the last four sessions are real rather than an artifact of the
   instrument. That closes the most plausible remaining excuse for the eval
   ceiling, and it is worth more than another neutral experiment would have been.

2. **Backward pawns and connected pawns are worth ~0 Elo — at any tested TC.**
   They were accepted in s24 at **+55 and +29 self-play** (+84 together), and s24
   then measured that the pair moved external strength by ~zero. This closes that
   loop: they do not move self-play strength either, *now*. The +84 was
   self-play against a lineage that lacked them — precisely the blind-spot
   artefact the s24 lesson describes, measured here directly rather than inferred.

**They are being KEPT, and the reason is not strength.** They cost roughly 10% of
eval time (backward 6.0% + connected 4.1% by the concept profile, so ~3% of
search) and buy no measurable Elo. But this engine's purpose is explanation, and
"your d6 pawn is backward on a half-open file" is exactly the kind of thing the
coach exists to say — the same argument that kept the OCB modifier. The honest
labelling is what changes: **these are coach features, not strength features**,
and the LOG should stop implying otherwise. Whether the 3% is worth the
explanations is William's call, not a research question.

*Trapped pieces* — a NEW additive concept rather than a reshaping, chosen
specifically to dodge the tuning confound below: leave mobility alone and add a
separate penalty that fires only at the cliff edge (zero safe squares), since
linear mobility rates "cramped" and "trapped" as points on the same gentle slope
when the real difference is an order of magnitude. Faithful (C==Python 0.000000).
**−16 Elo, rejected** — and the *reason* is the useful part.

**New instrument: `research/firing_rate.py`.** Before trusting that gate, the
firing rate was measured, and the concept turned out to fire **8 times on the
STARTING POSITION** — both bishops and both rooks, both colours, all of which
have zero safe squares behind their own pawns. It was never measuring trapped
pieces; it was measuring *undeveloped* ones, which the piece-square tables
already price. Tightening it to "zero mobility AND under attack" fires in
**0.5%** of real positions — too rare for any affordable number of games. Both
verdicts were reached **without playing a single game**.

That check is now a permanent tool, and pointing it at the existing eval
immediately paid again:

| | fires in | note |
|---|---|---|
| `mate_drive` | 1.4% | below the gateable threshold |
| **`ocb` modifier** | **0.0%** | **never fires in 216 real positions** |

**The opposite-bishop modifier is, in practice, dead code.** s24 kept it "not
for Elo but because it makes the eval correct where it fires" — which remains a
defensible reason, and it is the framework's proof-of-concept — but it should be
labelled as correctness rather than strength, and *it was never measurable*.
That retroactively explains its +17 [−45, +81] gate, and it is the same failure
mode the broadened-OCB experiment above was trying to fix.

Standing rule added to the handoff: **run `research.firing_rate` before gating
any new or changed eval concept.** A term firing under ~2% of the time cannot be
resolved by any number of games this project can afford, and a term that fires
on the start position is measuring something other than its name.

*Concave mobility* — the one large concept still modelled as a straight line.
`weight * (count - typical)` says a queen's 20th square is worth as much as her
14th, and that a trapped knight is only three weight-units worse than a
comfortable one; neither matches chess, and strong engines all use a concave
curve. Replaced with `w * 2*sqrt(T+1) * (sqrt(n+1) - sqrt(T+1))`, chosen to be
scale-COMPATIBLE rather than a free re-parameterisation: it is zero at the
typical count and has slope exactly `w` there, so only the tails bend. (The
C==Python invariant survives `sqrt` exactly — IEEE requires correctly-rounded
square root, and the operation order was written identically on both sides;
verified 0.000000 over 6204 positions.) **−37 Elo, rejected in 171 games.**

The likely reason is the same one that has now sunk several eval experiments:
the mobility weights were Texel-tuned *against the linear form*, so bending the
curve re-prices every piece relative to weights fitted for a different shape.
Testing it properly would require a full re-tune under the new functional form —
and the tuning flywheel has been measured as converged three times. That is a
real limit on eval experimentation here, and worth stating plainly: **any change
to a concept's FUNCTIONAL FORM is confounded with the weights fitted to the old
form, and this project cannot currently afford to re-tune per experiment.**

**Mining Stockfish's source and commit history (William's suggestion) — and the
single most useful thing it produced was a calibration, not an idea.** Cloned
the repo (7196 commits) and read `search.cpp`'s step list against ours. *Ideas
only — SF is GPL, so nothing was copied; everything below was implemented
independently from understanding.*

The calibration first, because it reframes the whole exercise: **modern
Stockfish improvements are sub-1-Elo each.** The "small ProbCut" commit passed
with SPRT bounds `{0.25, 1.25}` over **33,440 games**. Our instrument resolves
±19 Elo at 800 games. So copying modern SF micro-tuning is not merely low-yield,
it is *unmeasurable here* — and those constants are tuned to SF's own eval and
search shape anyway. What is worth mining is **structural signals we lack
entirely**, not tuned numbers.

By that filter SF's step list turned up exactly one real gap, and four ideas:

| from SF | result |
|---|---|
| **cutNode** — thread "is this node expected to fail high" through the search | **+0 [−18, +18]**, 777 games |
| TT-based ProbCut (a far-above-beta lower bound at depth−4 cuts immediately) | −14 |
| `improving \|= staticEval >= beta` | −18 |
| IIR also on a SHALLOW TT entry, not just a missing one | +7 [−11, +26], weak |
| `improving` skipping the in-check sentinel (our own bug-shaped variant) | −7 |

**cutNode deserves the note.** We genuinely had no such concept — we distinguish
only PV from non-PV, lumping together cut nodes (expect a cutoff) and all-nodes
(expect to fail low), which want opposite treatment. SF uses it in five places.
Threading it through and reducing harder at cut nodes measured **exactly zero**.
The likely reason is depth: SF reduces 5–6 plies at depth 30+, where an extra
ply of reduction on a doomed move is cheap; we search depth ~11, where our LMR
already caps near 4 and there is simply no room. Same story as the log-LMR table
(more reduction, neutral) and reduce-killers-less (less reduction, −23). **Our
reduction schedule is at an optimum for the depth we actually reach**, and
importing a stronger engine's tuning does not transfer across that gap.

*(`improving` also carries a real latent bug worth recording even though fixing
it lost: in-check plies store a −S_MATE sentinel in `seval`, so any node two
plies after a check compares against −100000 and is declared "improving"
unconditionally, silently disabling an extra ply of LMR and loosening LMP there.
Fixing it properly gated −7, so the accidental behaviour is apparently the
better one — but the next person to read that line should know it is accidental.)*

**Five untried standard techniques, screened in 110 minutes** (the old workflow
would have spent 250):

| technique | screen result | games |
|---|---|---|
| mate-distance pruning | −18 Elo, REJECTED | 312 |
| bounded history with gravity | −29 Elo, REJECTED | 227 |
| double extension (singular ×2) | −3 Elo, REJECTED | 622 |
| **LMR for late captures** | **+24 Elo [+6, +43]** | 754 |
| recapture extension | (patch anchor wrong; re-run) | — |

Two of these deserve comment. *Bounded history with gravity* losing is a genuine
surprise — the history table is **unbounded**, entries just accumulate depth²
forever, which is unusual and in principle overflowable; the standard fix made
things clearly worse, which is one more entry in this engine's long record of
move-ordering changes failing. And *mate-distance pruning* is finally off the
ROADMAP after several sessions of sitting there unimplemented.

**Is the engine mis-tuned for the regime it is actually used in? No — four
"more aggressive at depth" variants all lose at 3.0s.** Every tuned parameter in
this engine was swept at 0.3s, the analysis board thinks far longer, and the
quiescence-check result above proves a sign CAN flip with time control. So the
obvious worry is that the whole parameter set is blitz-tuned. Screened the four
most time-control-sensitive knobs on the mined blunder suite (216 real positions,
Stockfish-verified best move) at 1.0s and 3.0s:

| variant | 1.0s | 3.0s |
|---|---|---|
| **baseline** | 56/216 | **79/216** |
| quiescence quiet-checks extended to qd≤1 | 56 | 75 |
| LMP_DEPTH 5→8 | 54 | 75 |
| RFP_DEPTH 6→8 | 56 | 71 |
| TT_BITS 22→24 | 57 | 70 |

**The baseline wins at 3.0s against all four**, by 4–9 positions against a ~±2
noise floor (measured: re-running the baseline gave 56 and 57 on separate runs,
the fixed-time jitter again). RFP_DEPTH 8 and TT_BITS 24 are clearly harmful at
long TC — the third independent rejection of a bigger transposition table, now at
the deep regime where it should have had its best case.

The bias in this test runs **against** the baseline: the suite was mined from
positions the baseline itself got wrong, so every variant enjoys a free
decorrelation bonus. Losing anyway makes it strong evidence. Conclusion: the
0.3s-tuned parameters are also right at long TC, and the blitz-tuning worry is
not supported. That closes the largest open question in the s26 handoff without
spending 2.5 hours per long-TC match gate — the mined suite paid for itself.

**HEADLINE: what the engine is actually worth as it is really played — ~2840
external.** Every external number this project has ever quoted is
SINGLE-THREADED, because gates export `CC_THREADS=1` to stay clean. But nobody
plays it that way: UCI, the web opponent and the analysis board all run
full-width Lazy SMP. s20's "+140/+187 for SMP" was **self-play**, and s24/s25
proved self-play overstates. So: the same SF-2800 anchor, same book, same 0.3s,
concurrency 1 (our side wants the whole machine), full-width T=10.

| config | vs SF-2800 | Elo vs anchor |
|---|---|---|
| single-thread (400 games) | 41.2% (+83 =164 −153) | −61 [−88, −35] |
| **full width, T=10 (160 games)** | **55.0% (+60 =56 −44)** | **+35 [−8, +79]** |

**Lazy SMP is worth +96 external Elo, 95% CI [+45, +147]** — so the engine as
actually played sits at roughly **2840** (2743 single-threaded + 96), give or
take ~55 once both measurements' error is carried.

Two things fall out of this. First, it closes the loop on the question that
started the whole search push in s24: William was losing to a chess.com "Hikaru
2820" bot, and the honest single-threaded answer then was "we are ~2650, that is
expected". **The engine as he actually runs it is now ~2840 — at or slightly past
that bot's level.** Second, and more useful for future work: SMP's self-play
claim was +187 and it delivered +96 externally, a ratio of **0.51**. The RFP+LMP
search push measured +144 self-play → +80 external, a ratio of **0.55**. Two
independent search changes, both transferring at ~half their self-play value.
That is now a usable planning rule: **for SEARCH changes, expect roughly half the
self-play number externally** (eval changes, per s24, transfer ~0).

Caveats kept honest: 160 games is a wide interval, the anchor Stockfish is
1-threaded (standard, but it is a handicapped opponent whose own scaling is not
measured), and this is 0.3s — the analysis board's long thinks may scale
differently, which is untested.

**And the finding that most deserves to outlive this session: the removal build
searched +3.2 plies DEEPER and played 44 Elo WORSE.** Disabling the three took
avg benchmark depth from 16.50 to **19.67** and nps from 2.83M to 3.51M, because
singular extension's verification search is expensive. Nominal depth is not
strength — an extension spends nodes buying *quality* on forced lines, and the
depth counter cannot see that. Combined with the SMP metric trap earlier this
session (time-to-depth picked T=16 while depth-at-fixed-time picked T=10), the
rule is now well evidenced: **on this engine, every depth-shaped proxy has lied
at least once; only the match decides.**

---

## 2026-08-01 — Session 25: migrated to WSL2; the measuring instrument, rebuilt

s24 ended with both levers near their ceiling and one hard lesson — self-play
gates do not measure external strength for EVAL changes. The HANDOFF's plan was
therefore instrument-first: prove the new parallel harness is unbiased, then make
external Elo repeatable, and only then resume strength research. This session did
that, on a new machine.

**Machine migration (macOS -> Windows/WSL2).** The POSIX C core built unchanged;
the port needed exactly one fix — `core/libcengine.so` was missing from
`.gitignore` (only the macOS `.dylib` was listed). Stockfish 18 installed to
`~/.local/bin` without root (no passwordless sudo on this box; everything resolves
it via `shutil.which`, so no code change). **All sacred invariants hold on the new
box: C eval == Python eval to 0.000000 over 6204 positions, perft ALL PASS, 57
fast tests green, tactics 24/24.**

New hardware: i9-10900K, 10 physical cores / 20 threads, 23 GB RAM, 918 GB free
(the Mac was at 99% disk, which had been throttling how many baseline worktrees
could exist at once). It is **~1.7x SLOWER per core** than the Mac — 2.62M vs
4.37M nps on the same benchmark positions — but with parallel gating the *total*
throughput is several times higher, and throughput is what actually rate-limits
this research loop. A 600-game measurement now costs 38 minutes.

**Harness bias check (HANDOFF item 2) — PASSED.** The concurrency support is
worthless if parallelism favours a side, so: the engine vs a byte-identical copy
of itself (md5-verified same `.so`, separate worktree), 400 games, 0.2s,
concurrency 8, UHO book. **51.0% (+135 =138 -127), paired +7 Elo, 95% CI
[-19, +33]** — no detectable bias. CPU accounting confirms the parallelism is
real and uncontended: 124m28s CPU in 16m03s wall = 7.75x on 8 workers. Note the
big.LITTLE core-class hazard that motivated the check does not exist here (10
identical cores), so this is a cleaner machine for parallel gating than the Mac.

**`research.calibrate` (HANDOFF item 3) — external Elo, measured properly and
tracked.** The ROADMAP had listed the automated ladder *runner* as missing; this
is it, plus three fixes to how the number was computed:

- *It runs the ladder.* Previously the anchors were played by hand and the counts
  typed into `research.ladder_anchor`.
- *Draws are modelled.* `ladder_anchor` treats a 0/0.5/1 chess score as a
  binomial — the same draw-blind approximation already fixed for match gates in
  s25's harness upgrade. `calibrate` fits a trinomial with the BayesElo draw
  model and a nuisance `draw_elo` maximised out. Measured effect on simulated
  ladders: **+-51.9 vs +-56.3 Elo at 40 games/anchor (coverage 97% vs 100% — the
  binomial is over-conservative), +-26.6 vs +-28.8 at 150/anchor.** Modest, but
  free and correct.
- *Two intervals, deliberately.* A profile-likelihood CI (model-based) and a
  **paired bootstrap** over colour-swapped game pairs (assumption-light, catches
  model misfit and the correlation inside a pair). They are meant to be compared;
  if they disagree, trust the bootstrap.

`research/match.py` grew a reusable `run_match()` (extracted from `main()`, same
behaviour) so calibrate drives the real harness rather than reimplementing the
pairing/concurrency logic. Every run appends to `research/data/elo_history.json`
({commit, date, tc, anchors, W/D/L, elo, ci, machine, SF version}).

**The estimator is unit-tested, not just used.** `tests/test_calibrate.py` (12
fast + 1 slow) simulates ladders from a KNOWN rating and checks the fit recovers
it, that the fit really is the likelihood maximum, that more games tighten the
interval, and — the one that matters — that **the 95% interval covers the truth
~95% of the time** over 40 simulated ladders. A rating estimate the whole loop
leans on should not be trusted on the strength of its docstring.

**Pilot (3 anchors x 40 games) found a real misfit, and changed the anchor set.**
Crossover ~2725, but the residuals were **+4.8% at SF-2500 and -8.7% at SF-2900**:
our score curve is *steeper* than the logistic, so a wide ladder drags the single
fitted number around depending on which anchors are in it. Distant anchors also
carry little information per game. So the default anchor set is now a fixed, tight
**2600/2700/2800** — whatever misfit remains is then a constant offset that
cancels when comparing one run to the next, which is what a tracking instrument
actually needs. (The 40-game pilot also scored 52.5% vs SF-2700 where 200 games
gave 57.8% — a 5-point swing, and a compact illustration of why the old
40-games/anchor ladder could not resolve anything.)

**Baseline recorded: external Elo 2743, 95% CI [2717, 2769] (+-26).**

| SF anchor | our score | model expects | resid |
|---|---|---|---|
| 2600 | 67.0% (+110 =48 -42) | 67.6% | -0.6% |
| 2700 | 57.8% (+85 =61 -54) | 55.4% | +2.3% |
| 2800 | 39.8% (+39 =81 -80) | 42.7% | -3.0% |

600 games, 0.3s, single-thread, UHO book, Stockfish 18 anchors; paired bootstrap
[2718, 2767] agrees with the profile interval to 1 Elo, and residuals stay within
3%, so the logistic is a good local fit over this band. **This is the number to
beat from now on, and it costs 38 minutes to re-measure — where the s24 ladder
gave +-100 Elo and could not tell a +80 Elo search push from noise.** It also
confirms s24's honest "~2700-2740" estimate, now with a real error bar.
Caveats worth keeping: Stockfish 18's `UCI_LimitStrength` scale is its own, not
FIDE and not chess.com's, and this box's slower cores mean 0.3s here buys fewer
nodes than 0.3s on the Mac — so the number is comparable to FUTURE runs on this
instrument, not to the Mac-era anchors.

**Capture history — REJECTED (−5 Elo over 800 games), and the first gate that
actually earns the word "neutral".** With the instrument rebuilt, the first
research target was the one standard ordering technique genuinely missing: quiets
have had a learned signal (butterfly history) since early on, but captures were
ordered purely by **SEE — a static material verdict that returns 0 for every even
trade**, so it cannot separate two equal-SEE captures of which only one refutes
anything here. Added `caphist[side][piece][to][victim]`, updated with the same
bonus/gravity scheme as quiet history (reward the capture that caused the cutoff,
penalize the captures tried before it), and folded into the good-capture tier as
`100000 + SEE*16 + clip(caphist, ±4000)` — SEE still dominates any ≥250cp
difference, capture history only breaks ties. C-search only, so eval untouched.

Screens were mildly *encouraging*, which is the point of the story: eval
0.000000, perft, 69 tests, tactics 24/24, and the benchmark moved the right way —
**avg depth 16.50 vs 16.33, nps 2.80M vs 2.62M (+7%)**. The tree really did get
cheaper. It just didn't get better:

- batch A (400g, openings 0–199): 51.0% (+131 =146 −123), paired **+7** Elo [−19, +33]
- batch B (400g, openings 200–399): 47.5% (+116 =148 −136), paired **−17** Elo [−43, +8]
- **pooled 800g: 49.25% (+247 =294 −259), −5 Elo, 95% CI [−24, +14]**

Reverted (the rebuilt core is md5-identical to the baseline worktree's again).

Two things make this negative more useful than the six neutrals that closed s24.
First, **the control**: the A-vs-identical-A harness check scored 51.0%/+7 — the
*same* numbers as batch A. Batch A was literally indistinguishable from playing
the engine against itself, which is the clearest possible statement that nothing
happened. Second, **the CI excludes anything above +14 Elo**. The old instrument
returned "50%, ±90" and could not distinguish "no effect" from "a real +30 we
should keep"; this says capture history is worth less than +14 Elo on this engine,
which is a fact rather than a shrug. That is what the 800-game gate bought, and it
cost 50 minutes.

*Why it lost, mechanistically:* this is the fourth ordering experiment to come
back neutral-or-worse (continuation history +40% nodes, history-modulated LMR
−47, root-move ordering by previous score, now capture history), and they share a
cause. The move that a capture-ordering table would promote — the one that
actually refutes the node — is overwhelmingly *already* the TT move from a
previous iteration, and the TT move is searched first regardless. Capture history
only reorders the moves after it, which the search was going to refute cheaply
anyway. The +7% nps confirms it made the tree marginally cheaper without making
the *choice* better. This engine's ordering is a genuinely strong local optimum,
now established five ways.

**Session 25 ledger.** No Elo gained, and that is the honest headline. What the
session produced instead is the thing s24's handoff said was the blocker: an
instrument that can resolve the effects still on the table. External strength is
now a tracked number (2743 ±26, re-measurable in 38 minutes), gates run ~8× faster
with the parallelism proven unbiased against a byte-identical control, and the
first hypothesis run through it got a verdict with a ±19 error bar instead of ±90.

---

## 2026-07-24 — Session 24: external Elo calibration + true 2nd-best move (MultiPV)

**Motivation (from William, playtesting):** vs the chess.com "Hikaru 2820" bot on
the analysis board we lose/draw; and the board's *2nd* recommendation was often
nonsensical. Both are real signals — investigated both.

**True Elo calibration.** All internal Elo numbers were self-play-chained (each
"+X" measured vs our own prior version at 0.3s), which inflates. Anchored to an
external scale: single-thread ConceptChess vs Stockfish UCI_LimitStrength, 30
games each at 0.3s, sequential (no CPU contention), alternating colors.

| SF anchor | our score | Elo vs anchor |
|---|---|---|
| 1800 | 98% (+29 =1 −0) | +708 (saturated) |
| 2100 | 87% (+26 =0 −4) | +325 |
| 2400 | 73% (+20 =4 −6) | +176 |
| 2700 | 45% (+4 =19 −7) | −35 |

Clean monotonic trend; 50%-crossover ≈ **2650**. So single-thread true strength
≈ **Stockfish-2650 at 0.3s** — the self-play ~2750 claim was ~100 Elo optimistic
(real, but inflated). A 2650 engine losing/drawing to a 2820 bot is *expected*
(~120 Elo gap ≈ opponent scores ~2/3); it is not evidence of over-rating.
Caveats: (a) SF LimitStrength is imperfect and its scale ≠ chess.com's; (b) this
is 0.3s blitz — long-TC (how the board is actually used) may show a wider gap
since SF scales better with time. A long-TC spot-check is a follow-up.

**True 2nd-best move (MultiPV).** ACCEPTED, committed. Root cause: a plain
alpha-beta search scores only the *best* root move exactly — all others fail low
against best's alpha and return an upper bound, so the reported "second" was a
move-ordering artifact. Fix: when the GUI asks (`c_set_multipv(1)`), an extra
iterative-deepening root pass excludes best with a fresh full window, scoring the
real 2nd exactly. OFF in play (zero cost; UCI never asks). Verified vs a
brute-force ranking of every root move (start/italian/kiwipete/deep-endgame all
match). Eval untouched: C==Python 0.000000 over 6204 pos; 47 fast tests green.
Also unblocks the contrastive-alternative explanation the C search couldn't do.

**Tapered N/B/R/Q PST (the PeSTO gap).** REJECTED (neutral), reverted. Pawn+king
PSTs were already MG/EG-blended by `ctx.phase`; N/B/R/Q used a single table each.
Added principled EG tables (knights centralize harder, rooks favor 7th/activity
over the dead a/h penalty, bishops/queens centralize), blended identically.
Faithful: C==Python 0.000000 over 6204 pos, 47 tests green.
Gate vs pre-taper (single-thread, 0.3s):
- batch A (balanced openings, 80g): 54%, +30 Elo (95% −46..+110) — promising.
- batch B (UHO, 120g, higher power): 50% (+35 =49 −36), −3 Elo (95% −66..+60).
Batch A was winner's-curse optimism again; the higher-power UHO batch says
neutral. *Why:* the Michniewski MG tables already encode centralization and the
dominant phase effect (king activation) was already tapered — little headroom
left. Reverted (protocol: accept eval changes only if clearly positive).
Hypothesis preserved: this specifically improves *deep-endgame* placement, which
0.3s blitz under-samples — could be positive at the long TC the analysis board
actually uses. A targeted long-TC endgame gate could revisit it; not worth it now.

**Threat under-weighting follow-up.** REJECTED (neutral), reverted. The outcome
Texel tuner had driven threat.pawn (0.10→~0.15) and threat.initiative (0.25→~0.40)
into their upper bounds — suggestive that the (proven high-value) threat terms
were under-weighted. Tested directly: bump threat.pawn→0.15, threat.initiative→0.35,
gate vs the confirmed 0.10/0.25 baseline (UHO, 0.3s, single-thread):
- batch A (120g): 56% (+48 =38 −34), +41 Elo (95% −21..+105) — promising.
- batch B (120g, independent openings): 48% (+39 =37 −44), −14 Elo.
- pooled (240g): 51.9% (+87 =75 −78), +13 Elo (95% −23..+50). NEUTRAL.
Batch A was winner's-curse again. The confirmed 0.10/0.25 weights are correct;
the outcome-tuner's upper-bound pull does NOT translate to match Elo (same lesson
as the s23 full retune — outcome-loss optimum ≠ match-Elo optimum). Thread closed.

**Two neutral eval experiments in a row (tapered PST, threat bump)** are strong
evidence the eval is near its tuning ceiling at 0.3s. Small weight/table tweaks
sit at the noise floor. Higher-value directions from here: (a) multiplicative
eval terms via marginal-delta attribution (William's idea) — a factor `f` on
subtotal `P` shows contribution `(f-1)·P`, faithful and interpretable, unlocks
non-linear knowledge a sum can't express (OCB drawishness, king-safety×material);
(b) long-TC scaling — all tuning is at 0.3s but the analysis board runs long;
if we convert time to strength worse than the opponents, that is the real
long-TC gap, and it points at search, not eval.

**Long-TC scaling ladder (B).** Added `--opp-movetime` to the match harness and
ran a self-play time-odds ladder: our engine at a fixed 0.3s anchor vs the same
engine at 2x/4x/8x time (single-thread, UHO). The longer side's score = our Elo
gain from that much extra thinking time:
- 0.3s vs 0.6s (2x), 80g: anchor 34% → long side **+112 Elo**
- 0.3s vs 1.2s (4x), 80g: anchor 19% → long side **+248 Elo**
- 0.3s vs 2.4s (8x), 60g: anchor 13% → long side **+325 Elo**
Per-doubling: +112, +136, +77. FINDING: **we scale with time well — no plateau.**
Normal diminishing returns, but +77 Elo at the 1.2→2.4 doubling is healthy
(strong engines ~+60-70/doubling). So extra thinking time genuinely strengthens
us; the analysis board's long thinks are well spent. The losses to a 2820 bot at
long TC are therefore the genuine ~120-Elo strength gap (we're ~2650), NOT a
time-conversion failure. Caveats: single-thread (SMP×long-TC untested); self-
relative (external long-TC Elo needs a vs-SF-at-long-TC calibration, which is
confounded by SF's own scaling). The hypothesis that search under-uses long TC
is NOT supported.

**Extended scaling rung (2.4s vs 4.8s) — INCONCLUSIVE + two findings.** The 16x
rung crashed at game 27/40 (python-chess timed out waiting for a move) and its
partial result (2.4s side 28% → implied +166/doubling) is anomalous and not
trusted. Investigated:
- *Intermittent long-TC crash.* Could NOT reproduce in isolation: the C core and
  the UCI engine both respect the time budget and return promptly across many
  4.8s calls; deep fixed-depth searches (to depth 30) don't crash. Likely a rare
  hang or a harness/many-spawn issue over a ~2h run. NEEDS a longer repro run;
  note the analysis board uses /api/think (repeated bounded calls), not one long
  `go`, so it may not hit this. FLAGGED, not fixed.
- *PV truncation at long TC (real, display-only).* The expected line is extracted
  by walking the TT (`c_pv`); TT_BITS=22 → 4M entries, so at 17-60M nodes (long
  TC) deep PV entries — sometimes even the root — are overwritten, giving a SHORT
  or EMPTY displayed PV. The MOVE and SCORE are always correct (search works); only
  the analysis board's shown line degrades. Confirmed: same middlegame at 1/2/4/8s
  gave pvlen 11/9/12/4, and 0 at 30s. FIXED (William approved): a triangular PV
  table maintained in the search — pv[ply] recorded on each alpha-raise at a PV
  node, root line published per completed iteration, read out via c_get_pv instead
  of walking the TT. WRITE-ONLY side data: verified byte-identical node counts vs
  baseline on 6 positions (search tree unchanged) — no strength gate needed. PVs
  are now full length (12 at depth 12, 15 at depth 15) where they were 4/empty.
  eval 0.000000, perft PASS, 50 fast tests green.

**Multiplicative eval modifiers + OCB drawishness (A).** ACCEPTED, kept as a
feature. Implements William's idea: eval is now `sum(concepts)` THEN a chain of
multiplicative modifiers, each shown in the breakdown as its marginal delta
`(factor-1)*running` — so the displayed items still sum to the total and the
explanation stays faithful. First modifier: opposite-colored-bishop drawishness
(pure OCB ending — one bishop each, opposite colors, no other pieces — scales the
eval by ocb.draw_scale=0.6, since those endings are famously drawish). Faithful:
C==Python 0.000000 over 6204 pos incl. pure-OCB positions; new TestModifiers +
all 47 fast tests green; symmetry holds through the modifier. Gate vs pre-OCB
(120g UHO, 0.3s): 52% (+38 =50 -32), +17 Elo (95% -45..+81) — no regression.
Kept NOT for Elo (pure OCB is rare at 0.3s so the match effect is ~noise) but
because it makes the eval correct where it fires and is the interpretability
capability requested; it also unlocks future non-linear terms (king-safety x
material, etc.) a pure sum can't express. ocb.draw_scale is tunable.

**New eval concept classes (William: "try for a new eval concept class").**
Two attempts, both faithful (C==Python 0.000000), gated single-thread at 0.3s vs
the OCB+PV baseline:
- *King danger (safe checks)* — REJECTED. Count undefended squares from which the
  enemy could check our king (the top king-safety feature in strong engines).
  At weight 10: 44%, **-44 Elo** (a regression). At weight 3: 52%, +12 (neutral).
  Lowering the weight turned the regression into a wash, not a gain — the signal
  is largely REDUNDANT with the existing king_attack term (both score king
  pressure), so adding it only distorts. Reverted.
- *Backward pawns* — **ACCEPTED (+55 Elo confirmed).** A pawn whose adjacent-file
  neighbours have all advanced past it and whose stop square an enemy pawn covers
  is a chronic weakness (x2 on a half-open file) that doubled/isolated don't
  capture. Gate: batch A 60% (+56 =32 -32, +70), batch B (independent openings)
  56% (+47 =40 -33, +41), **pooled 240g 57.9% (+103 =72 -65), +55 Elo, 95% CI
  [+19,+93]** — CI clears zero, held across both batches (NOT winner's curse).
  Why this won where 3 eval experiments this session didn't: it is ORTHOGONAL to
  every existing term (no redundancy), a concrete structural fact nothing else
  measured. pawn.backward=6 (x2 half-open), tunable. New TestBackwardPawns + all
  54 fast tests green.
- *Connected pawns* — **ACCEPTED (+29 Elo, three consistent batches).** After
  backward pawns won, the pawn-structure eval was clearly the untapped seam, so:
  a phalanx (adjacent-file friend on the same rank) or supported pawn (friend one
  rank behind), bonus x(rank-3) so only advanced duos score (the starting chain
  earns nothing). Gated on TOP of backward (baseline = OCB+PV+backward): batch A
  55% (+38), B 53% (+23), C 54% (+26) -- **pooled 360g 54.2% (+138 =114 -108),
  +29 Elo, 95% CI [-1, +59]**. The CI grazes zero, but all three independent
  batches landed positive (~+29 each, no collapse) -- the signature of a real
  effect, not winner's curse. Orthogonal to every term (rewards structure, not
  advancement, which PST already has). pawn.connected=4, tunable. New
  TestConnectedPawns + 57 fast tests green. Session eval total ~+84 (backward+
  connected, gated incrementally).

**Re-calibration — the +84 self-play Elo did NOT transfer externally (important).**
Re-ran the Stockfish calibration on the full new engine (OCB+PV+backward+connected),
single-thread, 0.3s, 40 games/anchor: SF-2600 56%, SF-2700 45%, SF-2800 31% ->
crossover ~2655. Before this session's eval work it was ~2650, and vs the SAME
SF-2700 anchor we scored 45% BOTH times. So the ~+84 "Elo" from backward+connected
was SELF-PLAY-relative and did not move external strength vs Stockfish. Why: those
terms let us punish our own prior versions' blind spots (huge in self-play), but
Stockfish never had those blind spots, so correcting them gains ~nothing against
it. The concepts are still real, faithful eval improvements (more accurate, better
interpretability, no external REGRESSION), and kept -- but the honest external
number is ~2655, not ~2735. LESSON (again, now measured directly): self-play Elo
overstates external gain for eval changes; the only trustworthy strength number is
vs an external opponent. Closing the real gap to a 2820 bot needs a bigger lever
than classical eval tuning -- the eval is at its external ceiling for this engine.

**Search push (William: "let's push on search, it is critical this tool is as
strong as possible"). Reverse futility pruning -- ACCEPTED (+114 Elo).** The
search already had TT/null-move/futility/LMR/PVS/check-ext/improving; LMR/IID/
conthist were already tried and rejected. The conspicuous gap: reverse futility
(static null-move) pruning. At shallow depth in a non-PV node not in check, if
`eval_stm - RFP_MARGIN*depth >= beta`, return the eval (assume fail-high). C-
search-only (eval untouched -> C==Python still 0.000000). RFP_DEPTH=6,
RFP_MARGIN=90. Effect: **+1.5 ply deeper in the same 1.5s (depth 13.0 vs 11.5)**,
tactics 24/24 (100%, no blunder). Gate vs baseline (single-thread, 0.3s, UHO):
batch A 69% (+62 =42 -16, +140), batch B 63% (+53 =44 -23, +89), **pooled 240g
65.8% (+115 =86 -39), +114 Elo, 95% CI [+79, +151]**. Unlike the eval gains, this
is deeper search -- it finds better moves vs ANY opponent, so it should transfer
externally (to be re-confirmed by calibration). Biggest single gain in the log.
Next: LMP, razoring, singular extensions; then re-calibrate.

**Late move pruning (LMP) -- ACCEPTED (+30, borderline).** In a non-PV node at
depth<=5, skip late quiet moves outright once tried count `i >= (3+depth*depth)>>
(improving?0:1)` (fewer when not improving); never skip a checking move. C-search
only. Depth 13.5 vs 13.0 (RFP-only), tactics 24/24. Gate vs RFP-only baseline:
57% / 50% / 55% over three batches -> pooled 360g 54.3% (+138 =115 -107), +30 Elo,
95% CI [+0, +60]. Borderline (like connected pawns) but two of three batches
clearly positive, no collapse, and it's a depth-adding search change (should
transfer). Kept. LMP_DEPTH=5, tunable.

**Re-calibration (RFP+LMP) -- THE SEARCH GAINS TRANSFERRED (unlike eval).**
Same Stockfish anchors, 40 games, 0.3s, single-thread. Eval-only engine -> now:
vs SF-2600 56%->62%, vs SF-2700 45%->**58%** (~+88 Elo vs the SAME anchor),
vs SF-2800 31%->36%, vs SF-2900 28% (new). Crossover ~2655 -> **~2736, roughly
+80 external Elo** from RFP+LMP. Decisive validation: search improvements transfer
(~55% of the +144 self-play) because deeper search finds better moves vs ANY
opponent -- whereas the +84 eval self-play transferred ~0 (opponent-specific
blind-spot fixes). CONCLUSION: keep pushing search. (40g/anchor is noisy but the
shift is consistent across all four anchors.) Next: singular extensions, razoring.

**Singular extensions -- ACCEPTED (+29, borderline).** The trickiest search
feature: at a deep node (depth>=8) with a trusted TT fail-high move, a reduced-
depth verification search of every OTHER move (excluded-move mechanism, window at
ttScore-2*depth); if they all fail below it, the TT move is forced -> extend it a
ply. C-search only; excluded-move slot per ply, TT-cutoff/store suppressed during
verification, path popped so the verification doesn't see itself as a repetition,
and the only-excluded-move corner case returns fail-low (forced-move extend).
Verified: eval 0.000000, perft, tactics 24/24 (no blunder/crash -- the key
correctness signal for this feature), no node explosion, 57 tests. Gate vs
RFP+LMP baseline: batch A 55% (+32), batch B 54% (+26), pooled 240g 54.2%
(+91 =78 -71), +29 Elo, 95% CI [-7, +66]. Borderline but two consistent positive
batches; a standard technique that pays off MORE at long TC than the 0.3s gate
shows. Kept. Search stack now RFP+LMP+SE. Next: razoring, bigger TT, tuning.

**More search: razoring REJECTED (neutral, overlaps futility/qsearch); bigger TT
22->24 REJECTED (0.3s neutral/-12, cache locality); RFP margin swept -> 90 is
optimal (70 -> -53, 110 -> +12 noise). RFP/LMP/SE margins well-tuned.**

**Long-TC validation of the full search stack -- CONFIRMED BIG AT THE USER'S
REGIME.** Full stack (RFP+LMP+SE) vs the eval-only engine at 1.5s/move, 50 games,
UHO, single-thread: **71% (+28 =15 -7), +156 Elo, 95% CI [+59, +283]**. The stack
holds (does not shrink) at long TC -- singular extensions, which pays off at depth,
is included. Combined with the +80 external (RFP+LMP at 0.3s), the search push is
the real strength lever: the engine is now meaningfully stronger at the long/
indefinite TC the analysis board actually uses. Search >> eval for this engine.

**Internal iterative reduction (IIR) -- ACCEPTED (+48 Elo, confirmed).** With no
TT move to guide ordering (`!ttm && depth>=4`), reduce depth by one ply instead
of searching full-depth blind -- the shallower search fills the TT so the
re-search is well-ordered. (IID's cheaper modern replacement; plain IID was
tried and rejected -- IIR is the reduction variant, and it works.) One line,
C-search only (eval 0.000000, tactics 24/24). Gate vs RFP+LMP+SE baseline: batch
A 58% (+53), batch B 56% (+44), pooled 240g 56.9% (+96 =81 -63), +48 Elo, 95% CI
[+13, +85] -- both batches strongly positive, CI clears zero. Second-biggest
search gain after RFP. Also rejected this round: improving-aware RFP (+14 noise).
Stack now RFP+LMP+SE+IIR. Next: probcut, correction history.

**Null-move R tier -- ACCEPTED (+29, borderline).** Deeper null reduction as depth
grows: r = depth>=12?5:(depth>=6?4:3) (was depth>=6?4:3). Gate: batch A 53% (+23),
batch B 55% (+35), pooled 240g 54.2%, +29 Elo, CI [-6,+64] -- two consistent
positive batches. Kept. Stack now RFP+LMP+SE+IIR+null-R. (A full-stack re-
validation vs the pre-search engine is queued to confirm the borderline pieces
hold in aggregate.)

**Full-stack external re-calibration (RFP+LMP+SE+IIR+null-R).** vs SF-2700 44%,
2800 32%, 2900 29%, 3000 28% (40g/anchor). NOISY: at 40g the CI is ~+-100 Elo, so
this (crossover ~2700) is statistically indistinguishable from the RFP+LMP
calibration (~2736). HONEST READ: the search push confirmed ~+80 external (RFP+LMP,
clean 45%->58% before/after vs SF-2700); the SE/IIR/null-R external INCREMENT is
within the 40g noise and NOT separately claimed. But they are the same CLASS of
change (better/deeper search, opponent-agnostic) as RFP+LMP which did transfer,
so the transfer argument is mechanistic, unlike the eval concepts (which fixed
our own blind spots). Engine now ~2700-2740 external, up from ~2655.

**ProbCut -- ACCEPTED (+50 Elo, confirmed).** A good capture (SEE>=0) that, at a
raised beta (beta+180) via a quick qsearch then a depth-4 search, still fails high
-> the node almost certainly fails high, cut. Non-PV, not in check, depth>=5.
C-search only (eval 0.000000, perft, tactics 24/24, prunes nodes 1.67M vs 2.19M).
Gate vs full-stack baseline: batch A 55% (+35), batch B 60% (+64), pooled 240g
57.1% (+93 =88 -59), +50 Elo, 95% CI [+15, +85] -- both positive, CI clears zero.
Third big win (RFP +114, IIR +48, probcut +50). MISSING techniques keep winning;
tuning tweaks stay marginal. Stack: RFP+LMP+SE+IIR+null-R+probcut.

**Search ceiling reached: six consecutive REJECTED techniques.** After the three big
wins, everything else came back neutral and was reverted: razoring (50%, overlaps
futility/qsearch), TT 22->24 bits (48% at 0.3s, cache locality), improving-aware RFP
margin (+14, noise), RFP margin sweep (70 -> -53, 110 -> +12; 90 is optimal),
multi-cut on the singular verification (49%, fires too rarely), correction history
(49%; our concept-sum eval's error is evidently NOT pawn-structure-correlated, so the
correction adds noise not signal -- a genuinely interesting negative result for a
non-NN eval), and SEE-pruning of losing captures (batch A 58%/+53 collapsed to batch B
48%/-21, pooled 52.5%/+17 -- textbook winner's curse, caught by the confirmation rule).

**CAPSTONE: total search gain at the analysis board's real regime.** Full search stack
(RFP+LMP+SE+IIR+null-R+probcut) vs the pre-search eval-only engine, 1.5s/move, 50 games,
UHO, single-thread: **76% (+30 =16 -4), +200 Elo, 95% CI [+101, +343]**. The search push
is worth ~+200 Elo at long TC. External calibration puts the engine at ~2700-2740
single-threaded (up from ~2655), i.e. the search work roughly halved the gap to a
2820-class opponent, where the eval work had moved external strength ~0.

**Standing lesson (now proven twice):** self-play gates measure "did we fix our own
lineage's blind spots"; only search improvements reliably converted to external Elo.
Eval changes must in future be validated against an EXTERNAL opponent, not self-play.

---

## 2026-07-23 — Session 21: analysis board (product) + adaptive-time deprioritized

**Direction change (from William):** for this tool — primarily a *learning*
aid people run at long/indefinite think times — adaptive time management is
low-value (it only pays under strict clocks nobody analyzes with). Deprioritized
as a strength lever. The strength focus going forward is improvements **more
general than time management** (search/eval that help at any TC). The
adaptive-vs-naive game-clock gate (T=1, 10s+0.1) finished for the record:
**+24 =18 −18 (55%), +35 Elo (95% −53..+128)** over 60 games — mildly positive
where it's designed to help (a strict clock), but the CI spans zero and it's inert
at fixed/indefinite time, so it stays in the tree (harmless in the analysis board)
and is not pursued further.

**Product (the session's real deliverable): an analysis board, now the default
view of the web app.** Set up any position (free moves for either side, or paste
a FEN) and the engine thinks indefinitely, depth climbing live with the eval,
principal variation, and recommendation arrows (best move + runner-up) refining
in place. Options: opening-book toggle, board flip, reset, undo, arrows on/off,
insights overlay. Play-vs-engine (the old coach) moves under a header toggle.

- **Backend:** new `/api/think` endpoint. Live-deepening with **no streaming
  machinery** — the client calls repeatedly with an increasing `max_depth`; the
  C core's TT persists across calls, so re-searching shallow depths is near-free
  and each call effectively adds one ply. Per-call `movetime` is only a safety
  ceiling. Returns White-perspective score, PV (SAN), best + runner-up root moves
  (for the two arrows), node count, and a forced-mate flag. Book-aware.
- **Interpretability intact:** the arrows/score come from the same C search; the
  concept breakdown beside the board is the same faithful eval. No engine change,
  so single-threaded determinism and the C==Python invariant are untouched.

**Verdict:** ACCEPTED (product feature; no engine/eval change, no strength
impact; `/api/think` verified across depth ladder, book, and mate-in-1;
frontend passes `node --check`).

**Strength lever #1 — log-based LMR reduction table (REJECTED, neutral; a
refutation-of-a-refutation worth recording).** Replaced the coarse stepped LMR
(cap red=3) with the standard `0.85 + log(d)·log(m)/2.20` table, same
reduce-conditions. Reaches **+1–2 plies deeper** at fixed time (middlegame 11→9
became 11, i.e. +2). Screens green (perft, eval 0.000000, 47 tests, tactics
24/24). **Match vs the no-LMR base at 0.3s, 60 UHO games: +21 =18 −21 (50%),
−0 Elo (95% −90..+90).** Exactly neutral. The point: **s11 rejected this same
aggressive log-LMR at −29 Elo** — but s11's baseline predated history-malus,
countermove, and SEE ordering. With today's ordering, the same 4–5-ply late-quiet
reductions are no longer *harmful* (the well-ordered late moves really are worse,
so reducing them costs nothing) — but the extra depth they buy exactly offsets the
occasional missed line. So the s11 failure was ordering-dependent, not intrinsic;
fix the ordering and aggressive LMR becomes a wash, not a win. Reverted (a neutral
change doesn't earn its complexity, and "50% ± 90" hides a small negative as easily
as a small positive). Confirms, a second time, that this engine is bottlenecked on
*ordering/eval quality*, not on doing less per node. Next lever chosen accordingly.

**Verdict (lever #1):** REJECTED (strength-neutral; kept as a recorded negative).

**Strength lever #2 — internal iterative deepening (IID) (NOT GATED; inert then
uneconomic).** At a node with no TT move, do a reduced (depth−2) search first to
seed a best move for ordering. Two placements, diagnosed by fixed-depth node
counts (an exact A/B on an idle machine):
- *PV-only* (`beta>alpha+1`): **byte-identical node counts to base** — it never
  fires. With iterative deepening + TT, PV nodes already carry a hash move from
  the previous iteration, so `!ttm` is essentially never true there. A literal
  no-op; not worth gating.
- *All nodes:* now fires, but **+49% nodes on the middlegame** (2.50M→3.71M at
  d12) with the *same* best move. The shallow probes cost more than this engine's
  already-strong history/killer/SEE ordering saves. Node count is a weak proxy
  (it under-sold SEE ordering's +53), but inert-when-safe plus expensive-when-live
  plus unchanged move choice is a consistent picture, not a fluke.

Three search experiments this session (aggressive LMR, PV-IID, broad-IID) all say
the same thing: **the ordering/reduction machinery is already well-tuned — there is
no cheap search headroom left.** Redirecting to evaluation knowledge, which is
where this engine's big *interpretable* gains have always come from (king-race
concept +110, passer structure, SEE eval). Reverted to the clean baseline.

**Verdict (lever #2):** NOT GATED — diagnosed inert/uneconomic; reverted.

**Where the strength actually is — and lever #3, applied to the product.** After
LMR (neutral) and IID (uneconomic), a fresh quiet/positional SF-verified suite
(`research/suites/quiet_v1.epd`, 30 quiet-best-move positions) + `diagnose.py`:
**26/30 solved, 4 scattered misses, no concentrated concept culprit** — the eval
is well-calibrated (it was already Texel-tuned at scale in s16–17; knight outposts
already rejected s17). A flat `sample` profile of the search puts **eval_core at
~34% of self-time**, but it's already single-attack-pass optimized, and lazy/partial
eval is off-limits (would break "search maximizes the displayed concept sum").

So single-thread search is tuned, eval is tuned, and the ROADMAP's stated frontier
is *parallel-search quality*. The highest-value move is therefore not another
single-thread micro-lever but **applying the proven Lazy-SMP win (+187 Elo, s20) to
the analysis board** — which had been running the default T=1 engine. T=1 exists
only for *coach determinism*; an analysis board has no such constraint (occasional
PV nondeterminism while exploring is fine). Now `/api/think` runs at full width
(all cores, capped at 8) and resets to T=1 around the call so the coach/play path
stays byte-reproducible. Measured on a middlegame at 3s: **T=1 depth 12 → T=8 depth
14** (+2 plies, fuller PV) — the analysis board is now materially stronger for the
exact use it was built for. 47 tests green; coach path untouched.

**Verdict (lever #3):** ACCEPTED (product-strength win via committed SMP infra; no
engine change, coach determinism preserved).

**Levers #4–6 — pushing single-thread strength harder ("weaker levers OK, do your
best").** Three more, gated by fixed-depth node counts on a 4-position middlegame
set (idle machine, exact A/B) then matches:
- **#4 continuation history** (graded generalization of the countermove slot,
  keyed [side][prev_to][from][to]; ordering-only, no eval mirror needed).
  REJECTED — **+40% nodes-to-depth**. Every variant (additive, capped below the
  killer tier, tiebreaker-only) made ordering worse, not better. This engine's
  butterfly-history + killers + countermove + SEE ordering is a strong optimum
  that a second history table only adds noise to. Reverted.
- **#5 bigger TT** (TT_BITS 22→24, 96MB→384MB). REJECTED (neutral) — at deep
  analysis time it cut nodes (better hit rate) but reached the **same depth**: the
  384MB table's cache-miss penalty cancels the hit-rate gain. Same verdict as the
  s-earlier bigger-TT-under-SMP rejection, now confirmed at long TC too. Reverted.
- **#6 aspiration windows** (delta=20; the C search searched the root with a FULL
  window every iteration — genuinely missing). **ACCEPTED.** Screens green (perft,
  eval 0.000000, 47 tests, tactics 24/24), −2.1% nodes on middlegames, +2.5% NPS
  at equal avg depth. Match vs base at 0.3s, **two independent 60-game batches:
  A +24=17−19 (54%, +29 Elo), B +25=13−22 (52%, +17 Elo); pooled 120 games
  +49=30−41 = 53.3%, ≈+23 Elo (95% ~ −39..+87).** Both batches independently
  positive with no winner's-curse regression on confirmation (+29→+17, not
  +70→+13), and a mechanistic basis (the node/NPS wins) — so a real, modest gain
  that helps *every* mode and TC. Kept. Honest framing: small (~+20 Elo), CI wide;
  its value is as much a correct foundation as the raw points. delta swept
  (16:+2.4%, 20:−2.1%, 30:+11.6% nodes) → 20 is the local optimum; wider windows
  cost more via expensive high-depth re-searches.

**Lever #7 — root-move ordering by previous-iteration score (REJECTED).** Natural
follow-on to aspiration: keep the root list sorted by each move's last score so the
true best is first and the window holds without a re-search. On 4 middlegames it
looked good (−4.3% nodes vs base, better than aspiration's −2.1%) but the broad
benchmark told the truth — **avg depth 19.50 → 19.33** and middlegame fixed-time
depth 13 → 12. Cause: with PVS only move 1 gets a true score; moves 2..N carry
null-window *upper bounds*, so sorting by them misorders decent-but-scouted moves
to the back. Would need per-move re-search or bound-aware sorting to fix; not worth
it on top of aspiration. Reverted.

**Session-21 strength ledger:** seven levers, one clear product win (SMP-for-analysis),
one modest engine win (aspiration, ~+23 Elo pooled), five honest negatives (LMR
neutral, IID uneconomic, continuation-history worse, bigger-TT neutral, root-order
regresses). The recurring lesson — this engine's ordering/eval are a genuinely
strong local optimum — held all session; aspiration got in only because it attacks
a real structural gap (the un-windowed root) rather than re-tuning something already
tuned. Broad-benchmark avg depth is the reliable arbiter; 4-position node counts
mislead (root-order looked +good there, regressed on the suite).

**Verdict (lever #6 / aspiration):** ACCEPTED (~+23 Elo pooled over 120 games;
principled, faster, all invariants intact).

---

## 2026-07-24 — Session 23: SMP is the play default; SMP-quality frontier probed

**SMP as the play default (ACCEPTED — product/strength).** With single-thread
search and eval both at a hard optimum (see s22), the biggest available lever is
the proven Lazy-SMP gain (+140–190, s20). The engine now plays full-width by
default everywhere it actually plays — UCI (external GUIs/real games), the web
play-vs-engine opponent, and the analysis board — via `core.play_threads()`
(honor CC_THREADS, else all cores ≤8). The coach's move-verdict searches stay
single-threaded for reproducibility; `research.match` exports CC_THREADS=1 so
version-vs-version gates stay clean single-thread. Confirmed the gain holds on the
current engine: benchmark avg depth **20.5 (T=8) vs 19.3 (T=1), +1.2 plies**. Eval
and its explanations unchanged. Committed.

**SMP helper LMR-diversity (REJECTED, neutral).** With SMP now the default, its
*quality* is the live frontier. Tried: odd-id helper threads reduce one extra ply
(`SS.lmr_bias`), so they explore different tree shapes and fill the shared TT with
varied entries; main thread and the T=1 path provably unchanged. Gated clean at
**T=4 vs T=4** (8 threads on 8 cores — no contention): batch A +19=24−17 (52%),
confirmation +... (47%); **pooled ~49.6% over 116 games** — neutral washout, same
shape as history-LMR. Reverted. SMP-quality tuning is both noisy to gate (SMP
nondeterminism) and, on the evidence so far, not a cheap win.

**Frontier status:** single-thread search, eval, and now SMP-quality-diversity all
explored. Banked this session-pair: ~+100 Elo single-thread (aspiration +23, threats
+47, initiative +32) + SMP as the play default. The last three levers (pins,
history-LMR, SMP-diversity) were all neutral — the engine is at a deep optimum.

**Endgame concepts + full Texel retune (ACCEPTED, +58 Elo batch).** Two things at
once, both requested:

*Endgame concepts (additive, so they fit the concept-sum invariant — note that
drawishness ideas like opposite-bishop scaling are inherently MULTIPLICATIVE and
would break "eval = sum of named concepts", so they were deliberately not taken):*
**rook behind a passed pawn** (Tarrasch) — a friendly rook behind the passer
supports its advance (bonus), an enemy rook behind it attacks/stops it (penalty).
Both byte-identical C↔Python (0.000000).

*Full Texel retune on FRESH data.* Regenerated the dataset from the now-stronger
engine: **29,769 samples / 1500 self-play games**, balanced outcomes
(10234/9228/10307) from Stockfish-screened balanced starts. Crucially this used
`research.texel` (fits **game outcomes**) — not `research.tune`/`evalloss`
(eval-MSE vs Stockfish), the target the LOG had already flagged as anti-correlated.
Extended TUNABLE to cover the s22 threat terms and the new endgame terms, which had
never been tuned. **Loss 0.088139 → 0.087638 (0.57%); 21 weights changed.**

The headline finding: **`threat.pawn` 0.10→0.15 and `threat.initiative` 0.25→0.40
both hit their UPPER bounds** — the tuner wanted them higher still, i.e. the threat
concept (s22's big win) was materially under-weighted. This is the exact OPPOSITE
of what the earlier eval-MSE tune concluded (it wanted them lower, and gated
neutral), a clean demonstration that the outcome target is right and the MSE target
misleads. Endgame terms tuned too: defensive rook-behind (10→12) beats supporting
(12→9.6). PSTs, king safety (shield/open-file up), mobility and activity all shifted.

**Gate (combined, vs HEAD, 0.3s): batch A +25 =20 −15 (58%, +58 Elo) — but the
confirmation came in +17 =17 −26 (42%, −53). Pooled 120 games: +42 =37 −41 = 50.4%,
≈+3 Elo (95% −60..+66) — NEUTRAL.** The most violent winner's-curse swing of the
run (58%→42%), and the honest verdict is that the full retune did NOT improve
strength. Confirms, a third time this session-pair, that the tuning flywheel has
converged: even with the correct outcome target (not eval-MSE), a broad weight
re-fit doesn't beat the already-tuned weights at play. My first commit message
overclaimed +58 — corrected here.

**Resolution (disciplined):** reverted the broad weight changes (the confirmation
was negative, so keeping ~19 unconfirmed weight edits is a real risk). **Kept the
endgame rook-behind-passer concepts** — they're the requested, interpretable,
byte-identical part, and low-frequency-neutral is expected for them, not a failure;
they earn their place on coach value (the breakdown now explains "rook behind your
passer"), gated separately for no-regression. **The one real finding is preserved
as a follow-up:** the tuner drove `threat.pawn`→0.15 and `threat.initiative`→0.40
INTO their upper bounds — strong evidence those s22 terms are under-weighted — worth
a FOCUSED gate (just those two, not the whole re-fit) another session.

**Verdict:** retune REJECTED (strength-neutral, flywheel converged); endgame
rook-behind concepts KEPT (interpretable, faithful, no-regression).

---

## 2026-07-23 — Session 22: threat eval concept (+83 Elo) — eval knowledge, not search

After s21 showed single-thread *search* is a strong local optimum (aspiration the
lone win), the productive frontier is **eval knowledge** — a new interpretable
concept, the historical big-gain pattern (king-race +110). The `diagnose.py`
"eval is calibrated" reading only means the top move rarely flips; it doesn't mean
every positional feature is modeled.

**Expanded the Threats concept (ACCEPTED, +83 Elo).** The old concept scored only
*hanging* (attacked + undefended) pieces at 5.6% of value. Added the far larger
signal of pieces pressured by a **lower-value attacker** — a pawn hitting a
minor/rook/queen, a minor hitting a rook/queen, a rook hitting a queen — since
those win material (SEE) or force a concession even when defended. Three new terms
(threat.pawn 0.10, threat.minor 0.06, threat.rook 0.04 as fractions of the
threatened piece's value), added per piece in a fixed order so the C eval mirrors
the Python sum **byte-for-byte** (eval_check max |C−Python| = 0.000000, faithfulness
tests green, perft clean, tactics 24/24). Fully interpretable: the coach now says
"Black knight on d5 attacked by a pawn."

**Gate (isolated: aspiration+new-threats vs an aspiration-only worktree, 0.3s):
+23 =28 −9 (62%), +83 Elo (95% −4..+181)** over 60 games — 2.6:1 win ratio,
consistently positive the entire run (55→57.5→58→57.5→59→62, no negative window).
High draw rate (28), as expected for an eval nuance.

**Confirmation (winner's curse trimmed it, as expected).** A clean second batch —
run worktree-vs-worktree (threats-wt vs aspiration-wt) so it's independent of the
main build — came in at **+21 =20 −19 (52%, +12 Elo)**. (A first confirmation
attempt was discarded: I'd rebuilt main for the next concept *while it ran*, mixing
binaries — a real methodology bug, caught and re-run clean.) **Pooled over both
clean batches, 120 games: +44 =48 −28 = 56.7%, ≈+47 Elo (95% ~ −15..+112).** So
the honest figure is **~+47 Elo**, not the +83 of batch A alone — both batches
positive, grounded in chess theory, clearly worth keeping, but a textbook case of
why single-batch Elo is optimistic. Kept.

**Verdict:** ACCEPTED (new interpretable eval concept, ~+47 Elo pooled over 120
games; C==Python invariant preserved). Lesson re-underscored: never rebuild the
engine while a gate against it is running.

**Pawn-storm king-safety concept (REJECTED, −83 Elo).** Added a term penalizing a
king whose files carry advancing enemy pawns (integer storm sum, byte-identity
trivial). Faithful (C==Python 0.000000, perft/tests green) but gated **+17 =12 −31
(38%), −83 Elo** vs the threats baseline — a clear, consistent negative. It
over-rewards pawn-pushing at the enemy king and mis-weights king danger; king
safety is delicate and this was an intuition guess, not diagnosis-driven (the quiet
suite hadn't flagged king safety). Reverted. Takeaway: on this engine, *piece-
pressure* concepts land (threats +47) but *king-safety* re-tuning backfires — go
where the diagnosis points, not where intuition does.

**Threat-by-pawn-push concept (REJECTED, −64 Elo).** A pawn that can *safely* push
one square (empty, not into an enemy pawn's control) and from there attack an
enemy minor/rook/queen (weight 0.05). Faithful (C==Python 0.000000, the trickiest
mirror yet — bitboard shifts — passed; perft/tests green). Gated **+12 =25 −23
(41%), −64 Elo** vs the threats baseline. Second pawn-advance concept to fail after
storm, and it confirms the pattern hard: **concepts that reward pawn *advances*
(storm, push) lose; concepts that value *existing* piece pressure (threats +47)
win.** The engine already handles pawn breaks via search; nudging the eval to want
them just distorts move choice. Reverted. Next eval work will avoid pawn-advance
signals entirely.

**Bad-bishop concept (REJECTED, −70 Elo).** Penalty per own pawn on a bishop's own
square color. Faithful (0.000000). Gated **+18 =12 −30 (40%)** — too coarse: it
penalizes *every* bishop (~3–4 own pawns sit on its color in the opening) instead
of isolating genuinely bad ones, so it just adds noise. Reverted. Third coarse
new-concept reject; the eval is well-tuned, and blunt new terms distort it.

**Texel re-tune of the threat weights (NEUTRAL, kept guesses).** `research.tune
threat.` lowered train loss (0.02158→0.02148) and shifted the weights (pawn 0.10→
0.082, hanging 0.056→0.030 down; minor 0.06→0.097, rook 0.04→0.076 up). But gated
**+19 =23 −18 (51%, +6 Elo)** vs the guessed weights — the classic loss≠Elo
disconnect (the tuning flywheel converged sessions ago). Kept the committed guesses.

**Threats-initiative — refine the *proven* concept (ACCEPTED, +64 Elo batch).**
Key shift in approach: stop guessing coarse new concepts (0/3), instead sharpen the
one that works. Real chess idea the eval ignored — a threat the **side to move** can
execute *now* is worth more than the opponent's threat, which can be parried. Scaled
the mover's four threat terms by 1+`threat.initiative` (0.25). Faithful even though
now side-to-move-dependent (C==Python 0.000000; eval_check passes `side`). Gated vs
the threats baseline: **+24 =23 −13 (59%), +64 Elo (95% −23..+161)** — consistent
across the run (60/60/59), 1.85:1 wins. Committed; confirmation batch + initiative-
weight tune queued (expect winner's curse to trim +64, as it did threats' +83→+47).

**Confirmation:** clean second batch +19 =22 −19 (50%) — a weak final 20 games
(5/20) after a 62.5% first 40, i.e. high 60-game variance. **Pooled 120 games:
+43 =45 −32 = 54.6%, ≈+32 Elo (95% −30..+96).** Honest figure **~+32 Elo**, not the
+64 of batch A — same winner's-curse trim as threats (+83→+47). Kept.

**Verdict:** ACCEPTED (initiative refinement of the threats concept; ~+32 Elo pooled
over 120 games; C==Python preserved). Method lesson confirmed twice now: **refine
the proven concept, don't guess new ones** — threats +47 and its initiative
refinement +32 both landed; every coarse new concept (storm/push/bad-bishop) lost.

**Pins concept (REJECTED, neutral −12 Elo).** New concept penalizing own minors/
rooks/queens pinned to their king (both colors, symmetric). Notable engineering:
a from-scratch pin detector in C (between-table + slider rays) that reproduced
python-chess `is_pinned` **byte-for-byte on all 500 eval_check positions** — the
hardest mirror of the session, and it passed clean. But gated **+22 =14 −24 (48%),
−12 Elo** vs the initiative baseline. The refined lesson: a winning eval concept
must be concrete **and beyond the search horizon**. Threats/initiative qualify
(positional pressure the 0.3s search doesn't fully resolve); pins don't — the search
already handles pin *tactics* directly, so the eval term is redundant. Reverted.

**Session-22 tally (single-thread, all pooled/confirmed):** threats +47, threats-
initiative +32 ≈ **+79 Elo of eval knowledge**, on top of s21's aspiration +23 — the
engine is materially stronger while staying fully interpretable (every new term is a
named, explained concept; C==Python 0.000000 throughout). Six eval attempts: 2 wins
(threats, initiative), 4 losses (storm/push/bad-bishop coarse-or-search-handled;
pins search-handled; weight-tune loss≠Elo). **Winning eval concept = concrete +
beyond-horizon + not-already-in-search.** That trio is now well-covered — the eval
is mature; further eval headroom is scarce.

---

## 2026-07-20 — Session 20: Lazy SMP breaks the plateau (+140–187 Elo)

The s19 diagnosis said the gap to Stockfish was **search depth, not eval** —
so the lever is nodes/second, and the biggest untapped source is the seven
idle cores the sequential match harness leaves free while one side thinks.
**Lazy SMP** (the big change): N threads search the same root sharing one
transposition table; each keeps thread-local search state (killers, history,
path, nodes); helper threads stagger their iterative-deepening start depth so
they fill the shared TT with entries the main thread reuses to reach +1 ply
in the same wall-clock budget. TT/eval-hash writes race — tolerated by Lazy
SMP (the 64-bit key check rejects torn entries; rare torn scores
self-correct).

**Results (vs the single-threaded engine, 60 UHO games at 0.3s):**
- T=4: **+34 =15 −11 (69%), +140 Elo** (95% +52..+250)
- T=8: **+34 =11 −8 (75%), +187 Elo** (95% +91..+319, SPRT H1 at 53 games)

Two independent gates, both decisive — the biggest gain since the compiled C
core (+382), and it lands exactly where the diagnosis pointed. The plateau
was real *for single-threaded search*; it was not the ceiling of the
architecture.

**TC scaling (validation):** T=8 vs single-thread at **1.0s/move** (the
coach's real operating point): **+13 =21 −6 (59%), +61 Elo**. Net positive at
the product TC, but smaller than +187 at 0.3s — expected, since each extra
ply is worth less at deeper base search, so a fixed parallel speedup converts
to fewer Elo at longer TC. Honest range: ~+60 (1s) to ~+150–190 (0.3s).
Follow-up: depth-preferred TT replacement under 8-thread write pressure gated
neutral (49%) — the 4M-entry table is oversized for ~2M nodes/move at any
thread count.

**Design:** default is **1 thread = byte-identical** (cttd node count
unchanged), so the coach GUI stays deterministic and converts basic mates
reliably; N is opt-in via `CC_THREADS`. Known tradeoff, and why the default
is 1: T>1 is nondeterministic and can miss the precise KBN 50-move mate
(the multi-threaded search occasionally picks a non-converging move). For the
interpretable coach, determinism wins; for competitive strength, threads win.

---

## 2026-07-20 — Session 19: the plateau, established four ways

Six experiments, zero accepts — but the session's product is a rigorously
triangulated conclusion: **the engine is at the genuine ceiling of this
architecture (interpretable concept-sum eval + alpha-beta) at this hardware
and time control.** Four independent lines of evidence:

1. **Diverse gated experiments all neutral/negative.** Singular extensions
   (49% blitz; a 40-game 1s batch showed +70 but the confirmation batch
   regressed it to +13/52% over 80 — a caught false positive), flywheel
   re-spin iteration 4 (+12/52%, declined as noise vs the winner's curse),
   internal iterative reduction (50%, −15% nodes but no strength — its
   ordering benefit needs depth 20+), pawn storm (46%, unsound pushes the
   search already handles).

2. **The tuning flywheel converged.** Spin gains +53 → +23 → +12 → noise;
   iteration 4 declined.

3. **Move-choice diagnosis (research/diagnose.py, new).** On 50 realistic
   Texel positions vs Stockfish-16: **the engine's move agrees with SF on
   39/50 (78%).** Of 11 disagreements, material (+420cp, 2 pos, huge SF
   gaps) dominates — these are *tactical/search-depth* misses, not eval
   gaps. The leading *eval* culprit, threats, is only +60cp over 4 positions
   (noise-level, and already Texel-tuned). **The evaluation is well-
   calibrated; the gap to Stockfish is search depth, not missing concepts.**

4. **Memory isn't the bottleneck.** Bumping TT 22→23 bits and the eval hash
   20→23 bits left cttd node counts and time flat — no collision pressure at
   ~2M nodes/move, so depth can't be bought from bigger tables.

**Implication.** More Elo now requires leaving the single-hypothesis loop:
faster hardware / longer TC (not code), a fundamentally faster interpretable
eval (bounded below by the faithfulness tax, s16), or an opaque eval
(NNUE — out of scope by the interpretability mission). The autoresearch loop
for *strength* has converged. Remaining high-value work is product/coaching,
content (the research record is strong), and the reusable diagnosis harness
for any future concept ideas. New infra kept this session: `diagnose.py`
(concept-attribution) and `make_suite --quiet-only`.

---

## 2026-07-18 — Session 18: deep-TC validation + the backlog thins

**Deep-TC robustness check: +223 Elo at 1s/move (78%, +19 =9 −2)** vs the
s10 starting point, over UHO starts. The entire run's gains — every one
gated at 0.3s/move — hold at the coach's real time control. Not
blitz-overfit; the +336 blitz chain compresses to +223 at depth, which is
normal TC scaling.

**exp1 — mop-up extension of mating drive (ACCEPTED, 54%, +29).** Pawnless
defenders dominated by ≥ a rook get the corner-drive gradient at half
strength. Concrete-goal gradients: 4-for-5. Chain crossed 2800.

**exp2 — knight-outpost gradient (REJECTED, 48%, −17).** First real match
trial (s2 only screened it on the discredited eval-loss metric) confirms the
discard. Firm pattern: static positional features (space, outposts) lose —
12-ply search already prices placement via mobility+PST; concrete-goal
distance gradients win.

**exp3 — 50-move rule v2 (REJECTED, 46%, −29 — closed at blitz TC).** The
diagnosed TT pollution was engineered out (store guard at hm>80) and it
still lost: the guard discards useful long-endgame entries, and hm≥100
rarely bites at 0.3s/move. Two mechanisms, two failures.

**Anchors and the winner's curse (methodology close-out).** s18 ladder:
2670 (2523–2809); s17+s18 pooled: 2639 (2533–2739). The chain (~2810) now
sits persistently ~150 above the anchors, and the cause is textbook
**winner's curse**: gates accept at ≥50%, so accepted deltas carry upward
noise-bias, and summing them overstates cumulative gain. Going forward the
pooled anchor (~2650–2680) is the headline number and the chain is labeled
an optimistic upper bound. (The deep-TC head-to-head, +223 over the whole
run in one 30-game measurement, sits between the two — consistent with
both.)

**Session 18 net: +29, and an honest capacity note.** The last ten gates
produced +29 net — the standard-ideas backlog is harvested. Remaining
marginal value: periodic pooled anchors, flywheel re-spins after eval
changes (~+5–10 each), longer-TC re-tests of near-misses, and product/GUI
work (not Elo). The loop's yield curve is itself now a measured result.

**Deferred:** a flywheel re-spin over the mop-up eval was generated
(research/data/texel6.jsonl, 98,535 samples from the mop-up engine) but its
tune was stopped mid-run at session wrap. Resume next session with
`python -m research.texel tune --data research/data/texel6.jsonl` → apply →
UHO gate; expected ~+5–10 per the flywheel yield curve.

---

## 2026-07-18 — Session 17: the flywheel compounds

**exp1 — flywheel iteration 2 (ACCEPTED, 53%, +23).** 98,464 quiet samples
from 5,000 balanced games played BY the XL-tuned engine, retuned from the
accepted weights. +22 =20 −18. The self-improvement loop is real and
converging: +53 (iter 1) → +23 (iter 2). **Drift guard added before iter 3:**
per-spin bounds were relative to *current* weights, so repeated spins
compounded geometrically (bishop pair 30 → 37.5 → 46.9 across two spins) —
exactly the s2 escape route in slow motion. Tuning bounds are now hard-capped
to a 0.5–1.6× envelope of the frozen original hand priors.

**Session 17 close — flywheel parked with +88 banked; pooled anchor 2677
(2575–2776).** Iteration 3 gated +12 (52%, +19 =24 −17) with the drift guard
pinning several weights at the 0.5–1.6× envelope. Spin sequence +53/+23/+12:
halving per iteration, fourth projects to noise — parked until new concepts
join the eval. Anchor honesty note: single 30-game ladders bounced
2654→2685→2743→2606 across four sessions while the gate chain climbed
monotonically; the s16+s17 POOLED 60-game fit (2677, CI 2575–2776) is the
reported point, and 30-game anchors are hereafter treated as ±140
instruments. Chain ≈2778.

**exp2 — flywheel iteration 3 (ACCEPTED, 52%, +12 — see close above).** If it gates
≥50% the loop keeps spinning; below, the fixed point is measured and the
flywheel parks until the eval gains new concepts to tune.

---

## 2026-07-17 — Session 16: taxonomy stress-tests + the faithfulness tax

**exp1 — history-modulated LMR (REJECTED, 43%, −47).** Sharpened the
recoverable-family rule: history already sets the move ORDER, so late quiets
are already index-reduced — modulating reductions by the same signal
double-counts it. The improving signal won because it is ORTHOGONAL to
ordering. Recoverable modulation needs an independent signal.

**exp2 — TT two-bucket replacement (REJECTED, 47%, −23).** First
information-reuse loss: with 4M entries and ~300k nodes/move there is no TT
pressure, so depth-preferred slots just pin STALE entries from earlier game
moves that always-replace used to evict.

**exp3 — eval speed audit (structural).** Re-profiled: eval_core is 32% of
time. Unified the triplicated per-piece attack computation (byte-identical,
kept, flat speed — magic lookups were already ~free). Trialed a C pawn cache
mirroring Python's: values stayed 0.000000 vs Python but a 1-ulp summation
reorder shifted 4 cttd nodes for ~1% — dropped. **Conclusion: exact-eval
speed is tapped out. The eval's 32% is the measured price of
explanation == evaluation — the faithfulness tax.** Future speed comes from
search shape or hardware, not eval shortcuts.

**Session 16 close — Texel-XL lands (+53) and the anchor agrees: 2743
(2603–2880) vs chain 2738.** The 2800 ladder level jumped 25% → 45%. Run
total since the compiled core (s10–16): **2442 → 2743 anchored, +301 across
~150 gated experiments**, with the interpretability invariant intact the
whole way (C eval == Python eval to 0.000000 on every accepted state).

**exp4 — Texel-XL (ACCEPTED, 58%, +53).** 59,189 quiet samples from 3,000
balanced SF-screened self-play games. Gate +27 =15 −18. **The four-attempt
tuning arc is the run's cleanest science:** eval-MSE target −130 (s2) →
outcome target, confounded labels −29 (s14 v1) → clean labels, 17k samples
+6 (s14 v2) → clean labels, 59k samples **+53**. Each failure was diagnosed
in the LOG and the diagnosis confirmed by the next attempt. Deltas moderated
as data grew (noise shrinkage), all inside chess-prior bounds. The retune
flywheel (more games → better weights) is now a standing tool. The one remaining big swing with an
identified mechanism: v2's failure pointed at data scale (O(10–20k) samples
vs the ~100k+ real Texel setups use). 3,000 balanced games generating
(~60k quiet samples, 3× v2); tune + UHO gate when it lands.

---

## 2026-07-17 — Session 15: the improving family + a taxonomy that predicts

**exp1 — improving heuristic (ACCEPTED, 58%, +53 Elo, −31% nodes).** Static
eval vs 2 plies ago (same side, ~free via the eval hash); late quiets in
non-improving nodes get one extra ply of LMR. In-check plies record a
sentinel and count as not-improving. **The first "search less" change ever
to survive a gate here** — and it fits a taxonomy the whole project record
supports: it deepens REDUCTIONS (recoverable — re-searched on fail-high),
never DISCARDS (futility/RFP/LMP family, all rejected).

**exp2 — futility margins by improving (REJECTED, 48%, −12).** The same
signal applied to a discard mechanism immediately failed, right on script.
The taxonomy now *predicts*: recoverable modulation pays, discard modulation
doesn't, independent of which signal drives it.

**exp3 — continuation history steering LMR (REJECTED, 51%, neutral).** CMH's
proper home in strong engines — but neutral here, like the s14 plain-ordering
variant. At depth ~12 with per-move table resets the signal is too sparse;
top engines harvest it at depth 30+ with persistent tables. CMH closed for
this engine, both homes tried honestly.

**Session 15 close — anchor 2685 (2539–2823), +31 measured over s14.** 30
games vs SF 2600/2800/3000 at 0.3s/move (50% / 25% / 35% — held SF 3000 to
seven draws). Gate-measured gains this session: improving +53, qsearch TT
+35; anchor-chain ≈2795. Session record: 2 accepted, 4 rejected, and the
taxonomy that now *predicts* outcomes: recoverable-decision modulation and
information reuse pay; discard modulation and abstract positional counts
don't; CMH closed in both homes.

**exp5 — qsearch TT probe (ACCEPTED, 55%, +35).** Any stored TT depth ≥
qsearch's depth 0, so search-backed scores cut off at qsearch entry. The
node-count proxy misled in the OTHER direction this time (+17% nodes, match
won anyway). Information reuse: 3-for-3.

**exp4 — space concept (REJECTED, 46%, −29).** Safe center squares on your own side
(files c–f, ranks 2–4, unattacked by enemy pawns), phase-scaled, 2cp each —
a smooth count in the gradient style that keeps winning (king race +110,
king pressure +41). C mirror exact.

---

## 2026-07-17 — Session 14: unbalanced openings + the tuning rematch

**Infrastructure — UHO unbalanced openings for gates (William's suggestion).**
Gates at 2600+ were running 60–70% draws, starving the SPRT of signal. The
match harness now takes `--book <epd>`: TCEC-style ~+1.0-for-White starts,
each played from both colors (pair scoring stays fair). Sourced
UHO_Lichess_4852_v1 (the book Stockfish's own testing framework uses; 2.6M
positions), committed a deterministic 1,000-position sample. **Validated
immediately: the first UHO gate ran 28% draws vs ~65% on the balanced list**
— more than double the decisive games per gate.

**exp1 — continuation history, plain ordering (REJECTED, 51%, +6).** CMH
(quiet quality indexed by previous (piece,to) × current (piece,to)) is the
strongest ordering signal in modern engines — but there it pays through
LMR/pruning modulation, not raw ordering. Ours: neutral strength for +12%
nodes, a 590KB table, and per-quiet piece lookups in order(). +22 =17 −21
over 60 UHO games. Reverted for simplicity; retry when reductions consume it.

**exp3 — aspiration windows, third attempt (REJECTED, 43%, −47 — CLOSED).**
Best-conditioned attempt yet (depth 12+ root scores, mildly positive
deterministic screen for the first time at −1.5% nodes) and still lost the
gate decisively: +18 =16 −26. Three attempts across three engine generations
(s2, s8, s14), three rejections: this eval's iteration-to-iteration swings
blow any useful window, and re-searches cost more than the narrow window
saves. Closed permanently for this engine.

**exp4 — king-pressure proximity gradient (ACCEPTED, 56%, +41).** Pieces
closing in on the enemy king credited `UNIT[piece] × (4 − chebyshev)`,
phase-scaled, 2cp/unit: the swarm matters before it touches the attack zone.
Fixes the s4 divergence motif (center-stuck kings under attack) that three
static terms failed to fix back then. Gate: +25 =17 −18. **The
gradients-beat-rules pattern now has five data points**: king race +110 and
this +41 accepted; Tarrasch rook, square-rule passer, and 50-move rule all
rejected. Smooth distance terms give the search direction; discrete rules
duplicate what 12-ply search already computes and misfire at the boundaries.

**exp2 — Texel-style outcome tuning (v1 REJECTED, retry running).** The rematch of s2's
failed tuning, with the target fixed: logistic loss against OUR self-play
game outcomes (what eval is for), not eval-MSE vs Stockfish (what it isn't).
Guardrails from the s2 lesson: material/tempo anchored, every tuned weight
bounded to a chess-prior interval (±25% default), and adoption requires a
UHO match gate regardless of loss improvement.

**Session 14 close.** Texel v2 (balanced starts, quiet filter, 17.8k
samples): **REJECTED at 51% (+6, neutral)** — the clean-label version proved
the pipeline mechanically (v2's deltas reversed v1's confound-driven passer
inflation) but couldn't beat the hand-set priors. Two-attempt conclusion:
this eval's priors are at a local optimum for outcome-tuning at O(10–20k)
samples; the pipeline stays for tuning future concepts with guessed weights.
**Ladder anchor: 2654 (2505–2794), identical to s12** — the +53 of
gate-measured gains since (connected +12, king-pressure +41) is inside the
30-game ladder's noise, the known compression. Chain: ≈2707 on the anchor
chain. Net session: UHO gate infra (permanent, 2.3× decisive rate),
king-pressure +41, and four rigorous negatives (CMH, Texel ×2, aspiration
closed for good).

v1 verdict: **REJECTED (46%, −29)** despite loss improving 0.0975 → 0.0964.
Two flaws diagnosed: (1) 10k positions from 400 games is ~100× less than
working Texel setups — many weights slammed into their bounds, a classic
overfit sign; (2) **the labels were contaminated by the UHO starts**: White
wins because of the +1.0 opening, and the tuner attributes that to whatever
features correlate. The v2 retry fixes both: balanced starts (random 6-ply
walks screened by Stockfish to |eval| < 50cp), a quiet filter (halfmove
clock ≥ 2, not in check), and 900 games. Generation running.

---

## 2026-07-16 — Session 13: passer-structure concepts (+ a segfault hunt)

**exp1 — connected passers (gating).** Passers with a friendly passer on an
adjacent file get +15cp (chess prior), blockade-multiplied and
endgame-scaled like the base passer bonus. Pawn-only fact → lives inside the
pawn-keyed cache (near-zero cost). Interpretable item: "connected passer on
e5". C mirror exact (eval_check 0.000000). First gate attempt **segfaulted
at game 40** (+13 =16 −10 through 39 — discarded):

**Bug fix — path-buffer overflow on 500+ ply games.** `SS.path` (game
history + search stack) was 384 entries, but the match harness allows
250-move games = 500 plies. Long endgame grinds got *more common* after the
s12 repetition fix (winners no longer shuffle into threefold — they play
on), and game 40 ran long enough to overflow → SIGSEGV (exit −11). Now 4096
entries plus a drop-oldest guard in c_search (is_rep only ever looks back
one halfmove-clock window, so ancient history is dead weight). Regression
test: a 700-ply game searches cleanly (tests/test_core.py). cttd
byte-identical for normal games; committed without a gate (bb5f0d6).
Pattern note: this is the second bug this week whose exposure was CAUSED by
fixing another one — correctness work uncovers correctness work.

**exp1 verdict: ACCEPTED (52%, +12).** Re-run gate vs the overflow-fixed
baseline: +18 =26 −16. Modest, near-free (pawn-cached), kept (0844500).

**exp2 — rook behind passer, Tarrasch rule (REJECTED, 45%, −35).** Textbook
chess that doesn't survive measurement: +16 =22 −22. The +12cp bonus likely
rewards parking the rook passively where this engine's activity terms (open
file, 7th rank) matter more, and at 0.3s/move the long-run Tarrasch payoff
rarely materializes. Reverted.

**exp3 — unstoppable passer, square rule (REJECTED, 47%, −23).** +20 =16 −24.
The square-rule logic itself was verified against a hand-analyzed truth table
(the first draft had a real off-by-one: a defender king entering the square
on its move, or capturing the fresh queen, was being scored as too late — the
sanity probe caught it before any game was played). The verified version
still lost its gate: the C core searches 12+ plies and resolves promotion
races tactically, so the static bonus mostly added misjudged edge cases
(defended promotion squares, mutual races). Reverted.

**Session 13 pattern:** three passer terms tried, one kept. The distance-
gradient term (s12 king race, +110) crushed both discrete-rule terms
(Tarrasch, square rule). Hypothesis for future eval work: smooth gradients
give the search direction; binary rules duplicate what 12-ply search already
computes and misfire at the boundaries.

**State at session close:** anchor 2654 (2505–2794), chain ≈2790. Engine =
king race + connected passers + all s10–12 search/speed work. 121 gated
experiments total across 13 sessions.

---

## 2026-07-16 — Session 12: the dead repetition detector (major bug fix)

**Discovery.** While screening a new eval concept, the full test suite (with
slow tests — which the loop's `-m 'not slow'` gates had been skipping) failed
KBB/KBN mate conversion. Tracing a KBN game showed the *winning* side walking
into threefold repetition at ply 48. Bisect: fails identically at the
learning-tool commit (497c026) — **pre-existing since the session-9 C port**,
invisible to every match gate because gates only see final scores.

**Root cause.** `is_rep()` scanned `path[path_len-2], path[path_len-4], ...`
— but the current position sits at `path_len-1`, so the scan only ever
visited **opposite-side-to-move entries**, which can never match a hash that
includes Z_SIDE. Repetition detection had been completely dead on the C
engine. (The step-by-2 idiom was ported off by one; the Python reference is
correct.)

**Fix.** Scan every entry within the halfmove-clock window (`Board.hm`, added
in s11 exp11): Z_SIDE already rejects wrong-side entries, and stepping by 1
is also the only sound option once null moves interleave the path (a second
latent hole: null-move children now increment `hm` so the clock window covers
their path entries). **KBB and KBN now convert to CHECKMATE (45/57 plies vs
50-move-drawn / threefold before).** Full suite 50/50 green; tactics 24/24 +
29/30 unchanged; conversion tests remain mildly load-flaky (movetime-based).

**Lessons.** (1) Slow tests that gates never run are tests that don't exist —
the conversion suite would have caught this 2 days earlier. (2) A match gate
can't see a bug whose symptom is "draws games it should win" unless the
opponent punishes it; self-play siblings shared the same bug. (3) The s11
"byte-identical" hm-bound validated cleanly partly *because* is_rep almost
never fired.

**Match gate vs HEAD: +16 =36 −8 (57%), +47 Elo (95% −41..+141) — ACCEPTED**
(8c39103). Wins that were being drawn now convert; 2:1 decisive ratio. Chain
estimate ≈**2680** on the project scale (2529 anchor +108 speed +47 this).

**exp1 — passed-pawn king race (ACCEPTED, 71%, ~+110 marginal Elo — the
project's strongest eval change).** Per passer:
`W × (1−phase) × (chebyshev(enemyK, front) − chebyshev(ownK, front))` —
escort your own passer, catch theirs, endgame-scaled, weight 4cp/square set
by chess prior (per the s2/s3 rule: metrics screen concepts, priors set
magnitudes). Interpretable items: "e5 passer escorted by king" / "outrun by
enemy king". Lives outside the pawn-keyed cache (kings move); C mirror exact
(eval_check 0.000000 on 6,204 positions). **Gate: +24 =19 −4 (71%), +158 Elo
(95% +59..+291), SPRT stopped early on H1 at 47 games.** Measurement note,
recorded honestly: the baseline worktree was still pre-rep-fix, so +158
bundles the rep fix's +47 — the concept's marginal effect is ≈+110. 6:1
decisive ratio either way (7611e3b).

**Session 12 close — ladder anchor 2654 (95% 2505–2794),** 30 games vs SF
2600/2800/3000 at 0.3s/move (40% / 30% / 30% — note 2800 and 3000 scored
identically: UCI_Elo compression at fast TC again). **+140 measured over the
s11b anchor** — the rep fix + king race are visible even on the conservative
instrument; the chain estimate (~2790) sits inside the upper CI. Timeline
updated: research/elo_report.html.

**exp2 — 50-move-rule awareness (REJECTED, 48%).** `Board.hm >= 100` now scores 0 in
negamax — the search finally feels the clock, so dawdling lines near the
limit stop looking like wins. Found via KBN conversions timing out at ply 99
by FIFTY_MOVES with zero urgency. cttd nodes unchanged (positions there never
approach the clock); the effect is match-play-only. Test infra: conversion
budget bumped 100→120 plies (KBN takes ~80 under best defence; 0.2s/move
searches made 100 load-flaky — a drawing bug still fails at 120 since the
50-move rule bites at ply 100 of shuffling regardless).

---

## 2026-07-15/16 — Session 11: search-quality experiments on the C core

**exp1 — "search-quality v2" batch (REJECTED, −29 Elo).** Three standard
search-quality upgrades bundled (session-5 style batch gate): (a) log(depth)×
log(movenum) LMR reduction table replacing the 2/3 tiers — tuned to be *more*
aggressive (up to −5 on deep/late quiets), −10% nodes to depth 10; (b) history
malus/gravity — quiets tried before a beta cutoff get −depth² so ordering
learns from failures too; (c) countermove heuristic — quiet reply that refuted
the previous move gets an ordering slot just under killers. Screens all passed
(tactics 24/24, 46 tests green). **Match gate vs session-10 HEAD: +6 =43 −11
(46%), −29 Elo (95% −121..+59); SPRT stopped at H0 after 60 games.** Reverted;
full diff kept in research/searchv2.patch.

The suspect is the aggressive LMR table: reductions of 4–5 plies on late quiets
discard too much at this engine's depths (~10–12) — the same shape as every
"do less per node" rejection in this project's history (RFP, LMP, tuned-weight
magnitudes). The 24-position tactics screen can't see it; only games can.

**exp2 — ablation: history malus + countermove only, baseline LMR (ACCEPTED,
+35 Elo).** Isolates the ordering-quality half of the batch from the
reduction-aggression half. Screens passed (tactics 24/24, tests green; +10%
nodes on the 4-position cttd — same weak proxy that mispredicted SEE
ordering's +53). **Match gate vs session-10 HEAD: +11 =44 −5 (55%), +35 Elo
(95% −53..+128)** over 60 games at 0.3s/move; 2.2:1 decisive ratio. Kept
(f0525a6). Clean ablation story: better ordering helps (+35); 4–5-ply LMR
reductions on top of it were worth ≈−60 and sank the batch. One more entry
for "ordering quality > doing less per node" — and for never trusting a batch
verdict without ablating.

**State after s11 so far:** s10 + malus/countermove ≈ **2530 Elo** (chained:
2442 anchor +53 +35; two chained hops now, fresh ladder anchor queued).

**exps 3–6 — the byte-identical speed batch (all KEPT, −21% time to depth).**
Four speedups, each validated by EXACTLY unchanged cttd node counts
(3,418,463 across the 4-position suite) so search shape is provably untouched
— the no-gate protocol from the s5 eval cache / s10 incremental hashing:
- **eval hash** (−4%): side-to-move static eval cached by Board.hash (hash
  covers side via Z_SIDE; full 64-bit key compare like the TT). qsearch
  stand-pat + futility probes stop recomputing eval_core.
- **captures-only movegen in deep qsearch** (−7%): gen_legal_captures()
  generates captures + queen promos in gen_pseudo's exact relative order;
  qd>0 nodes skip the copy+in_check legality tax on the ~90% of moves they
  were about to discard. (Same win the Python engine got in s1 exp2 — the C
  port had regressed to generate-all-and-filter.)
- **quiet-check test on a light copy** (−2%): the qd==0 quiet-checks scan
  paid full make() per quiet just to test check; in_check only reads piece
  bitboards, so test on make_light and pay make() only for actual checkers.
- **lazy legality via ordered pseudo list** (−10%, the big one): negamax
  orders the pseudo-legal list up front (stable sort + per-move scores keep
  the legal moves' relative order identical) and legality-tests each move
  only when the loop reaches it. On a first-move cutoff — the common case at
  interior nodes with a TT move — the other ~35 copy+in_check tests are never
  paid. Subtle design point: an earlier "staged TT-move" draft searched the
  TT move before ordering the rest, which reads the history table *after* the
  TT subtree updated it — not byte-identical, would have needed a match gate.
  Ordering pseudo-moves first keeps order() before any child search.

Net: 3.12s → 2.46s to depth 10 on the cttd suite; benchmark now ~2.0M NPS,
depth 10–11 middlegames @2s (vs 9 at the s9 port). Perft + eval cross-check
(0.000000 on 6,204) + 46 tests + tactics 24/24 green throughout.

**Fresh ladder anchor: 2529 Elo (95% 2388–2666)** — 30 games vs SF 2400/2600/
2800 at 0.3s/move (60% / 50% / 15%). The independent measurement lands within
1 Elo of the chained estimate (2442 + 53 + 35 ≈ 2530), validating both the
chain and the anchor methodology (now reproducible via
`python -m research.ladder_anchor`, which refits every committed historical
anchor exactly). Timeline updated: research/elo_report.html.

**Session 11 close — the speed batch is worth +108 Elo head-to-head, and the
SF ladder can't see it.** Two measurements of the same engine state:
- Fresh ladder anchor (30 games, SF 2400/2600/2800): **2514 (2372–2652)** —
  statistically identical to the pre-speed-batch 2529.
- Direct head-to-head vs the pre-speed-batch state (f0525a6, same strength
  features, −48% time): **+21 =36 −3 (65%), +108 Elo (95% +20..+211)** over
  60 games. CI excludes zero; 7:1 decisive ratio.

Interpretation: UCI_Elo-limited Stockfish plays with deliberate mistakes; once
our depth suffices to refute them, additional depth converts poorly *against
that opponent* — but converts fully against an equal engine. Lesson for the
Elo timeline: the ladder anchors are a conservative, internally-consistent
scale, but chained head-to-heads are the sensitive instrument for recent
gains. Both are recorded; the chain now places the engine ≈**2620–2640** on
the project scale while the anchor says ~2514 — the gap is the instrument,
not the engine.

**exp10 — null-move static-eval guard (ACCEPTED, 51%, −11% nodes).** Only try
null move when `eval_stm(b) >= beta`: statically-below-beta positions almost
never fail high on a pass, so the reduced search was wasted; skipping also
avoids some wrong cutoffs where the eval overestimates (near-zugzwang).
Nearly free via the eval hash. Deterministic screen: 3,418k → 3,047k nodes to
depth 10 (−11%), −6% time. **Match gate vs HEAD: +9 =43 −8 (51%, +6 Elo)** —
neutral strength, free speed. Kept (7082a25).

**exp11 — halfmove-clock repetition bound (KEPT, byte-identical).** Board now
tracks the halfmove clock (set_fen parses FEN field 5; make() resets on pawn
moves/captures); is_rep scans only back to the last irreversible move —
identical answers, O(hm) instead of O(game length) per node. Invisible in
cttd (short search paths) but real in games, where the path carries 80–160
entries. Also unlocks proper 50-move detection as future work (currently the
engine has none — the doc header overstated it).

**Infrastructure — tactics suite v2.** 30 positions mined at SF depth 22 with
a ≥250cp best-vs-second gap. The engine saturates it at 1s (30/30 — modern
depth solves any verified 1-move tactic), so the regression gate runs at
0.25s where baseline is 29/30. Lesson: harder suites for a 2500+ engine need
multi-move quiet tactics, not deeper verification of 1-move wins.
tests/test_tactics.py::test_tactics_suite_v2 gates at 90%.

**exp8 — is_legal() bitboard surgery (KEPT, −10% time).** Profiling (macOS
`sample` on a 12s search) showed make_light at 20% of time — every legality
test copied the Board + mutated + refreshed occupancy. is_legal() instead
builds the post-move occupancy and captured-piece removal in locals and
probes attacks from the (possibly moved) king square via magic lookups —
handles ep double-removal, castle rook relocation, king moves. Perft exact,
cttd nodes EXACTLY 3,418,463, 1.79 → 1.61s. **Session speed: 3.12 → 1.61s
(−48%).**

**exp9 — lazy best-move selection (REJECTED, no gain).** Replaced order()'s
full insertion sort in negamax with score-once + pick-max-on-demand
(original-index tie-break for byte-identical order). Nodes identical, time
unchanged (1.62 vs 1.61s): the sort isn't the hot part of ordering (the
see()/history scoring is), and each skipped illegal move newly paid an O(n)
selection scan. Reverted — simplicity wins when the metric says no.

**exp7 — magic bitboards (KEPT, −28% time, the second-biggest speed win).**
slide()'s ray-walking loops — the primitive under in_check/legality tests,
SEE, movegen, and eval mobility — replaced by one multiply + table lookup.
Magics are found at init by seeded deterministic search (<0.5s once per
process); the tables are built FROM slide() and verified injective, so attack
sets are identical **by construction**. cttd 2.46 → 1.79s; nodes EXACTLY
3,418,463 again. **Session speed total: 3.12 → 1.79s (−43%), all
byte-identical.** Benchmark: 3.76M NPS (2.04M pre-magics; 38k at v0 — a 100×
project journey). Landed *after* the 2529 anchor, so the next anchor captures
its fixed-movetime Elo.

---

## 2026-07-15 — Session 10: post-core search cleanups (hashing, SEE ordering, two bug fixes)

First session on top of the compiled core. Theme: squeeze the C search and fix
correctness debt, gating strength changes against the pre-change core.

**exp1 — incremental Zobrist hashing (KEPT).** `Board.hash` is now maintained
incrementally by `make()` (XOR exactly what changed) instead of every negamax
node recomputing it from scratch. First attempt was *slower* (1.28→1.33s to
depth 9) because `gen_legal()`'s throwaway legality-test copies were paying for
hash upkeep they never use; added `make_light()` (piece placement only, no
hash/castle/ep/side) for that path. Net **1.28→1.22s to depth 9 (−5%), node
count BYTE-IDENTICAL** (1,401,527) so search shape is unchanged — no match gate
needed, same reasoning as the session-5 eval cache. Verified: perft unchanged,
a hash-verify walk over 350k+ positions finds zero mismatches vs from-scratch
recompute (`tests/test_core.py`), eval cross-check still 0.000000, 46 tests pass.

**Bug fix — promotion moves reported the WRONG piece (since session 9).** A
critical correctness bug in the C move encoding surfaced in coach output;
fixed and committed (`61ce8a2`). Lesson logged: the promo-piece index table is
`" nbrq"` (index 0 unused), easy to off-by-one.

**exp2 — SEE-based capture ordering in the main search (ACCEPTED, +53 Elo).**
`order()` now ranks captures by static-exchange value (actual material outcome),
demoting losing captures (SEE<0) below quiet-move history — still searched, just
not explored first. This mirrors the signal qsearch already prunes on.
- Deterministic metric said **NO**: +7% nodes / +5% time to depth 9. Node-count
  is a weak proxy (this project has repeatedly seen it mislead), so it was
  gated with real games rather than trusting the metric.
- **Match gate vs the pre-SEE core: +15 =39 −6 (58%), +53 Elo** (95% −35..+147)
  over 60 games at 0.3s/move. Clearly positive (15 wins vs 6 losses, 2.5:1)
  despite the metric's verdict — searching better moves first wins even at a
  small per-node cost. Kept.
- **Reinforces the core methodology:** ordering quality > raw node count; the
  match is ground truth. The one metric that *is* reliable (byte-identical node
  count for shape-neutral speedups, exp1) still held.

**Bug fix — SPRT crashed on high draw rates** (math domain error in the
trinomial LLR when the draw fraction dominated); fixed (`aec23e9`).

**State after session 10:** compiled core + incremental hashing + SEE ordering.
Estimated **≈2495 Elo** (2442 anchor + 53 head-to-head; re-anchor on a fresh SF
ladder pending). Interpretability untouched — all changes are in search/hashing;
C eval still == Python concept eval to 0.000000.

---

## 2026-07-14 — Learning-tool session: from "engine that explains" to "coach"

Full session on interpretability + the app as a teaching tool (engine strength
unchanged). First restored the contrastive "alternative" for the C engine
(c_search now exports its runner-up; core.eval_move scores any move by searching
the child position — the reusable primitive behind everything below).

New coaching layer (gui/coach.py + server routes + redesigned GUI), all reusing
the compiled search and the interpretable concept breakdown so every number is
a real evaluation:
- **Coach my moves** — instant verdict on each human move vs the engine's best,
  in concept terms, with clear mate phrasing ("walks into a forced mate in 1").
- **Candidates** — top moves ranked, each with the concepts it changes + line.
- **Insights** — board overlays: hanging pieces (yours/winnable), king under
  attack, passed pawns.
- **Review** — post-game blunder detection (loss = E_i + E_{i+1}); each move
  marked on the eval graph + move list by quality.
- **Concepts** — glossary of every eval term (what + why).
Consistent best→blunder color scale throughout. 45 tests pass; the compiled
eval is still verified identical to the Python concept eval.

# Research log

Newest entries at the top. Every experiment gets an entry, including rejected
ones — negative results are data. Structured metrics per experiment live in
research/metrics.json (source of truth for the progress graphs).

---

## 2026-07-14 — Session 9: compiled core (C engine) — the big strength jump

After the session-8 plateau, ported the engine core to C (clang → shared lib,
loaded via ctypes; no new Python deps). Four milestones, each validated:

- **M1 move generator** (core/cengine.c): bitboard board + legal move gen
  (copy-make). **Perft matches python-chess exactly** on startpos, Kiwipete, and
  3 tricky endgames (core/perft_check.py). **~43× faster** (42.8 vs 0.99 Mnps).
- **M2 eval** (core/ceval.c): every concept ported to C; constants generated
  from the Python source (core/gen_eval_data.py → eval_data.h) so they can't
  drift. **Cross-check: C eval == Python eval to 0.000000 on 6,204 positions**
  (core/eval_check.py) — this is the interpretability guarantee.
- **M3 search** (core/csearch.c): iterative-deepening negamax, Zobrist TT,
  MVV-LVA/killer/history ordering, quiescence + SEE + first-ply checks, null
  move, two-tier LMR, PVS, futility, check extension, draw detection, PV export.
  On the Italian at 1s: **depth 9 / 1.0 Mnps vs Python depth 4 / 20 knps.**
- **M4 integration**: Engine uses the C core by default; the Python explanation
  layer stays authoritative (breakdowns from evaluate_detailed, expected line
  from the C PV). The C eval == Python eval, so the fast search optimizes
  exactly what the breakdown shows. All 43 tests pass; UCI/GUI/matches run C.

**Head-to-head gate vs the session-8 Python engine: +24 =6 −0 (90%), +382 Elo
(95% +233..+1200) — zero losses in 30 games.** The compiled core is the single
biggest jump in the project. Interpretability fully preserved: the concept
breakdown and per-concept explanations are unchanged and still exact.

**Ladder anchor: 2442 Elo (95% 2305–2582)** over 30 games vs SF 2200–2600 — up from the Python engine's ~2018 (+424, consistent with the +382 head-to-head). Same interpretable eval; the jump is entirely from ~50x deeper search.

Notes for future work: the contrastive "alternative" explanation currently
needs the Python path (use_core=False) — the C search doesn't export the root
ranking yet. Any eval change must re-run core/gen_eval_data.py + rebuild, or
tests/test_core.py::test_c_eval_matches_python fails by design.

---

## 2026-07-14 — Session 8: search refinements (both reverted) + plateau assessment

Two untried search levers, both gated, both reverted — the engine is at a hard
local optimum:
- **Aspiration windows** (failed in s2, retried since the search is more stable):
  −7% nodes to depth 7, but gated **46% (−26 Elo)** — neutral, same verdict as s2.
- **One-reply extension** (forced single-legal moves +1 ply): gated **36%
  (−98 Elo)**. At fixed movetime, extending steals time from breadth, and
  one-reply moves are often already check-extended (double extension).

**Plateau assessment.** Across this run every incremental search change has been
either metric-gameable-but-strength-negative (reverse futility, late-move
pruning) or directly neutral/negative (time management, aspiration, one-reply
extension, book expansion). Only two things stuck: the session-6 opening book
and the session-7 mating drive. Conclusion: **pure-Python search + a
deliberately-simple eval is genuinely optimized at ~2018 Elo for this time
control.** The one remaining large strength lever is a compiled core (move
generation + eval in C/Rust, ~10–50× nodes/sec), which is a rewrite rather than
a loop-sized experiment — and it would keep interpretability by mirroring the
Python eval as a cross-checked reference. Engine unchanged this session.

---

## 2026-07-14 — Session 7: endgame technique

Theme: fix concrete endgame weaknesses (interpretable), found by a conversion
diagnostic (self-play a won position to mate vs a defender).

**Diagnostic found real holes:** KQ/KR vs K mate fine (search handles them),
but **K+2B vs K and K+B+N vs K were NOT converted in 120 plies** (drawn by the
50-move rule), and a won **K+P vs K was lost** (pawn given away).

**The win: a "mating drive" concept (`engine/concepts/mate_drive.py`).** In
bare-king endgames only, it drives the enemy king toward a corner (center-
manhattan distance) and brings our king up. After: **KBB mate in 67 plies, KBN
in 79** — both inside the 50-move rule, from unconvertable before. It is
*provably neutral outside bare-king endgames* — returns exactly 0 on all
non-lone-king positions (verified: the 74/2204 eval-set triggers are all
genuine bare-king endgames), so it needs no match gate and cannot touch normal
play. Interpretable: "White driving the black king toward the corner." Tests in
tests/test_endgame.py (gradient + KBB/KBN conversion).

**Two negative results:**
- **KPvK bitbase — dropped.** The KPvK loss needs exact opposition/key-square
  knowledge (distance heuristics give the *wrong* sign there). A retrograde
  bitbase is the correct fix but is a correctness rabbit hole for a very rare
  endgame — poor Elo-per-effort. Noted as future work.
- **Book expansion — gate-rejected.** Doubled the book (250→478 positions, adding
  Najdorf/Dragon/Winawer/etc.) expecting more coverage = more Elo. It gated at
  **36% (−98 Elo)** vs the session-6 book. Those lines are theoretically sound
  but practically sharp, and our simple-eval engine mishandles them; the narrow
  book had implicitly selected lines that *suit* this engine. Reverted. Lesson:
  book quality for a given engine ≠ maximal theory coverage.

**Net:** engine stays ≈2018 Elo (mate-drive helps rare endgames the 40-game
ladder rarely reaches, so no re-anchor) but now converts the basic mates it was
drawing. Two more entries for the "more isn't better — measure it" column.

---

## 2026-07-14 — Session 6: pruning dead-ends, SPRT tooling, opening book

Theme: more search strength. The session's biggest lesson is a negative one,
and its win came from an unglamorous place.

**Tooling:** `research/sprt.py` — trinomial SPRT (H0 elo=0 vs H1 elo=+35) with a
self-test; `match.py --sprt` stops a gate as soon as it is decisive. `exp6.py`
reuses the time-to-depth metric.

**Pruning is a trap for THIS engine (the key finding).** The time-to-depth
metric rewards node-cutting unconditionally, so every pruning idea "passed" it —
and every one lost its match gate:
- reverse futility + late-move pruning stacked: −38% time to depth, gate **42%**
- reverse futility alone (buggy: applied at PV nodes): gate **29%**
- reverse futility fixed (non-PV only, conservative 100cp/depth): gate **40%**
All reverted. RFP trusts the static eval to predict the search result; ours is
deliberately simple and interpretable (rank agreement ~47%), so static-eval
pruning discards too many real fail-lows. **Generalized rule: a fast metric
that rewards doing-less (pruning → fewer nodes, like s2's weight magnitudes →
lower loss) is gameable and must be match-gated.** Time management was also
tried and is neutral at fixed movetime (reverted).

**The win: an opening book (interpretable).** `engine/book.py` — 17 openings /
250 positions of mainline theory compiled from SAN, consulted for the first 16
plies, working for either colour. Book moves are played instantly and reported
as "Book move: Ruy Lopez", not dressed up as a search result. Gate vs the
no-book session-5 engine: **+20 =2 −8 (70%), +147 Elo (95% +25..+321)** — a
clear, significant gain. It keeps the engine out of dubious openings and saves
clock for the middlegame; both help at 0.3s/move. GUI labels book moves.

**Ladder anchor: ~2018 Elo (95% 1905–2134)** over 40 games vs SF 1800–2100 —
up from session-5's 1850, consistent with the +147 head-to-head. 65% / 60% /
55% / 55% across the four levels.

---

## 2026-07-14 — Session 5: search sprint

Metric: wall time to fixed depth-6 over 4 positions (research/ttd.py), nodes
reported for determinism; quality-affecting changes match-gated. Runner:
research/exp5.py → session5.json. Baseline: 388,774 nodes / 15.56s.

| # | Change | Result | Verdict |
|---|---|---|---|
| 1 | Eval cache keyed by transposition key | −18.7% time, nodes identical | KEPT |
| 2 | Bitboard capture test in ordering | +1.3% — under the 3% bar | DISCARDED |
| 3 | Adaptive null-move R (+1 at depth ≥6) | −13% nodes at d7 (d6-blind) | KEPT |
| 4 | LMR r=3 tier for moves ≥12 | −23% time, tactics 100% | KEPT |
| 5 | LMR onset i≥3 | −7.7% time | KEPT |
| 6 | SEE pruning + ordering in qsearch | −29% time, −33% nodes | KEPT |
| 7 | Qsearch evasions + first-ply quiet checks | +54% time tax; gate +5 =1 −4 (55%) | KEPT (gated) |

Net: **15.56s → 9.88s to depth 6 with strictly better search quality** (2.4×
faster before the check extension spent some of it on tactics). SEE bug worth
remembering: `attackers_mask(color, sq, occupied)` intersects the board's full
piece sets — mask the result with the shrinking occupancy or SEE loops forever.

**Batch gate: +9 =5 −6 (57.5%) over 20 games vs session-4 ≈ +53 Elo** —
consistent with ~1 extra ply at 0.3s/move.

**Ladder anchor:** (results below — see metrics.json exp 12 / elo_report.html.)

---

## 2026-07-14 — Session 4: divergence mining + Stockfish ladder + Elo timeline

**GUI (user-driven):** square colors were inverted (a1 rendered light) — fixed,
queens now start on their color; pieces enlarged; eval bar only moves on
completed searches; new Moves tab (click any move to view that position) and
Eval-graph tab; server returns SAN history.

**Divergence mining (research/divergence.py):** ranked the eval set by
|winprob(ours) − winprob(SF)|. 126/150 worst cases are queens-on middlegames;
the dominant motif is a king stuck in the center under attack (SF +4, us −1.5).
Three targeted experiments, all honestly discarded:
- stuck-in-center penalty: BOTH metrics worse at every weight 15–90 (misfires
  on legitimately-fine uncastled kings in this distribution)
- pawn-storm units in king attack: rank −0.39pt, evalloss −0.0001 — mixed noise
- kattack scale sweep: 3.0 confirmed optimal on both metrics
Conclusion: this error class likely needs search (deeper attack resolution),
not more static terms. Candidate: qsearch checks, king-attack extensions.

**Stockfish ladder (60 games, levels 1320–1800 @ 0.3s/move):**
100% / 85% / 65% / 75% / 60% / 60% → **MLE 1773 Elo (95% 1668–1886)**.
Re-anchored the session-1 state on the same ladder (20 games): ≈1737
(1575–1916) — consistent with the +70 head-to-head chain since. The original
"1435" anchor was a noisy 10-game draw; scale caveat: UCI_Elo differences
compress at fast time controls (60% vs 1700 AND 1800).

**Elo timeline:** research/elo_timeline.py → elo_timeline.svg / elo_report.html.
Honest picture: session 1 (search) bought the big jump; sessions 2–4 are flat
within error bars — they bought explanation quality, metrics infrastructure,
and negative knowledge instead.

---

## 2026-07-13 — Session 3: metric research + move-ranking loop + contrastive explanations

**Meta-experiment (the session's core deliverable).** Validated 4 candidate
fast metrics against 4 engine states with match-measured strength spanning
~350 Elo (research/validate_metrics.py, results in metric_validation.json):

| metric | verdict |
|---|---|
| evalloss (session 2) | perfectly ANTI-correlated — retired as a target |
| **rank agreement** (static eval picks SF's best of its top-3, margin ≥30cp) | **monotone with strength, <1s — adopted** |
| qrank agreement (quiescence values) | monotone, smaller spread, slower |
| move-match @ depth 3 | noisy, non-monotone at n=250 — rejected |

**Loop results (session3.json, 8 experiments):**
- Shared attack masks in EvalContext (−3.7% time to depth) and bitmask-based
  threats (+15% NPS) — speed, eval-identical.
- Threats concept re-screened: rank metric kept it (+1.6pt val) where evalloss
  had rejected it; **match gate confirmed 0.1× weight (55% vs pre-threats)**.
- **Second gaming failure documented:** the rank metric wanted threat weight
  0.6 (+5.1pt val!) but that engine scored 5% in the gate match (~−500 Elo) —
  a large static threat term fakes 1-ply lookahead and double-counts with
  quiescence. **Standing rule: fast metrics screen concepts and directions;
  matches set weight magnitudes. No weight change ships without a gate.**

**Interpretability (product):** contrastive explanations — search reports its
root-move ranking, the runner-up gets a brief sub-search, and the panel now
explains the *choice*: "Nf3 was preferred over Bc4: the line after Bc4 is
worse for White mainly in king safety (−0.35)…" with the alternative's line
shown in the GUI and its shallower depth disclosed. tests/test_explain.py
extends faithfulness to the contrast: alternative breakdowns must be exact
evals, diffs exactly best−alt per concept, and no personification.

**Final state:** exp-13 concepts + threats@0.1 + speed fixes. Tactics 24/24,
avg depth 7.83 @2s, ~37k NPS. Strength ≈ session-1 +35±small (gate matches).

---

## 2026-07-13 — Session 2: eval-accuracy autoresearch (32 rapid experiments)

**Methodology.** Built a fast optimization target: `eval loss` = MSE between
win-prob of our static eval and Stockfish depth-12, over 2,204 quiet positions
from self-play/random games (train 1,470 / held-out val 734, committed in
research/data/). Central weights module (engine/weights.py), coordinate-descent
tuner (research/tune.py), one-command experiment runner (research/exp2.py) that
logs every attempt to session2.json. **Cycle time ~0.5s per experiment** vs
minutes in session 1. Graph: `python -m research.plot2`.

**What the metric was good at (screening concepts):**
- KEPT: king attack units (quadratic, phase-scaled), safe mobility (exclude
  enemy-pawn-controlled squares), blockaded passers, bad bishop, graded shield.
- DISCARDED honestly: threats/hanging pieces, knight outposts, protected
  passers, aspiration-style material re-trades (train improved, val worsened).

**The headline negative result: the metric is a harmful optimization target
for weight values.** Sequential joint tuning drove val loss 0.0197 → 0.0168
(−15%) but produced chess-nonsense weights (semi-open > open file, ~free
doubled pawns, zeroed PSTs) — and match play was monotonically anti-correlated
with loss beyond small doses:
- unbounded-tuned vs chess-prior-bounded: bounded won +7 =1 −2 (~+190 Elo)
- fully-tuned (bounded) vs session-1: **32.5% over 20 games (~−130 Elo)**
- exp-13 state (new concepts, prior weights) vs session-1: 55% (+4 =3 −3)

**Adopted final state: exp-13** — the new interpretable concepts at chess-prior
weights (≈ session-1 strength, richer explanations). All tuning drift reverted.

**Why the proxy fails (hypotheses for session 3):** (1) play depends on eval
*differences between sibling positions*, not absolute agreement with SF on
quiet positions; (2) NPS cost of new concepts (−14%) eats depth; (3) tuned
scales interact with search constants (futility margins, delta pruning, tempo
in stand-pat). Better target candidates: move-agreement with SF at fixed
nodes, or direct small-match Elo with sequential pruning (SPRT-lite).

---

## 2026-07-13 — Session 1: speed + search (experiments 1–7)

Profiling showed 68% of time in eval, dominated by dict building and f-string
detail lists on the hot path. Fixed that, then attacked search depth.

| # | Hypothesis | Result | Verdict |
|---|---|---|---|
| 1 | String-free eval fast path (bitboard EvalContext) | 38.0k → 45.3k NPS | ACCEPTED b185f02 |
| 2 | Qsearch generates captures directly | 45.3k → 51.4k NPS | ACCEPTED |
| 3 | Pawn-keyed caches (pawn structure, king safety) | 51.4k → 55.1k NPS | ACCEPTED |
| 4 | Late move reductions | avg depth 7.0 → 8.2 @2s; tactics 23→24/24 | ACCEPTED |
| 5 | Principal variation search | −2.4% nodes to depth 6 | ACCEPTED |
| 6 | Aspiration windows (±50, ±100) | +0.8% / −0.2% nodes — noise | **REJECTED** |
| 7 | Futility pruning (150/300cp margins, depth ≤2) | −38% nodes to depth 6, −16% time | ACCEPTED |

Notes:
- Node counts at fixed depth are deterministic — use them (not wall-clock NPS)
  to judge search-shaping changes. Script: nodes-to-depth-6 over 4 positions.
- Aspiration windows fail here because iteration-to-iteration score swings
  regularly exceed ±100cp with this eval; revisit only after eval tuning
  stabilizes scores.
- End state: avg depth 8.17 @2s (middlegames 5–6, was 4), 24/24 tactics.
- **Strength gate (exp 8): +11 =7 −2 (72.5%) vs v0 over 20 games ≈ +168 Elo**
  (95% CI ~ +20..+425), 10 openings, both colors, 0.3s/move. GATE PASSED.
- **Absolute anchor: +5 =1 −4 (55%) vs Stockfish-1400 over 10 games at
  0.3s/move → engine ≈ 1435 Elo** (wide CI; re-anchor with 30+ games later).
- The match surfaced a real bug (fixed, committed): when depth 1 didn't finish
  inside the budget, search returned no move and UCI sent an illegal null move.
  Lesson: matches are also integration tests — run them even for "pure speed"
  sessions.

---

## 2026-07-13 — Neutral analytical explanations

**What:** Removed personification from the explanation layer. Output is now:
verdict ("White is clearly better (+1.45)" / "Forced mate in 2 for Black"),
main factors at the end of the expected line, biggest concept shifts over the
line (tempo excluded as uninstructive), and an explicit residual note when
quiescence tactics beyond the PV make the search score differ from the static
breakdown by >0.60. GUI: breakdown chart labeled with its scope (current
position vs end of expected line), concept items sorted by magnitude.

**Verdict:** ACCEPTED (product change; no strength impact, tests green).

---

## 2026-07-13 — v0 baseline (initial build)

**What:** Full rewrite from scratch. Concept-sum evaluation (material,
placement/PST, pawn structure, king safety, mobility, activity, tempo) with
enforced faithfulness (explanation == search eval). Negamax search with TT,
MVV-LVA + killers + history, quiescence + delta pruning, null move, check
extension, soft time management. UCI interface, web GUI with live concept
breakdown, Stockfish-verified tactics suite miner.

**Numbers (baseline, this machine):**
- Benchmark (2s/pos): avg depth 6.83 (middlegames 4, endgames 6–17), avg NPS ~38k
- Tactics v1 (24 Stockfish-verified positions, 1s/move): 23/24 = 95.8%
  - suite is capture-heavy; harder suites needed (see ROADMAP)
- No match data yet — first loop session should establish a Stockfish-limited
  anchor (suggest: 20 games vs stockfish:1400 at 0.5s/move) and use
  version-vs-version matches thereafter.

**Verdict:** ACCEPTED (v0 baseline).

**Known weaknesses to attack first:** no LMR/PVS (depth), `_transposition_key`
and mobility are likely hot spots (profile first), endgame technique, tactics
suite too easy.

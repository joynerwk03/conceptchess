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

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

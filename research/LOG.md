# Research log

Newest entries at the top. Every experiment gets an entry, including rejected
ones — negative results are data. Structured metrics per experiment live in
research/metrics.json (source of truth for the progress graphs).

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

# Research log

Newest entries at the top. Every experiment gets an entry, including rejected
ones — negative results are data.

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

# Research schedule — closing the gap to a classical Stockfish

Written 2026-08-04, after reading Stockfish 11 (`sf_11`, Jan 2020) — the **last
classical Stockfish**, ~3450 Elo, hand-crafted evaluation plus alpha-beta. That
is our exact architecture, roughly 700 Elo ahead, and it is a far better
reference than modern Stockfish, whose search is tuned around NNUE's evaluation
characteristics and whose gains are sub-1-Elo each (measured: the "small
ProbCut" commit passed with SPRT bounds `{0.25, 1.25}` over 33,440 games — below
anything this project can resolve).

*Ideas only. Stockfish is GPL; nothing is copied. Everything below is
reimplemented from understanding, and every term must satisfy the concept-sum
invariant and the C==Python mirror.*

## Why the method has to change first

The last 26 hypotheses produced **one** acceptance (+9). That is not bad luck —
it is a measurement floor. An 800-game gate resolves ±19 Elo, and SF 11's
individual eval terms are each worth roughly 5–20. **Testing them one at a time
is guaranteed to return "neutral" no matter how good they are.**

So the unit of work changes: **build bundles, tune them together, gate the
bundle.** Six terms worth +8 each is +48, which is measurable. Single terms are
not. This is the single most important line in this document.

## What SF 11 has that we do not

| | Stockfish 11 | ConceptChess |
|---|---|---|
| **Every term is `make_score(mg, eg)`** | yes, tapered by phase | only pawn/king PSTs taper |
| Material imbalance (Kaufman quadratic) | yes | none |
| Space | yes | none |
| Initiative / complexity correction on the whole score | yes | framework exists, empty |
| Per-piece terms | outpost, reachable outpost, minor-behind-pawn, king-protector, bishop-pawns, long-diagonal bishop, cornered bishop, rook-on-queen-file, rook-on-file, trapped rook, weak queen | rook open/semi/7th, bishop pair |
| Threats | by minor / rook / king / safe pawn / pawn push, hanging, restricted piece, knight-on-queen, slider-on-queen | hanging, by pawn / minor / rook, initiative multiplier |
| King safety | king danger² (MG) and linear (EG), safe checks, flank attacks, pawnless flank, king-ring attack counts | shield gaps, open files, attack-units², proximity |

The two most striking:

**1. MG/EG everywhere.** SF 11 gives *every* weight two values. King danger is
`make_score(danger²/4096, danger/16)` — quadratic in the middlegame, linear in
the endgame. This is exactly the "blended evaluation" question, and we do it for
two PSTs only.

**2. `initiative(score)` is a correction applied to the entire score**, built
from outflanking, infiltration, pawns on both flanks, passed-pawn count and an
"almost unwinnable" flag, and carefully capped so it cannot flip the sign. That
is precisely the multiplicative-modifier idea, validated at 3450 Elo — and our
modifier framework currently holds one term that fires in **0.0%** of real
positions.

## Phases

### Phase 1 — MG/EG infrastructure (no Elo, unblocks everything)
Give every weight an endgame counterpart, initialised to the current value so the
change is a provable **no-op**: `eval_check` stays 0.000000 and fixed-depth node
counts stay byte-identical. **Validation costs zero games** — the class of change
this project should always prefer. Doubles the eval's capacity.

### Phase 2 — Re-tune the doubled parameter set
Texel on game outcomes (the target s16–17 established; *not* eval-MSE), fresh
data from the current engine. The flywheel "converged" three sessions ago — but it
converged on *today's* parameterisation. A richer one has capacity it never had.
Gate the tuned result as one bundle.

### Phase 3 — Term bundles from SF 11, four at a time
Each bundle: implement → `research.firing_rate` (kill anything firing <2% or
non-zero on the start position) → `eval_check` 0.000000 → SPRT screen → confirm
on disjoint openings → re-tune → re-gate.

- **A, piece placement**: outposts + reachable outposts, minor behind pawn,
  bishop pawns (blocked by own colour), long-diagonal bishop, rook on queen file,
  trapped rook, weak queen, king protector.
- **B, threats**: restricted pieces, threat by safe pawn, knight-on-queen,
  slider-on-queen.
- **C, king safety**: safe checks (retry — s24 rejected it standalone at weight
  10 and 3, but SF uses it *inside* a king-danger accumulator, not as a separate
  additive term), flank attacks, pawnless flank.
- **D, structural**: imbalance table, space.

### Phase 4 — Initiative / complexity modifier
The whole-score correction, in the existing modifier framework, displayed as its
marginal delta so the breakdown still sums to the total.

## Honest expectation

SF 11 is ~3450; we are ~2750 single-threaded. **That gap is not all evaluation** —
much of it is search depth from thirty years of tuning, and we have already
measured that our reduction schedule is at an optimum for the depth we reach.
A richer eval plus a real re-tune plausibly buys **50–150 Elo**, which would be
the largest gain since Lazy SMP. It will not buy 700, and any plan that claims
otherwise is selling something.

## Standing rules that still apply

- Screen with `research/screen.sh` (SPRT, worktree-isolated); the screen
  **nominates**, only a confirmation on disjoint openings decides.
- `research.firing_rate` before gating any eval concept.
- Eval changes need `research.abgate` (external) — self-play does not transfer.
- Prefer changes whose validation needs **no games**: byte-identical refactors,
  provable no-ops, correctness fixes.

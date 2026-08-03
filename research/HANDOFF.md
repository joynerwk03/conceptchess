# Handoff — where the research loop stands

Updated 2026-08-02 (end of session 26). `research/LOG.md` is the full record;
this file is just "where we are and what to do next".

## Setup

The Windows/WSL2 box is set up and verified — no migration work left. Repo lives
at `~/mission-control/projects/conceptchess` (WSL2's own ext4, NOT `/mnt/c/...`,
or match timings distort). Stockfish 18 is at `~/.local/bin/stockfish` (installed
without root), and **`~/.local/bin` is only on PATH in a LOGIN shell** — scripts
that shell out must `export PATH="$HOME/.local/bin:$PATH"`.

Hardware: i9-10900K, 10 physical cores / 20 threads, 918 GB free. Use
`--concurrency 8` for gates (validated unbiased, and measured NOT to weaken the
engines: 375k nodes per 0.3s search solo vs ~363k under 8-way load).

## Where the engine stands

- **Single-threaded external Elo 2743, 95% CI [2717, 2769]** (600 games vs SF-18
  anchors at 0.3s) — `research/data/elo_history.json`.
- **As actually played (full-width SMP): ~2840.** Lazy SMP measured at **+96
  external Elo [+45, +147]**, which puts the engine at or slightly past the
  chess.com "Hikaru 2820" bot that motivated the whole search push.
- Sacred invariants hold: C eval == Python eval to 0.000000 over 6204 positions,
  perft passes, 77 fast tests green, tactics 24/24.

## Screening: use it, it is 3–10x faster than a gate

```bash
# SPRT screen of a search variant. Variant lives in its own worktree, main stays
# at the baseline, and the run stops as soon as the verdict is decisive.
research/screen.sh <name> 'python3 /path/to/patch.py' [movetime] [maxgames]
```

A clearly-bad change is rejected in **76 games / 5 min**; a mildly-bad one in
~300 games / 10 min; only genuinely ambiguous ones run the full 800. Measured
against the old workflow (patch main, 800 games, revert) this is 3–10x.

**The screen NOMINATES, it never ACCEPTS.** Anything that survives gets a
two-batch confirmation gate on *disjoint* openings, and the confirmation is the
number you report — see the winner's-curse note below.

## The instrument (built s25–s26 — use it, don't rebuild it)

```bash
# external Elo, ~38 min, +-26. Anchors are fixed on purpose; don't change them.
.venv/bin/python -m research.calibrate --games 200 --movetime 0.3 --concurrency 8
.venv/bin/python -m research.calibrate --show

# a strength gate: 400 games in ~25 min. ALWAYS run two batches with disjoint
# --opening-offset (0 and 200) and quote the pooled figure.
.venv/bin/python -m research.match --games 400 --movetime 0.3 --concurrency 8 \
    --opening-offset 0 --book research/books/uho_1000.epd \
    --opponent "cmd:$PWD/.venv/bin/python -m engine.uci" \
    --opponent-cwd research/worktrees/<baseline>

# EVAL changes only: external, paired on openings (self-play does not transfer)
.venv/bin/python -m research.abgate --games 400 --opponent stockfish:2700 \
    --baseline-cwd research/worktrees/<baseline>

# where does strength leak / is a mistake search or eval?
.venv/bin/python -m research.postmortem <pgn> --depth 14 --workers 8
.venv/bin/python -m research.blunders --pgn <pgn> --out research/suites/blunders_v2.epd

# cheap second opinion on any change, esp. depth-sensitive ones:
.venv/bin/python -m research.tactics research/suites/blunders_v1.epd --movetime 1.0
```

Read the **paired** Elo line, not the per-game one.

**Before gating ANY new or changed eval concept, run this — it costs seconds:**

```bash
.venv/bin/python -m research.firing_rate
```

A concept firing under ~2% of the time cannot be resolved by any number of games
this project can afford (the `ocb` modifier fires in **0.0%** of 216 real
positions — that is why it gated as noise for two sessions). A concept with a
non-zero value on the *start position* is measuring something other than its
name: a "trapped pieces" term defined as zero-safe-squares fired 8 times there,
on the undeveloped bishops and rooks, and gated −16.

## The s26 screening run: 22 hypotheses, 1 accepted

Worth knowing before planning more of the same. With SPRT screening making an
attempt cost ~20 minutes instead of ~50, twenty-two ideas were tested in a
single block. **One landed** (LMR for late captures, +9). The rest:

* *Search, 18 tried* — mate-distance pruning, bounded history w/ gravity, double
  extension, recapture extension, SEE-filtered quiescence checks, eval-scaled
  null-move R, reduce-killers-less, ProbCut margin, exempt-checking-quiets from
  LMR, singular extension depth, qsearch delta margin, aspiration width,
  **cutNode** (SF's expected-fail-high flag — we had no such concept, measured
  exactly +0), TT-based ProbCut, two `improving` variants, IIR on shallow TT
  entries (+7, weak, unconfirmed).
* *Eval, 4 tried* — broadened opposite-bishops (−19), winning-difficulty
  modifier v1 and v2, concave mobility (−37).

Three conclusions that should shape the next session:

1. **The search is saturated.** Not "we ran out of ideas" — the standard
   technique list is now *exhaustively* tested, including one structural signal
   (cutNode) that every strong engine uses and that measures zero here. Our
   reduction schedule is at an optimum for depth ~11; importing a stronger
   engine's tuning does not cross that gap.
2. **Eval experiments are confounded by the tuning.** Any change to a concept's
   FUNCTIONAL FORM (concave mobility) is tested against weights Texel-fitted to
   the old form, so the experiment measures the mismatch as much as the idea.
   This project cannot currently afford to re-tune per experiment, so eval work
   is limited to *additive new terms* and *multiplicative modifiers*, not
   reshaping existing ones.
3. **At this screening volume, multiplicity is not optional.** ~20 SPRT screens
   at alpha=0.05 produced ~1 false H1, exactly as expected — the
   winning-difficulty modifier screened **+68 Elo [+29, +109]** and confirmed at
   **+6**. The screen nominates; only a confirmation on disjoint openings decides.

## What is settled (do not re-litigate without new evidence)

- **Move ordering is closed.** Six experiments neutral-or-worse: continuation
  history, history-modulated LMR, root-move ordering, aggressive log-LMR (retested
  s26 at 800 games: +6 [−13,+25]), capture history, and the deferred-ordering
  refactor (declined on a measured ~4.8% ceiling).
- **Eval weights are on a plateau.** Threat weights tested higher (s24, neutral)
  and 30% lower (s26, −3 [−22,+16]). The Texel flywheel converged three sessions
  ago. Only a genuinely NEW concept could move eval, and its ceiling is low:
  **only 18% of real blunders survive 10x thinking time.**
- **Endgame knowledge is not a strength lever.** We play endgames at parity with
  SF-2800 (+0.6 cp/move excess vs +5.2 opening, +4.4 middlegame).
- **The three borderline search features are real**: removing singular extensions
  + null-move R tier + LMP together costs −44 Elo [−64, −24].
- **Speed is capped**: eval_core 29% (the faithfulness tax, and lazy eval is
  off-limits by design), order() 18.4% with ~5% recoverable, the rest diffuse.

## Traps this project has now walked into and out of

1. **Every depth-shaped proxy has lied at least once.** Time-to-depth picks T=16
   for SMP where depth-at-fixed-time picks T=10 (correct); disabling three good
   features searched +3.2 plies deeper and played 44 Elo worse. Only the match
   decides.
2. **At fixed TIME the engine is not deterministic even at one thread** — two
   0.3s searches disagree on the move 18% of the time, a full game replay
   reproduces 71% of its own moves. The byte-identical guarantee is a
   fixed-DEPTH property. Do not build a classifier on a short re-search.
3. **A 0.3s gate is not neutral evidence about depth-sensitive features.**
   Quiescence checks gate as neutral-to-positive to REMOVE at 0.3s but clearly
   want keeping at 1.0s. Every gate here is blitz; the product is not.
4. **Concept attribution names the concept that DIFFERS, not the one that is
   WRONG.** `research.blunders`' culprit table is a place to look, never a
   diagnosis — acting on it directly (threat weights) gated at −3.
5. **Transfer rules.** Search changes deliver ~half their self-play number
   externally (RFP+LMP 0.55, SMP 0.51). Eval changes deliver ~0.
6. **Selection creates winner's curse even when the CI clears zero.** LMR for
   late captures screened at **+24 Elo, 95% CI [+6, +43]** over 754 games — an
   interval excluding zero — and then measured **+4 [−15, +23]** on 800 games of
   *independent* openings. It was picked *because* its screen was the best of
   five, so its screen estimate is biased upward and its interval is not a
   real 95% interval. Never report a screen number; report the confirmation.
7. **A suite screen is trustworthy in one direction only.** The mined
   `blunders_v1.epd` suite is built from positions the BASELINE got wrong, so
   variants get a free decorrelation bonus. Baseline-wins is strong evidence
   (it overcame a handicap); variant-wins is weak — RFP_MARGIN 130 led the suite
   by +8 positions and gated at −4 Elo.

## Next actions

1. **Long TC: the parameters are already validated, a long-TC MATCH is not.**
   s26 screened the four most time-control-sensitive knobs (quiescence check
   depth, LMP_DEPTH, RFP_DEPTH, TT_BITS) on the mined blunder suite at 1.0s and
   3.0s and the baseline beat all four at 3.0s — so the blitz-tuned parameters
   are not mis-set for the product's regime. What remains untested is an actual
   long-TC *match*: the suite is a proxy, and every Elo number in this project is
   from a 0.3s gate. Budget ~2.5h for 2x400 games at 1.0s, concurrency 8.
2. **An unresolved robustness flag** from s24 is still open: an intermittent hang
   at long TC (a 16x scaling rung crashed at game 27/40 and could not be
   reproduced in isolation). ~6000 games at 0.3s this session hit nothing, so if
   it is real it is long-TC specific — item 1 would double as the repro run.
3. **If attempting eval work**, it must be a new CONCEPT (weights are exhausted),
   gated with `research.abgate`, and expect a low ceiling.
4. **Re-calibrate after anything accepted** and let `elo_history.json` accumulate.

## Watch out for

- `research/worktrees/base26` is a worktree at bfc40a9 with a built `.so`, kept
  as the ready-made gate baseline. `git worktree list` to see it.
- `research/graphs/make_graphs.py` is tracked by BOTH this repo and
  mission-control; mission-control's copy is a stale duplicate showing as a
  permanent uncommitted modification there. The fix is `git rm --cached` it in
  mission-control and ignore `projects/conceptchess/` — not done, it is a
  different repo.
- Driving WSL from a Windows-side shell: `&&` chains and `$VAR` inside
  `bash -lc '...'` silently misbehave across the boundary. **Write a script file
  and run it.** This bit twice, once shipping a Python eval the C core did not
  mirror (caught immediately by `eval_check`).

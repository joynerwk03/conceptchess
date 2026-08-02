# Handoff — resuming research on a new machine

Written 2026-08-01, migrating the research loop from macOS to Windows/WSL2.
`research/LOG.md` remains the full record; this file is just "where we are and
what to do next" so a fresh session can resume without replaying history.

## Setup

See the "Setup on a new machine (Linux / Windows-WSL2)" block in `CLAUDE.md`.
The C core is POSIX and builds unchanged in WSL2 — `core/build.sh` picks
`libcengine.so` there and `libcengine.dylib` on macOS. Work on WSL2's own
filesystem (`~/conceptchess`), not `/mnt/c/...`, or match timings get distorted.

## Where the engine stands

- **~2700–2740 external Elo**, single-threaded at 0.3s/move, measured against
  Stockfish with `UCI_LimitStrength` (up from ~2655 before the search push).
  Full-width Lazy SMP is the default in real play and adds roughly +150 on top.
- The search stack added this cycle: reverse futility pruning (+114 self-play),
  internal iterative reduction (+48), probcut (+50), plus late move pruning,
  singular extensions and a null-move R tier (each ~+30, borderline).
  Against the pre-search engine the whole stack is **+200 Elo at 1.5s/move**.
- Sacred invariants all hold: C eval == Python eval to 0.000000 over 6204
  positions, perft passes, 57 fast tests green, tactics 24/24.

## The two lessons that should govern future work

1. **Self-play gates do not measure external strength for EVAL changes.** Two
   eval concepts (backward pawns, connected pawns) gated at +55 and +29 in
   self-play and transferred ~ZERO against Stockfish. Self-play rewards fixing
   *our own lineage's* blind spots, which Stockfish never had. Search changes did
   transfer, because a better move is better against anyone.
   → Gate eval changes against **Stockfish**, not against ourselves.
2. **One batch is never enough.** Repeatedly a first batch looked like +50 Elo
   and an independent second batch collapsed to ~0 (most recently SEE pruning:
   +53 then −21, pooled +17). Always confirm with an independent batch before
   accepting, and prefer the paired/pentanomial estimate.

## Both levers are near their ceiling

- **Eval**: three straight neutral results, and the two "wins" didn't transfer.
- **Search**: after the three big wins, SIX consecutive neutral results
  (razoring, bigger TT, improving-aware RFP, RFP margin sweep, multi-cut,
  correction history, SEE pruning). The major missing techniques are now in.

So further progress probably needs either a sharper measuring instrument (so
small real gains become detectable and accumulable) or a genuinely new
direction — not more of the same tuning.

## In flight / next actions

1. **DONE, just landed** — `research/match.py` upgrade: `--concurrency N`
   (parallel games), correct trinomial + **pentanomial paired** statistics, and
   `--sprt` finally wired up. This attacks the real bottleneck: gates were both
   slow and too noisy to resolve +20–30 Elo.
2. **Verify the harness is unbiased before trusting it.** Run the engine against
   a byte-identical copy of itself; it must score ~50%. A deviation means the
   harness (spawn order, core assignment, colour handling) is favouring a side.
   ```bash
   git worktree add research/worktrees/selfcheck HEAD
   (cd research/worktrees/selfcheck && sh core/build.sh)
   .venv/bin/python -m research.match --games 200 --movetime 0.2 --concurrency 4 \
     --book research/books/uho_1000.epd \
     --opponent "cmd:$PWD/.venv/bin/python -m engine.uci" \
     --opponent-cwd research/worktrees/selfcheck
   ```
   (This was running on the Mac when we migrated; re-run it on the new box, and
   re-tune `--concurrency` to that machine's performance-core count.)
3. **Build `research/calibrate.py` + `research/data/elo_history.json`** so
   external Elo is measured repeatably and tracked over time (the stated goal:
   "provably stronger, tracking Elo over time, grounded in Stockfish matches").
   It should fit a rating by maximum likelihood across several Stockfish anchors
   rather than eyeballing a crossover, and append `{commit, date, tc, opponents,
   W/D/L, elo, ci}` per run. 40 games/anchor gave ±100 Elo — far too loose;
   size it for ±25.
4. **Then resume strength research**, gating eval work against Stockfish.
   Candidate directions not yet tried: move-ordering quality (history/capture
   history), quiescence quality, time management in real play (the analysis
   board thinks indefinitely — gates never measured that), Lazy SMP scaling, and
   hand-built endgame knowledge.

## Watch out for

- Disk on the Mac was at 99%; keep at most one baseline worktree alive and
  remove it after each gate. Consider caching built `.dylib`/`.so` per commit
  instead of keeping whole worktrees.
- **Never rebuild the engine while a gate against it is running** — that
  silently mixed two binaries mid-match once and corrupted a result.
- `research/graphs/make_graphs.py` is tracked by BOTH this repo and
  mission-control (an artifact of moving it); harmless but confusing.

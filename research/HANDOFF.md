# Handoff — where the research loop stands

Updated 2026-08-01 (end of session 25). `research/LOG.md` is the full record;
this file is just "where we are and what to do next" so a fresh session can
resume without replaying history.

## Setup

**The Windows/WSL2 box is now set up and verified** — no migration work left.
Repo lives at `~/mission-control/projects/conceptchess` (WSL2's own ext4, NOT
`/mnt/c/...`, or match timings distort). If you ever need to rebuild it:

```bash
python3 -m venv .venv && .venv/bin/pip install chess pytest matplotlib
sh core/build.sh                                    # -> core/libcengine.so
PYTHONPATH=. .venv/bin/python core/eval_check.py    # must print 0.000000
.venv/bin/python core/perft_check.py                # must print ALL PERFT PASS
.venv/bin/python -m pytest -q -m 'not slow'         # 69 green
```

Stockfish 18 is at `~/.local/bin/stockfish` (installed without root — this box
has no passwordless sudo). Everything finds it via `shutil.which`, but
**`~/.local/bin` is only on PATH in a LOGIN shell** — scripts that shell out
should `export PATH="$HOME/.local/bin:$PATH"` or they will fail to find it.

Hardware: i9-10900K, 10 physical cores / 20 threads, 918 GB free. ~1.7× slower
per core than the old Mac, but parallel gating makes total throughput far higher.
**Use `--concurrency 8`** (validated; see below). Disk is no longer a constraint,
so keeping a baseline worktree alive between gates is fine.

## Where the engine stands

- **External Elo 2743, 95% CI [2717, 2769]** — single-threaded, 0.3s/move, vs
  Stockfish 18 `UCI_LimitStrength` anchors at 2600/2700/2800, 600 games.
  Recorded in `research/data/elo_history.json`. Full-width Lazy SMP is the
  default in real play and adds roughly +150 on top.
- Sacred invariants all hold: C eval == Python eval to 0.000000 over 6204
  positions, perft passes, 69 fast tests green, tactics 24/24.
- Benchmark on this box: avg depth 16.33, 2.62M nps at 2.0s/position.

## The instrument (built in s25 — use it, don't rebuild it)

```bash
# external Elo: ~38 min, gives +-26. Anchors are fixed on purpose; don't change them.
.venv/bin/python -m research.calibrate --games 200 --movetime 0.3 \
    --concurrency 8 --label "what changed"
.venv/bin/python -m research.calibrate --show     # the tracked history

# a strength gate: 400 games in ~25 min
.venv/bin/python -m research.match --games 400 --movetime 0.3 --concurrency 8 \
    --opening-offset 0 --book research/books/uho_1000.epd \
    --opponent "cmd:$PWD/.venv/bin/python -m engine.uci" \
    --opponent-cwd research/worktrees/<baseline>
```

Read the **paired** Elo line, not the per-game one. Run two batches with
disjoint `--opening-offset` ranges (0 and 200) — see lesson 2 below.

## The four lessons that govern this work

1. **Gate eval changes against Stockfish, not against ourselves.** Two eval
   concepts gated at +55 and +29 in self-play and transferred ~ZERO externally.
   Self-play rewards fixing *our own lineage's* blind spots, which Stockfish
   never had. Search changes did transfer — a better move is better against
   anyone.
2. **One batch is never enough.** Capture history went +7 then −17; SEE pruning
   went +53 then −21. Always confirm with an independent batch and quote the
   pooled figure.
3. **Keep the A-vs-identical-A control in mind.** It scores ~51%/+7 Elo on this
   harness. A batch landing there is indistinguishable from the engine playing
   itself — that is the null, not a small win.
4. **Never rebuild the engine while a gate against it is running.** It silently
   mixes two binaries mid-match. (Editing C *source* mid-gate is safe; only
   `core/build.sh` is destructive.)

## Both original levers are at their ceiling

- **Eval**: three straight neutral results in s24, and the two "wins" didn't
  transfer externally.
- **Search**: after RFP (+114), IIR (+48) and probcut (+50), *seven* consecutive
  neutral results — razoring, bigger TT, improving-aware RFP, RFP margin sweep,
  multi-cut, correction history, SEE pruning, and now capture history. The
  standard techniques are all in.
- **Move ordering specifically is a closed door**: five experiments
  (continuation history, history-modulated LMR, root-move ordering, aggressive
  log-LMR, capture history) all neutral-or-worse. Don't reopen it without a
  diagnosis pointing there.

## Next actions

1. **Pick a direction that isn't more of the same tuning.** Untried, roughly by
   expected value:
   - **SMP scaling.** `MAX_THREADS` is hardcoded to 8 in `core/csearch.c:21` and
     `engine/core.py:play_threads()` caps at 8 — this box has 10 physical cores,
     so the analysis board currently leaves two idle. Raising the cap is a small
     change with a real product payoff, and SMP gains are *search* gains, which
     the record says transfer. Measure with benchmark avg-depth at T=8/10/16
     first (SMP-vs-SMP matches contend for cores and gate badly).
   - **Quiescence quality** — never systematically examined.
   - **Hand-built endgame knowledge** — the ROADMAP's unstoppable-passer /
     wrong-bishop items, gated at long TC where they actually fire.
   - **Time management in real play.** The analysis board thinks indefinitely and
     no gate has ever measured that regime.
2. **Re-gate the borderline-ACCEPTED search features** now that 800-game gates
   cost ~50 min: singular extensions (+29, CI [−7,+66]), null-move R tier (+29,
   CI [−6,+64]), LMP (+30, CI [+0,+60]). All three are in the tree on evidence
   that would not survive the current instrument. Converting them to confirmed —
   or removing them — is real progress toward "provably stronger".
3. **Re-calibrate after anything accepted**, and let `elo_history.json` accumulate.

## Watch out for

- `research/graphs/make_graphs.py` is tracked by BOTH this repo and
  mission-control; mission-control's copy is a stale duplicate and shows as a
  permanent uncommitted modification there. Harmless, but the fix is to untrack
  it in mission-control (`git rm --cached`) and ignore `projects/conceptchess/`.
- `research/worktrees/selfcheck` is a worktree at 647ee7d with a built `.so`,
  kept as a ready-made baseline. `git worktree list` to see it.
- When driving WSL from a Windows-side shell, prefer running a script file over
  a long inline `bash -lc '...'` — quoting/expansion of `$VAR` and `&&` chains
  across the boundary silently misbehaved and cost time this session.

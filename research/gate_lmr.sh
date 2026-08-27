#!/bin/bash
# Two-anchor gate for the depth-scaled LMR (deep region only).
#
# Decision rule, FIXED BEFORE THE RUN: merge only if BOTH anchors are positive.
export PATH="/home/joynerwk03/bin:/home/joynerwk03/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/usr/lib/wsl/lib:/mnt/c/Users/joyne/bin:/mnt/c/Program Files/Git/mingw64/bin:/mnt/c/Program Files/Git/usr/local/bin:/mnt/c/Program Files/Git/usr/bin:/mnt/c/Program Files/Git/usr/bin:/mnt/c/Program Files/Git/mingw64/bin:/mnt/c/Program Files/Git/usr/bin:/mnt/c/Users/joyne/bin:/mnt/c/Program Files/WindowsApps/CanonicalGroupLimited.Ubuntu_2404.1.68.0_x64__79rhkp1fndgsc:/mnt/c/Windows/system32:/mnt/c/Windows:/mnt/c/Windows/System32/Wbem:/mnt/c/Windows/System32/WindowsPowerShell/v1.0:/mnt/c/Windows/System32/OpenSSH:/mnt/c/Program Files/Git/cmd:/mnt/c/Program Files/nodejs:/mnt/c/Users/joyne/.local/bin:/mnt/c/Users/joyne/AppData/Local/Microsoft/WindowsApps:/mnt/c/Users/joyne/AppData/Local/Programs/Microsoft VS Code/bin:/mnt/c/Users/joyne/AppData/Local/Programs/Ollama:/mnt/c/Users/joyne/AppData/Roaming/npm:/mnt/c/Program Files/Git/usr/bin/vendor_perl:/mnt/c/Program Files/Git/usr/bin/core_perl"
# One external gate is not an external gate -- cut-node reduction read +28.5 on
# one anchor and +1.8 on a second, and was reverted. If the two disagree in
# sign, a third anchor decides, and the rule for that is likewise fixed first.
#
# Anchor order: stockfish:3000 first. Information per game is highest where the
# score is near 50% (se 10.6 there against 14.1 and 17.1 at 2700/2600).
#
# The candidate is the cwd; the baseline is main, already built and unpatched.
# The worktree is recreated from HEAD so it carries the committed harness --
# an old worktree's copy of abgate.py would gate with the sequential-phase
# defect that produced a phantom +70.7 Elo.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
WT="$CC/research/worktrees/gate_lmr"

cd "$CC"
git worktree remove --force research/worktrees/gate_lmr 2>/dev/null || true
git worktree add research/worktrees/gate_lmr HEAD >/dev/null 2>&1
"$PY" "$R/deepcap.py" "$WT" lmr
cd "$WT"
sh core/build.sh >/dev/null 2>&1
if [ ! -f core/libcengine.so ]; then echo "BUILD FAILED"; exit 1; fi
echo "candidate eval_check: $(PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"
if [ ! -f "$CC/core/libcengine.so" ]; then echo "BASELINE NOT BUILT"; exit 1; fi

for ANCHOR in stockfish:3000 stockfish:2700; do
  echo ""
  echo "=== anchor $ANCHOR ==="
  PYTHONPATH=. "$PY" -m research.abgate \
    --games 600 --opponent "$ANCHOR" --baseline-cwd "$CC" \
    --movetime 0.3 --threads 1 --concurrency 6
done

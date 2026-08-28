#!/bin/bash
# Calibrate the iso-node screen against a configuration whose Elo is known.
#
# rfp25 (RFP_MARGIN 90 -> 25) measured -35.5 and -32.2 on two anchors. It also
# HALVES the tree, so at an equal node budget it buys real extra depth. That
# makes it the sharpest possible test of this instrument:
#
#   * the old FIXED-DEPTH screen saw only the fidelity cost and rated it barely
#     worse (30.5% vs 27.0% >20cp), which is why it survived triage and then
#     lost 33 Elo in games
#   * an iso-node screen that rates it BETTER is measuring the depth gain and
#     missing the cost -- it would be worse than useless and gets thrown away
#   * an iso-node screen that rates it clearly WORSE, despite handing it the
#     depth, is pricing the real trade
#
# A subset by STRIDE, never a block: this data is self-play sampled every few
# plies, so adjacent lines are the same game.
set -eu
CC=/home/joynerwk03/mission-control/projects/conceptchess
R=/home/joynerwk03/ccruns
PY="$CC/.venv/bin/python"
cd "$CC"

awk 'NR%8==1' "$R/ref_partial.jsonl" > "$R/ref_calib.jsonl"
echo "calibration positions: $(wc -l < "$R/ref_calib.jsonl")"

WT="$CC/research/worktrees/rfp25"
git worktree remove --force research/worktrees/rfp25 2>/dev/null || true
git worktree add research/worktrees/rfp25 HEAD >/dev/null 2>&1
sed -i 's/^#define RFP_MARGIN 90/#define RFP_MARGIN 25/' "$WT/core/csearch.c"
grep -q '^#define RFP_MARGIN 25' "$WT/core/csearch.c" || { echo "patch failed"; exit 1; }
(cd "$WT" && sh core/build.sh >/dev/null 2>&1)
[ -f "$WT/core/libcengine.so" ] || { echo "BUILD FAILED"; exit 1; }
echo "rfp25 eval_check: $(cd "$WT" && PYTHONPATH=. "$PY" core/eval_check.py 2>&1 | tail -1)"

echo ""
echo "=== iso-node screen (new instrument) ==="
"$PY" research/screen_isonode.py "$R/ref_calib.jsonl" 9 rfp25="$WT"

echo ""
echo "=== fixed-depth screen (old instrument, same positions) ==="
"$PY" "$R/screen_paired.py" "$R/ref_calib.jsonl" 9 rfp25="$WT"

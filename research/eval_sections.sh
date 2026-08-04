#!/bin/bash
# Per-section share of total search runtime, by cumulative early-return.
#
# Insert `return s;` before section N and measure NPS: that gives the cost of
# "section N and everything after it". Differencing consecutive probes gives each
# section on its own. Cleaner than stubbing sections out individually, which
# failed to compile wherever a section opens with a declaration.
#
# This decides where speed work goes. It has already produced one surprise --
# everything except material is only 28.4% of runtime -- and the answer matters
# because a 96-byte-bigger Board costs 2.3% NPS all by itself, so an incremental
# scheme has to beat that before it is worth anything.
exec > /home/joynerwk03/ccruns/eval_sections.log 2>&1
set -u
CC=/home/joynerwk03/mission-control/projects/conceptchess
PY="$CC/.venv/bin/python"
WT="$CC/research/worktrees/prof3"

nps () { (cd "$1" && PYTHONPATH=. "$PY" -m research.benchmark 2>&1 \
   | grep "avg nps" | sed 's/.*avg nps *//; s/ .*//' | tr -d ','); }

cd "$CC"
git worktree remove --force "$WT" 2>/dev/null || rm -rf "$WT"
git worktree add --detach "$WT" main > /dev/null 2>&1
(cd "$WT" && sh core/build.sh > /dev/null)
BASE=$(nps "$WT")
echo "baseline nps: $BASE"
echo
cp "$WT/core/ceval.c" /tmp/ceval.orig

probe () {   # $1 = marker text, $2 = label
  cp /tmp/ceval.orig "$WT/core/ceval.c"
  python3 - "$WT" "$1" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1]) / "core/ceval.c"
s = p.read_text()
m = sys.argv[2]
if m not in s:
    print("MARKER NOT FOUND: " + m); raise SystemExit(1)
i = s.index(m)
p.write_text(s[:i] + "    if(1) return s;   /* PROBE */\n" + s[i:])
PY
  if [ $? -ne 0 ]; then echo "$2: marker missing"; return; fi
  if (cd "$WT" && sh core/build.sh > /dev/null 2>&1); then
    local N; N=$(nps "$WT")
    awk -v b="$BASE" -v n="$N" -v l="$2" 'BEGIN{
      printf "%-34s nps %8d   this section and after: %5.1f%% of runtime\n", l, n, 100*(n-b)/n }'
  else
    echo "$2: build failed"
  fi
}

probe "    /* piece placement (PST) */"        "from PST onward"
probe "    /* pawn structure */"               "from pawn structure onward"
probe "    /* king safety */"  "from king safety onward"
probe "    /* mobility (safe squares) */"      "from mobility onward"
probe "    /* piece activity */"               "from activity onward"
probe "    /* imbalance and space"             "from imbalance onward"
probe "    /* minor pieces:"                   "from minor pieces onward"
probe "    /* tempo */"                        "from tempo onward"

cp /tmp/ceval.orig "$WT/core/ceval.c"
cd "$CC" && git worktree remove --force "$WT" 2>/dev/null
echo
echo "Difference between consecutive rows = that one section's share."

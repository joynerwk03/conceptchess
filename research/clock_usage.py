"""Clock usage over MANY positions -- the 8-sample version was not measurable.

Eight samples on one position gave mean 1.30x for the baseline, then 0.61x for a
variant, then 1.03x for that same variant minutes later. That spread is noise,
and tuning a constant on it would have been fitting jitter -- the same mistake as
reading one benchmark run for the pawn hash.

20 positions x 4 clocks = 80 samples per build, which is enough for the mean to
mean something.

    clock_usage3.py <engine-tree>
"""
import json
import random
import statistics
import subprocess
import sys
import time

MAIN = "/home/joynerwk03/mission-control/projects/conceptchess"
TREE = sys.argv[1] if len(sys.argv) > 1 else MAIN
CLOCKS = [10000, 5000, 2000, 800]
INC = 100

rows = [json.loads(l) for l in open(MAIN + "/research/data/texel5.jsonl")]
random.Random(31).shuffle(rows)
fens = [r["fen"] for r in rows[:20]]


def ask(p, line):
    p.stdin.write(line + "\n")
    p.stdin.flush()


proc = subprocess.Popen([MAIN + "/.venv/bin/python", "-m", "engine.uci"],
                        cwd=TREE, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        text=True, bufsize=1,
                        env={"PYTHONPATH": TREE, "PATH": "/usr/bin:/bin"})
ask(proc, "uci")
while "uciok" not in proc.stdout.readline():
    pass

ratios = []
for fen in fens:
    for ms in CLOCKS:
        ask(proc, "ucinewgame")
        ask(proc, f"position fen {fen}")
        opt = ms / 1000 / 25 + INC / 1000 * 0.8
        t0 = time.perf_counter()
        ask(proc, f"go wtime {ms} btime {ms} winc {INC} binc {INC}")
        while not proc.stdout.readline().startswith("bestmove"):
            pass
        ratios.append((time.perf_counter() - t0) / opt)

ask(proc, "quit")
proc.wait(timeout=10)

ratios.sort()
n = len(ratios)
print(f"{n} samples ({len(fens)} positions x {len(CLOCKS)} clocks)")
print(f"  mean   {statistics.mean(ratios):.2f}x of the optimum budget")
print(f"  median {ratios[n//2]:.2f}x")
print(f"  p10    {ratios[n//10]:.2f}x     p90 {ratios[9*n//10]:.2f}x")
print(f"  max    {ratios[-1]:.2f}x")
print("  target: mean near 1.0 (spend the budget) with p10..p90 tight")

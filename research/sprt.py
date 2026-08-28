"""Sequential gating: spend games adaptively instead of a fixed 600-slot block.

The instrument problem, stated plainly. A 600-slot paired gate resolves about
+/-26 Elo. The effects still available in this engine are 5 to 15 Elo. So a
single gate structurally cannot see them, which is why nearly every result this
session reads "not distinguishable from zero" and why one change swung 28 Elo on
the SAME anchor between two runs. Pooling fixes it but costs ~4800 slots per
answer.

SPRT spends games where they buy information. A clearly bad change crosses the
lower bound in a few hundred slots; a genuinely close one gets thousands. Same
compute, far more decisions -- and decisions with a stated error rate rather
than an eyeballed interval.

Test: H0 elo <= elo0 against H1 elo >= elo1, with alpha = beta = 0.05.
Log-likelihood ratio under a normal approximation on the PAIRED per-slot
difference, which is what abgate already reports:

    LLR = n / (2 s^2) * ( 2 xbar (m1 - m0) - (m1^2 - m0^2) )

Bounds are log(b/(1-a)) and log((1-b)/a). Elo is converted to score units with
the derivative of the logistic at 50%, 400/ln(10) ~ 173.7 Elo per unit score,
which is the right linearisation for the small effects this is built to detect.

Batches use a FRESH OPENING OFFSET each time, so accumulated slots are distinct
positions rather than repeats -- otherwise the variance estimate is a lie and
the test stops early on nothing.

Usage: sprt.py <candidate_cwd> <baseline_cwd> <anchor> [elo0] [elo1] [maxslots]
"""
import math
import re
import subprocess
import sys

CC = "/home/joynerwk03/mission-control/projects/conceptchess"
PY = CC + "/.venv/bin/python"
ELO_PER_SCORE = 400.0 / math.log(10.0)      # 173.7 at 50%
BATCH = 100                                  # games per arm per batch


def batch(cand, base, anchor, offset, games):
    out = subprocess.run(
        [PY, "-m", "research.abgate", "--games", str(games), "--opponent", anchor,
         "--baseline-cwd", base, "--movetime", "0.3", "--threads", "1",
         "--concurrency", "6", "--opening-offset", str(offset)],
        cwd=cand, capture_output=True, text=True)
    txt = out.stdout
    m = re.search(r"PAIRED external delta over (\d+) shared slots:\s*([-+]?[\d.]+) Elo"
                  r"\s*95% \[([-+]?[\d.]+),\s*([-+]?[\d.]+)\]", txt)
    d = re.search(r"mean per-slot difference ([-+]?[\d.]+)", txt)
    if not m or not d:
        sys.stderr.write(txt[-1500:] + out.stderr[-500:])
        raise RuntimeError("could not parse abgate output")
    n = int(m.group(1))
    xbar = float(d.group(1))
    # recover per-slot sd from the reported 95% Elo interval
    se_elo = (float(m.group(4)) - float(m.group(3))) / (2 * 1.96)
    sd = (se_elo / ELO_PER_SCORE) * math.sqrt(n)
    return n, xbar, sd


def main():
    cand, base, anchor = sys.argv[1], sys.argv[2], sys.argv[3]
    elo0 = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    elo1 = float(sys.argv[5]) if len(sys.argv) > 5 else 5.0
    maxslots = int(sys.argv[6]) if len(sys.argv) > 6 else 6000

    a = b = 0.05
    lo, hi = math.log(b / (1 - a)), math.log((1 - b) / a)
    m0, m1 = elo0 / ELO_PER_SCORE, elo1 / ELO_PER_SCORE
    print(f"SPRT H0 elo<={elo0} vs H1 elo>={elo1}, alpha=beta={a}")
    print(f"bounds [{lo:.3f}, {hi:.3f}], max {maxslots} slots, batch {2*BATCH}\n")

    n_tot, wsum, var_acc, off = 0, 0.0, 0.0, 0
    while n_tot < maxslots:
        n, xbar, sd = batch(cand, base, anchor, off, BATCH)
        off = (off + 991) % 1000                     # fresh openings each batch
        # pooled mean and pooled per-slot variance
        wsum += xbar * n
        var_acc += (sd ** 2) * n
        n_tot += n
        mean = wsum / n_tot
        s2 = var_acc / n_tot
        llr = (n_tot / (2 * s2)) * (2 * mean * (m1 - m0) - (m1 ** 2 - m0 ** 2))
        elo = mean * ELO_PER_SCORE
        se = math.sqrt(s2 / n_tot) * ELO_PER_SCORE
        print(f"  {n_tot:5d} slots  elo {elo:+7.1f} +/-{1.96*se:5.1f}  LLR {llr:+7.3f}",
              flush=True)
        if llr >= hi:
            print(f"\nACCEPT H1: elo >= {elo1} (LLR {llr:.3f} >= {hi:.3f})")
            return
        if llr <= lo:
            print(f"\nACCEPT H0: elo <= {elo0} (LLR {llr:.3f} <= {lo:.3f})")
            return
    print(f"\nINCONCLUSIVE at {n_tot} slots: elo {elo:+.1f} +/-{1.96*se:.1f}, LLR {llr:+.3f}")


if __name__ == "__main__":
    main()

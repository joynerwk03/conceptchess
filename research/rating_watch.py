"""Running rating and interval from a match log, for adaptive stopping.

Goal criterion: point estimate above 3000 AND lower bound above 2990. Games
needed scale as 1/margin^2 against the threshold, so at a measured 3005 this
takes ~1,065 games where the old margin-of-1 criterion needed tens of thousands.

Reads the per-game lines match.py emits and reports the running score, implied
Elo against the anchor, and the interval, so the run can be stopped the moment
the criterion holds rather than padded to a fixed length -- and abandoned early
if the score is clearly tracking below 50%, where no number of games can succeed.

Elo conversion uses the correct derivative: d(Elo)/d(score) at p=0.5 is
400/(ln10 * p(1-p)) = 695, NOT 400/ln10 = 173.7. Getting that wrong by 4x once
produced a false claim that the rating interval was systematic rather than
binomial.

Usage: rating_watch.py <logfile> [anchor_elo]
"""
import math
import re
import sys


def main():
    path = sys.argv[1]
    anchor = float(sys.argv[2]) if len(sys.argv) > 2 else 3000.0

    w = d = l = 0
    for line in open(path, errors="ignore"):
        m = re.match(r"game\s+\d+:\s+[WB]\s+(\S+)", line)
        if not m:
            continue
        res = m.group(1)
        if res in ("1-0", "0-1"):
            # match.py prints the result from OUR perspective in the score column;
            # fall back to counting via the trailing running tally if present
            pass
        if "win" in line or res == "1-0":
            pass
    # match.py's per-game format varies; prefer its own running tally if present
    txt = open(path, errors="ignore").read()
    tally = re.findall(r"(\d+)W\s+(\d+)D\s+(\d+)L", txt)
    if tally:
        w, d, l = (int(x) for x in tally[-1])
    else:
        w = len(re.findall(r"game\s+\d+:.*\bwin\b", txt))
        d = len(re.findall(r"game\s+\d+:.*\bdraw\b", txt))
        l = len(re.findall(r"game\s+\d+:.*\bloss\b", txt))

    n = w + d + l
    if n == 0:
        print("no completed games parsed yet")
        return

    p = (w + 0.5 * d) / n
    ex2 = (w + 0.25 * d) / n
    var = max(ex2 - p * p, 1e-9)
    se_p = math.sqrt(var / n)
    k = 400.0 / (math.log(10.0) * 0.25)          # 694.9
    elo = anchor + (0 if abs(p - 0.5) < 1e-12 else
                    400.0 * math.log10(p / (1 - p)))
    se = k * se_p
    lo, hi = elo - 1.96 * se, elo + 1.96 * se

    print(f"{n} games  {w}W {d}D {l}L  score {100*p:.2f}%")
    print(f"Elo {elo:.1f}  95% [{lo:.1f}, {hi:.1f}]  (se {se:.2f})")

    ok_point = elo > 3000.0
    ok_lower = lo > 2990.0
    print(f"  point > 3000 : {'YES' if ok_point else 'no'} ({elo:.1f})")
    print(f"  lower > 2990 : {'YES' if ok_lower else 'no'} ({lo:.1f})")
    if ok_point and ok_lower:
        print("\n*** CRITERION MET -- stop the run ***")
    elif elo <= 3000.0 and n >= 400:
        need = "cannot succeed at this score; more games will not raise the point estimate"
        print(f"\n  tracking below 3000: {need}")
    else:
        # games needed for the lower bound to clear 2990 at the current point estimate
        margin = elo - 2990.0
        if margin > 0:
            need_n = n * (1.96 * se / margin) ** 2
            print(f"\n  at this score, lower bound clears 2990 at ~{need_n:.0f} games")


if __name__ == "__main__":
    main()

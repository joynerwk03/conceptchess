"""Pool the two independent external gates on the phase3 stack.

Two batches, different opening offsets, so independent samples of the same
quantity. Inverse-variance weighted, which for near-equal variances is close to
a straight mean but is the right estimator regardless.
"""
import math

BATCHES = [
    ("batch 1 (offset 0)",   15.0, -4.1, 34.1),
    ("batch 2 (offset 500)", 10.6, -8.6, 29.8),
]

print(f"{'':24s} {'delta':>8s} {'95% CI':>18s} {'sigma':>8s}")
print("-" * 62)
num = den = 0.0
for name, d, lo, hi in BATCHES:
    sigma = (hi - lo) / (2 * 1.96)
    num += d / sigma ** 2
    den += 1 / sigma ** 2
    print(f"{name:24s} {d:+8.1f}  [{lo:+6.1f}, {hi:+6.1f}] {sigma:8.2f}")

pooled = num / den
sig = math.sqrt(1 / den)
lo, hi = pooled - 1.96 * sig, pooled + 1.96 * sig
z = pooled / sig
# one-sided: the hypothesis was directional and registered before batch 1 ran
p_one = 0.5 * math.erfc(z / math.sqrt(2))

print("-" * 62)
print(f"{'POOLED (3200 slots)':24s} {pooled:+8.1f}  [{lo:+6.1f}, {hi:+6.1f}] {sig:8.2f}")
print()
print(f"z = {z:.2f}    one-sided p = {p_one:.3f}    two-sided p = {2*p_one:.3f}")
print(f"P(true effect > 0) = {(1 - p_one) * 100:.1f}%")
print()
print("The pre-registered prediction was +15.0 (2.683% loss at ~8.5 Elo/%, minus")
print("~8 for the 3.9% nps cost). Observed pooled: "
      f"{pooled:+.1f}.")

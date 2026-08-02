"""The paired external-delta estimator.

research.abgate is what makes EVAL work gateable again (self-play Elo does not
transfer for eval changes -- s24 measured that directly), so its arithmetic gets
the same treatment as the calibration fit: checked against cases with a known
answer, including the one property the whole design exists for -- that pairing
on openings is tighter than differencing two independent runs.
"""

import random

import pytest

from research.abgate import _elo_slope, paired_delta


class TestSlope:
    def test_slope_is_flattest_at_the_extremes(self):
        assert _elo_slope(0.5) < _elo_slope(0.2)
        assert _elo_slope(0.5) < _elo_slope(0.8)

    def test_slope_is_symmetric(self):
        assert pytest.approx(_elo_slope(0.3), rel=1e-9) == _elo_slope(0.7)


class TestPairedDelta:
    def test_identical_runs_give_zero(self):
        a = {i: (i % 3) / 2.0 for i in range(40)}
        delta, ci, mean_d, n, p_a, p_b = paired_delta(a, dict(a))
        assert delta == pytest.approx(0.0, abs=1e-9)
        assert mean_d == pytest.approx(0.0, abs=1e-9)
        assert ci[0] == pytest.approx(0.0, abs=1e-9)
        assert ci[1] == pytest.approx(0.0, abs=1e-9)
        assert n == 40

    def test_uniformly_better_b_is_positive_and_clears_zero(self):
        a = {i: 0.0 for i in range(60)}
        b = {i: 0.5 for i in range(60)}
        delta, ci, mean_d, n, p_a, p_b = paired_delta(a, b)
        assert delta > 0
        assert mean_d == pytest.approx(0.5)
        assert p_a == 0.0 and p_b == 0.5
        assert ci[0] > 0                    # zero variance in the difference

    def test_uniformly_worse_b_is_negative(self):
        a = {i: 1.0 for i in range(60)}
        b = {i: 0.5 for i in range(60)}
        delta, _, _, _, _, _ = paired_delta(a, b)
        assert delta < 0

    def test_only_shared_slots_are_used(self):
        a = {0: 1.0, 1: 0.0, 2: 0.5}
        b = {1: 0.0, 2: 0.5, 9: 1.0}
        _, _, _, n, _, _ = paired_delta(a, b)
        assert n == 2

    def test_too_few_slots_returns_none(self):
        assert paired_delta({0: 1.0}, {0: 1.0}) is None

    def test_pairing_beats_differencing_independent_runs(self):
        """The whole point: shared openings cancel opening difficulty.

        Simulate slots with a large per-opening effect and a small, real
        improvement for B. Paired analysis should give a much tighter interval
        than treating the two runs as independent samples.
        """
        rng = random.Random(4)
        n = 300
        a, b, b_indep = {}, {}, {}
        for i in range(n):
            difficulty = rng.choice([0.0, 0.5, 1.0])   # opening effect, shared
            a[i] = difficulty
            # B wins one extra half-point on a tenth of the slots
            b[i] = min(1.0, difficulty + (0.5 if rng.random() < 0.10 else 0.0))
            # an INDEPENDENT run of B re-rolls the opening effect
            d2 = rng.choice([0.0, 0.5, 1.0])
            b_indep[i] = min(1.0, d2 + (0.5 if rng.random() < 0.10 else 0.0))

        _, ci_paired, _, _, _, _ = paired_delta(a, b)
        _, ci_unpaired, _, _, _, _ = paired_delta(a, b_indep)
        width_paired = ci_paired[1] - ci_paired[0]
        width_unpaired = ci_unpaired[1] - ci_unpaired[0]
        assert width_paired < width_unpaired

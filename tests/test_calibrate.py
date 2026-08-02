"""The external-Elo estimator, tested the way an estimator should be.

`research.calibrate` turns a handful of Stockfish anchor results into ONE
number that the whole research loop now leans on ("is the engine actually
stronger?"), so the fit itself has to be trustworthy before its output means
anything. These tests simulate matches from a KNOWN rating and check that the
fit recovers it and that the reported interval really covers it -- no engine and
no Stockfish needed, so they run in the fast suite.
"""

import random

import pytest

from research.calibrate import (_pair_counts, _probs, bootstrap_ci, fit,
                                loglik, profile_ci)

ANCHORS = [2600, 2700, 2800, 2900]
TRUE_RATING = 2712.0
TRUE_DRAW_ELO = 200.0


def simulate(rating, draw_elo, anchors, games, rng):
    """Trinomial samples from the model itself -- [(anchor, w, d, l), ...]."""
    out = []
    for anchor in anchors:
        pw, pd, _ = _probs(rating - anchor, draw_elo)
        w = d = l = 0
        for _ in range(games):
            u = rng.random()
            if u < pw:
                w += 1
            elif u < pw + pd:
                d += 1
            else:
                l += 1
        out.append((anchor, w, d, l))
    return out


class TestModel:
    def test_probabilities_are_a_distribution(self):
        for delta in (-600, -100, 0, 100, 600):
            for de in (1, 100, 300):
                pw, pd, pl = _probs(delta, de)
                assert pytest.approx(pw + pd + pl, abs=1e-9) == 1.0
                assert min(pw, pd, pl) > 0

    def test_equal_ratings_are_symmetric(self):
        pw, _, pl = _probs(0, 250)
        assert pytest.approx(pw, abs=1e-12) == pl

    def test_stronger_side_scores_more(self):
        prev = 0.0
        for delta in (-400, -200, 0, 200, 400):
            pw, pd, _ = _probs(delta, 200)
            score = pw + 0.5 * pd
            assert score > prev
            prev = score

    def test_more_draw_elo_means_more_draws(self):
        assert _probs(0, 400)[1] > _probs(0, 100)[1]


class TestFit:
    def test_recovers_a_known_rating(self):
        rng = random.Random(7)
        results = simulate(TRUE_RATING, TRUE_DRAW_ELO, ANCHORS, 400, rng)
        rating, draw_elo, _ = fit(results)
        assert abs(rating - TRUE_RATING) < 25
        assert abs(draw_elo - TRUE_DRAW_ELO) < 60

    def test_recovers_a_rating_outside_the_anchor_bracket(self):
        """Extrapolation still works, but is the case to distrust in practice."""
        rng = random.Random(3)
        results = simulate(2450.0, TRUE_DRAW_ELO, ANCHORS, 400, rng)
        rating, _, _ = fit(results)
        assert abs(rating - 2450.0) < 40

    def test_the_fit_is_the_likelihood_maximum(self):
        rng = random.Random(5)
        results = simulate(TRUE_RATING, TRUE_DRAW_ELO, ANCHORS, 200, rng)
        rating, draw_elo, ll = fit(results)
        for dr in (-30, -5, 5, 30):
            assert loglik(rating + dr, draw_elo, results) <= ll + 1e-6

    def test_more_games_tighten_the_interval(self):
        rng = random.Random(13)
        small = simulate(TRUE_RATING, TRUE_DRAW_ELO, ANCHORS, 40, rng)
        big = simulate(TRUE_RATING, TRUE_DRAW_ELO, ANCHORS, 400, rng)
        r_s, _, ll_s = fit(small)
        r_b, _, ll_b = fit(big)
        w_s = lambda ci: ci[1] - ci[0]
        assert w_s(profile_ci(big, r_b, ll_b)) < w_s(profile_ci(small, r_s, ll_s))

    def test_forty_games_per_anchor_is_too_loose_for_small_effects(self):
        """The LOG's complaint, made concrete: the old 40-game ladder cannot
        resolve the +20-30 Elo effects the gates now chase."""
        rng = random.Random(17)
        results = simulate(TRUE_RATING, TRUE_DRAW_ELO, ANCHORS, 40, rng)
        rating, _, ll = fit(results)
        lo, hi = profile_ci(results, rating, ll)
        assert (hi - lo) / 2 > 50


@pytest.mark.slow
class TestCoverage:
    def test_profile_interval_covers_the_truth(self):
        """A 95% interval has to actually cover ~95% of the time."""
        rng = random.Random(23)
        trials, covered = 40, 0
        for _ in range(trials):
            results = simulate(TRUE_RATING, TRUE_DRAW_ELO, ANCHORS, 150, rng)
            rating, _, ll = fit(results)
            lo, hi = profile_ci(results, rating, ll)
            covered += lo <= TRUE_RATING <= hi
        assert covered >= trials - 6      # allow sampling noise at 40 trials


class TestPairing:
    def test_pair_counts_sum_the_two_colour_swapped_games(self):
        class FakeResult:
            games = 6
            scores = {0: 1.0, 1: 0.0,      # win + loss  -> (1, 0, 1)
                      2: 0.5, 3: 0.5,      # two draws   -> (0, 2, 0)
                      4: 1.0, 5: 1.0}      # two wins    -> (2, 0, 0)

        assert _pair_counts(FakeResult()) == [(1, 0, 1), (0, 2, 0), (2, 0, 0)]

    def test_incomplete_pairs_are_dropped(self):
        class FakeResult:
            games = 4
            scores = {0: 1.0, 1: 0.0, 2: 0.5}     # game 3 never finished

        assert _pair_counts(FakeResult()) == [(1, 0, 1)]

    def test_bootstrap_interval_brackets_the_point_estimate(self):
        rng = random.Random(29)
        results = simulate(TRUE_RATING, TRUE_DRAW_ELO, ANCHORS, 200, rng)
        rating, draw_elo, _ = fit(results)
        # rebuild plausible pairs from the counts: the estimator only needs
        # per-pair (w, d, l) triples that sum to the same totals.
        pair_counts = {}
        for anchor, w, d, l in results:
            pairs, games = [], [1] * w + [0.5] * d + [0] * l
            rng.shuffle(games)
            for i in range(0, len(games) - 1, 2):
                a, b = games[i], games[i + 1]
                pw = sum(1 for s in (a, b) if s == 1)
                pl = sum(1 for s in (a, b) if s == 0)
                pairs.append((pw, 2 - pw - pl, pl))
            pair_counts[anchor] = pairs
        lo, hi = bootstrap_ci(pair_counts, draw_elo, iters=120, seed=1)
        assert lo < rating < hi

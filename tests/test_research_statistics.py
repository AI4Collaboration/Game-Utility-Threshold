"""Mathematical edge cases and finite distributions, without paid model calls."""

from dataclasses import replace
from itertools import product
import json
from math import comb, factorial, log, sqrt

import pytest

from utility_threshold.research_statistics import (
    EpisodeObservation, Interval, hoeffding_interval, hoeffding_required_episodes,
    infer_threshold, paired_episode_score, summarize_cell, wilson_interval,
)


def make_cell(cell_id, x, score, *, n=1000, family_size=3, alpha=0.05):
    return summarize_cell(cell_id, x,
        [EpisodeObservation(f"{cell_id}-{i}", score) for i in range(n)],
        expected_episodes=n, family_size=family_size, alpha=alpha)


def test_fractional_scores_are_one_episode_each_and_use_bounded_mean_formula():
    scores = [paired_episode_score(0, 0), paired_episode_score(0, 1), paired_episode_score(1, 1)]
    assert scores == [0, 0.5, 1]
    scores *= 100
    interval = hoeffding_interval(scores)
    radius = sqrt(log(40) / 600)
    assert interval.lower == pytest.approx(0.5 - radius)
    assert interval.upper == pytest.approx(0.5 + radius)
    assert interval.lower < 0.5 - sqrt(log(40) / 1200)  # Not 600 independent players.


@pytest.mark.parametrize("scores", [[], [0] * 100, [1] * 100, [0.5] * 100])
def test_empty_or_unanimous_samples_have_nonzero_uncertainty(scores):
    interval = hoeffding_interval(scores)
    assert interval.lower < interval.upper
    assert 0 <= interval.lower <= interval.upper <= 1
    if not scores:
        assert interval == Interval(0, 1)


def test_bonferroni_widens_bands_and_planning_bound_is_sufficient():
    pointwise = hoeffding_interval([0.5] * 100)
    simultaneous = hoeffding_interval([0.5] * 100, family_size=60)
    assert simultaneous.lower < pointwise.lower < pointwise.upper < simultaneous.upper
    n = hoeffding_required_episodes(0.1, family_size=60)
    assert sqrt(log(2 * 60 / 0.05) / (2 * n)) <= 0.1
    assert sqrt(log(2 * 60 / 0.05) / (2 * (n - 1))) > 0.1


def test_finite_sample_bernoulli_coverage_by_enumeration():
    # Exact binomial sums, not a stochastic simulation or a nominal-coverage claim.
    for n in (1, 2, 5, 10, 20, 40):
        bands = [hoeffding_interval([1] * k + [0] * (n - k), alpha=0.1) for k in range(n + 1)]
        for p in (0, 0.01, 0.1, 0.3, 0.5, 0.8, 0.99, 1):
            coverage = sum(comb(n, k) * p**k * (1 - p)**(n - k)
                           for k, band in enumerate(bands) if band.lower <= p <= band.upper)
            assert coverage >= 0.9 - 1e-12


def test_finite_sample_fractional_episode_coverage_by_exact_multinomial_sum():
    n = 10
    probabilities = (0.2, 0.5, 0.3)  # Episode outcomes 0, 0.5, 1, with mean 0.55.
    true_mean = 0.55
    coverage = 0.0
    for zeros in range(n + 1):
        for halves in range(n - zeros + 1):
            ones = n - zeros - halves
            band = hoeffding_interval([0] * zeros + [0.5] * halves + [1] * ones, alpha=0.1)
            mass = factorial(n) / (factorial(zeros) * factorial(halves) * factorial(ones))
            mass *= probabilities[0]**zeros * probabilities[1]**halves * probabilities[2]**ones
            if band.lower <= true_mean <= band.upper:
                coverage += mass
    assert coverage >= 0.9


def test_invalid_missing_and_unrecorded_are_separate_and_never_zero_imputed():
    cell = summarize_cell("c", 2, [EpisodeObservation("1", 1), EpisodeObservation("2", 0.5),
        EpisodeObservation("3", None, "invalid"), EpisodeObservation("4", None, "missing")],
        expected_episodes=6, family_size=1)
    assert (cell.recorded_episodes, cell.valid_episodes, cell.invalid_episodes,
            cell.missing_episodes, cell.unrecorded_episodes, cell.unavailable_episodes) == (4, 2, 1, 1, 2, 4)
    assert cell.valid_mean == 0.75
    assert cell.completion_mean_bounds == Interval(0.25, 5.5 / 6)
    assert cell.valid_episodes + cell.unavailable_episodes == cell.expected_episodes
    assert cell.valid_episodes + cell.invalid_episodes + cell.missing_episodes == cell.recorded_episodes
    json.dumps(cell.as_dict(), allow_nan=False)


def test_completion_envelope_encloses_every_possible_filling_without_missing_at_random():
    known = [0, 0.5, 1] * 30
    cell = summarize_cell("c", 0, [EpisodeObservation(str(i), y) for i, y in enumerate(known)],
                          expected_episodes=len(known) + 3, family_size=3)
    for filling in product((0, 0.5, 1), repeat=3):
        completed_band = hoeffding_interval(known + list(filling), family_size=3)
        assert cell.completion_interval.lower <= completed_band.lower + 1e-15
        assert cell.completion_interval.upper >= completed_band.upper - 1e-15


def test_all_missing_has_no_mean_and_full_uncertainty():
    cell = summarize_cell("empty", 0, [], expected_episodes=100)
    assert cell.valid_mean is None
    assert cell.unrecorded_episodes == 100
    assert cell.completion_mean_bounds == cell.completion_interval == Interval(0, 1)
    result = infer_threshold([cell], direction="increasing")
    assert result["status"] == "unresolved"
    assert result["empirical_pattern"]["label"] == "no_data"
    assert result["never_reaches_target_possible"] is True
    json.dumps(result, allow_nan=False)


def test_complete_data_has_identical_valid_and_completion_intervals():
    cell = make_cell("c", 0, 0.5)
    assert cell.valid_interval == cell.completion_interval
    assert cell.completion_mean_bounds == Interval(0.5, 0.5)


def test_wilson_known_values_empty_counts_and_unanimity():
    band = wilson_interval(5, 10)
    assert band.lower == pytest.approx(0.236593090512564)
    assert band.upper == pytest.approx(0.763406909487436)
    assert wilson_interval(0, 10).upper == pytest.approx(0.277532799862889)
    assert wilson_interval(0, 10).lower == 0
    assert wilson_interval(10, 10).upper == 1
    assert wilson_interval(0, 0) == Interval(0, 1)
    assert wilson_interval(5, 10, family_size=10).lower < band.lower


def test_absent_single_crossing_assumption_abstains_even_for_clean_data():
    result = infer_threshold([make_cell("low", 0, 0), make_cell("high", 1, 1)])
    assert result["status"] == "assumption_not_declared"
    assert result["point_estimate"] is None
    assert result["location_envelope"] is None
    assert result["candidate_first_crossing_cells"] == []
    assert [cell["relation_to_target"] for cell in result["grid"]] == ["below", "above"]


def test_confidence_inversion_keeps_grid_uncertainty_and_no_midpoint():
    # Include uncertain cells between confidently low and high settings.
    cells = [make_cell("lo", 1, 0, family_size=4), make_cell("u1", 3, 0.5, family_size=4),
             make_cell("u2", 8, 0.5, family_size=4), make_cell("hi", 12, 1, family_size=4)]
    result = infer_threshold(reversed(cells), direction="increasing")
    assert result["status"] == "bounded"
    assert result["location_envelope"]["lower"] == 1
    assert result["location_envelope"]["upper"] == 12
    assert [candidate["cell_id"] for candidate in result["candidate_first_crossing_cells"]] == ["u1", "u2", "hi"]
    assert result["target_compatible_cell_ids"] == ["u1", "u2"]
    assert result["point_estimate"] is None
    assert not result["left_censoring_possible"]
    assert not result["right_censoring_possible"]


@pytest.mark.parametrize("direction,score,status", [
    ("increasing", 0, "right_censored"), ("increasing", 1, "left_censored"),
    ("decreasing", 0, "left_censored"), ("decreasing", 1, "right_censored"),
])
def test_flat_unanimous_curves_are_censored_not_given_fake_thresholds(direction, score, status):
    result = infer_threshold([make_cell("a", 0, score), make_cell("b", 1, score)], direction=direction)
    assert result["status"] == status
    assert result["empirical_pattern"]["label"] == "all_flat"
    assert result["point_estimate"] is None


def test_observed_target_plateau_is_unresolved_and_exact_ties_are_retained():
    result = infer_threshold([make_cell("a", 0, 0.5), make_cell("b", 1, 0.5)], direction="increasing")
    assert result["status"] == "unresolved"
    assert result["empirical_pattern"]["exact_target_tie_cells"] == ["a", "b"]
    assert result["left_censoring_possible"] and result["right_censoring_possible"]


def test_reversed_and_multiple_confident_crossings_are_rejected_under_declared_assumption():
    reverse = [make_cell("a", 0, 1), make_cell("b", 1, 0)]
    result = infer_threshold(reverse, direction="increasing")
    assert result["status"] == "incompatible_with_assumption"
    assert "observed_crossing_reverses_declared_direction" in result["flags"]
    assert infer_threshold(reverse, direction="decreasing")["status"] == "bounded"
    multiple = [make_cell("a", 0, 0), make_cell("b", 1, 1), make_cell("c", 2, 0)]
    result = infer_threshold(multiple, direction="increasing")
    assert result["status"] == "incompatible_with_assumption"
    assert result["empirical_pattern"]["label"] == "multiple_crossings"


def test_noisy_reversal_is_flagged_but_not_automatically_rejected():
    cells = [make_cell("a", 0, 0.6, n=10), make_cell("b", 1, 0.4, n=10)]
    result = infer_threshold(cells, direction="increasing")
    assert result["status"] == "unresolved"
    assert "observed_crossing_reverses_declared_direction" in result["flags"]


def test_sign_single_crossing_does_not_impose_global_monotonicity_of_means():
    cells = [make_cell("a", 0, 0), make_cell("b", 1, 1), make_cell("c", 2, 0.8)]
    result = infer_threshold(cells, direction="increasing")
    assert result["status"] == "bounded"
    assert [row["cell_id"] for row in result["candidate_first_crossing_cells"]] == ["b"]


def test_exact_interval_boundary_obeys_explicit_target_reached_convention():
    # Exercise inversion algebra at exact band endpoints independently of rounding
    # in a specific sample. The first band permits equality; the second forces it.
    cell = make_cell("a", 0, 0.5, family_size=1)
    permits = replace(cell, completion_interval=Interval(0.4, 0.5))
    forces = replace(cell, completion_interval=Interval(0.5, 0.6))
    assert infer_threshold([permits], direction="increasing")["status"] == "unresolved"
    assert infer_threshold([forces], direction="increasing")["status"] == "left_censored"
    assert infer_threshold([permits], direction="decreasing")["status"] == "left_censored"


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.1, 1.1, True, "0.5", None])
def test_invalid_scores_rejected(bad):
    with pytest.raises(ValueError):
        EpisodeObservation("episode", bad)
    with pytest.raises(ValueError):
        hoeffding_interval([bad])


@pytest.mark.parametrize("alpha", [0, 1, -0.1, float("nan"), float("inf"), True])
def test_invalid_alpha_rejected(alpha):
    with pytest.raises(ValueError):
        hoeffding_interval([0.5], alpha=alpha)


@pytest.mark.parametrize("family", [0, -1, 1.5, True])
def test_invalid_family_size_rejected(family):
    with pytest.raises(ValueError):
        hoeffding_interval([0.5], family_size=family)


def test_invalid_observation_states_and_pair_components_rejected():
    with pytest.raises(ValueError):
        EpisodeObservation("e", 0, "invalid")
    with pytest.raises(ValueError):
        EpisodeObservation("e", None, "refusal")
    with pytest.raises(ValueError):
        EpisodeObservation(" ", 0)
    with pytest.raises(ValueError):
        paired_episode_score(0.5, 1)
    with pytest.raises(ValueError):
        paired_episode_score(None, 1)


def test_counts_and_duplicate_episode_ids_rejected():
    observation = EpisodeObservation("e", 1)
    with pytest.raises(ValueError, match="duplicate"):
        summarize_cell("c", 0, [observation, observation], expected_episodes=2)
    with pytest.raises(ValueError, match="exceed"):
        summarize_cell("c", 0, [observation, observation], expected_episodes=1)
    for bad in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            summarize_cell("c", 0, [], expected_episodes=bad)
    with pytest.raises(ValueError):
        summarize_cell("c", float("nan"), [], expected_episodes=1)
    with pytest.raises(ValueError):
        summarize_cell("c", 0, [0], expected_episodes=1)


def test_incompatible_curve_metadata_and_duplicated_cells_rejected():
    a, b = make_cell("a", 0, 0), make_cell("b", 1, 1)
    with pytest.raises(ValueError, match="duplicate cell_id"):
        infer_threshold([a, a])
    with pytest.raises(ValueError, match="unique"):
        infer_threshold([a, replace(b, x=0)])
    with pytest.raises(ValueError, match="same alpha"):
        infer_threshold([a, replace(b, alpha=0.1)])
    with pytest.raises(ValueError, match="smaller"):
        infer_threshold([replace(a, family_size=1), replace(b, family_size=1)])
    for target in (0, 1, float("nan")):
        with pytest.raises(ValueError):
            infer_threshold([a, b], target=target)
    with pytest.raises(ValueError):
        infer_threshold([a, b], direction="auto")
    with pytest.raises(ValueError):
        infer_threshold([])


def test_wilson_rejects_fractional_or_impossible_counts():
    for successes, trials in ((0.5, 10), (11, 10), (-1, 10), (True, 10), (0, -1)):
        with pytest.raises(ValueError):
            wilson_interval(successes, trials)


def test_extreme_valid_alpha_keeps_hoeffding_finite():
    band = hoeffding_interval([0.5] * 10, alpha=1e-300, family_size=100)
    assert band == Interval(0, 1)
    with pytest.raises(ValueError):
        hoeffding_required_episodes(1e-300)

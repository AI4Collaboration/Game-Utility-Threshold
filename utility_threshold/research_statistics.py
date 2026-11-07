"""Conservative, dependency-free inference for predeclared research cells.

The independent unit is an episode, not a player in a paired episode.  See
``docs/research/statistical-methods.md`` for estimands, assumptions, and proofs.
No function below establishes independence or validates a sampling protocol.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil, fsum, isfinite, log, sqrt
from numbers import Real
from statistics import NormalDist
from typing import Iterable, Literal


def _number(value: Real, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite number, not a boolean or string")
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _integer(value: int, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _probability(value: Real, name: str) -> float:
    result = _number(value, name)
    if not 0 <= result <= 1:
        raise ValueError(f"{name} must be in [0, 1]")
    return result


def _design(alpha: float, family_size: int) -> tuple[float, int]:
    alpha = _number(alpha, "alpha")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be strictly between 0 and 1")
    return alpha, _integer(family_size, "family_size", 1)


def _identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


@dataclass(frozen=True)
class Interval:
    lower: float
    upper: float

    def __post_init__(self) -> None:
        lower = _probability(self.lower, "lower")
        upper = _probability(self.upper, "upper")
        if lower > upper:
            raise ValueError("lower must not exceed upper")

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EpisodeObservation:
    """One independent episode; unavailable outcomes never receive a zero score.

    ``valid`` requires a score in [0, 1]. ``invalid`` means a received response
    could not be scored; ``missing`` means no usable response was obtained.
    Both unavailable statuses require ``score=None``. Keep detailed per-call
    reasons and component outcomes in the immutable collection records.
    """

    episode_id: str
    score: float | None
    status: Literal["valid", "invalid", "missing"] = "valid"

    def __post_init__(self) -> None:
        _identifier(self.episode_id, "episode_id")
        if self.status not in ("valid", "invalid", "missing"):
            raise ValueError("status must be valid, invalid, or missing")
        if self.status == "valid":
            _probability(self.score, "score")
        elif self.score is not None:
            raise ValueError("invalid/missing episodes must have score=None")


@dataclass(frozen=True)
class CellSummary:
    cell_id: str
    x: float
    expected_episodes: int
    recorded_episodes: int
    valid_episodes: int
    invalid_episodes: int
    missing_episodes: int
    unrecorded_episodes: int
    unavailable_episodes: int
    valid_score_sum: float
    valid_mean: float | None
    valid_interval: Interval
    completion_mean_bounds: Interval
    completion_interval: Interval
    alpha: float
    family_size: int
    interval_method: str = "hoeffding_bonferroni"
    independent_unit: str = "episode"

    def as_dict(self) -> dict:
        """Return JSON-compatible data; no missing value is encoded as NaN."""
        return asdict(self)


def paired_episode_score(row_score: float, column_score: float) -> float:
    """Average two binary player outcomes into ONE independent episode score.

    Both component actions must have been valid. If either cannot be scored,
    retain an unavailable EpisodeObservation instead of imputing a defection.
    """
    row = _probability(row_score, "row_score")
    column = _probability(column_score, "column_score")
    if row not in (0, 1) or column not in (0, 1):
        raise ValueError("paired component outcomes must be binary 0 or 1")
    return (row + column) / 2


def _radius(n: int, alpha: float, family_size: int) -> float:
    # Separate logarithms avoid overflow in 2 * family_size / alpha.
    return sqrt((log(2) + log(family_size) - log(alpha)) / (2 * n))


def hoeffding_interval(
    scores: Iterable[float], *, alpha: float = 0.05, family_size: int = 1
) -> Interval:
    """Two-sided finite-sample interval for independent [0, 1] scores.

    ``family_size`` is the number of mean intervals declared before collection,
    including other planned panels/models/roles, not just populated cells.
    An empty cell returns [0, 1]. Fixed sample size/no outcome-based stopping
    is required. Unanimous finite samples still have nonzero uncertainty.
    """
    alpha, family_size = _design(alpha, family_size)
    values = [_probability(value, "score") for value in scores]
    if not values:
        return Interval(0.0, 1.0)
    mean = fsum(values) / len(values)
    radius = _radius(len(values), alpha, family_size)
    return Interval(max(0.0, mean - radius), min(1.0, mean + radius))


def hoeffding_required_episodes(
    half_width: float, *, alpha: float = 0.05, family_size: int = 1
) -> int:
    """Worst-case fixed complete episodes per cell for the requested radius.

    This is a precision bound, not power for a particular scientific effect;
    incomplete episodes can make the completion envelope wider still.
    """
    alpha, family_size = _design(alpha, family_size)
    width = _probability(half_width, "half_width")
    if width == 0:
        raise ValueError("half_width must be greater than zero")
    if width**2 == 0:
        raise ValueError("requested precision exceeds floating-point range")
    required = (log(2) + log(family_size) - log(alpha)) / (2 * width**2)
    if not isfinite(required):
        raise ValueError("requested precision exceeds floating-point range")
    return max(1, ceil(required))


def wilson_interval(
    successes: int, trials: int, *, alpha: float = 0.05, family_size: int = 1
) -> Interval:
    """Approximate Wilson score interval for independent Bernoulli trials.

    Never pass fractional episode scores or count both players as independent
    trials. Bonferroni-adjusting Wilson does not give an exact finite-sample
    coverage guarantee; primary threshold inference uses Hoeffding instead.
    """
    alpha, family_size = _design(alpha, family_size)
    n = _integer(trials, "trials")
    successes = _integer(successes, "successes")
    if successes > n:
        raise ValueError("successes must not exceed trials")
    if n == 0:
        return Interval(0.0, 1.0)
    tail = alpha / family_size / 2
    if tail == 0:
        raise ValueError("adjusted alpha is below floating-point precision")
    # Lower-tail inverse avoids subtracting tiny probabilities from 1.
    z_squared = NormalDist().inv_cdf(tail) ** 2
    p = successes / n
    denominator = 1 + z_squared / n
    center = (p + z_squared / (2 * n)) / denominator
    radius = sqrt(z_squared * (p * (1 - p) / n + z_squared / (4 * n**2))) / denominator
    lower = 0.0 if successes == 0 else max(0.0, center - radius)
    upper = 1.0 if successes == n else min(1.0, center + radius)
    return Interval(lower, upper)


def summarize_cell(
    cell_id: str,
    x: float,
    observations: Iterable[EpisodeObservation],
    *,
    expected_episodes: int,
    alpha: float = 0.05,
    family_size: int = 1,
) -> CellSummary:
    """Summarize one immutable design cell without concealing unavailable data.

    ``valid_interval`` describes valid-response scores under the conditional
    sampling assumptions in the methods document. ``completion_interval``
    encloses the Hoeffding interval for EVERY [0, 1] assignment to unavailable
    scheduled outcomes; it makes no missing-at-random assumption. Its population
    interpretation additionally requires well-defined independent hypothetical
    complete outcomes. Invalid responses are not silently called cooperation or
    defection. Unrecorded scheduled episodes are counted separately.
    """
    _identifier(cell_id, "cell_id")
    x = _number(x, "x")
    expected = _integer(expected_episodes, "expected_episodes", 1)
    alpha, family_size = _design(alpha, family_size)
    rows = list(observations)
    if any(not isinstance(row, EpisodeObservation) for row in rows):
        raise ValueError("observations must contain EpisodeObservation objects")
    if len(rows) > expected:
        raise ValueError("recorded episodes exceed the predeclared expected count")
    if len({row.episode_id for row in rows}) != len(rows):
        raise ValueError("duplicate episode_id within cell; retries are not new episodes")
    valid = [float(row.score) for row in rows if row.status == "valid"]
    invalid = sum(row.status == "invalid" for row in rows)
    missing = sum(row.status == "missing" for row in rows)
    unrecorded = expected - len(rows)
    unavailable = expected - len(valid)
    total = fsum(valid)
    completion_bounds = Interval(total / expected, (total + unavailable) / expected)
    radius = _radius(expected, alpha, family_size)
    completion_interval = Interval(
        max(0.0, completion_bounds.lower - radius),
        min(1.0, completion_bounds.upper + radius),
    )
    return CellSummary(
        cell_id=cell_id, x=x, expected_episodes=expected, recorded_episodes=len(rows),
        valid_episodes=len(valid), invalid_episodes=invalid, missing_episodes=missing,
        unrecorded_episodes=unrecorded, unavailable_episodes=unavailable,
        valid_score_sum=total, valid_mean=total / len(valid) if valid else None,
        valid_interval=hoeffding_interval(valid, alpha=alpha, family_size=family_size),
        completion_mean_bounds=completion_bounds, completion_interval=completion_interval,
        alpha=alpha, family_size=family_size,
    )


def _empirical_pattern(cells: list[CellSummary], target: float) -> dict:
    observed = [(cell.x, cell.valid_mean) for cell in cells if cell.valid_mean is not None]
    means = [mean for _, mean in observed]
    strict_signs = [1 if mean > target else -1 for mean in means if mean != target]
    changes = [(a, b) for a, b in zip(strict_signs, strict_signs[1:]) if a != b]
    if not means:
        label = "no_data"
    elif len(means) == 1:
        label = "one_observed_cell"
    elif all(mean == means[0] for mean in means):
        label = "all_flat"
    elif len(changes) > 1:
        label = "multiple_crossings"
    elif changes:
        label = "increasing_crossing" if changes[0] == (-1, 1) else "decreasing_crossing"
    else:
        label = "no_strict_crossing"
    return {
        "label": label,
        "strict_sign_changes": len(changes),
        "exact_target_tie_cells": [cell.cell_id for cell in cells if cell.valid_mean == target],
        "observed_cells": len(means),
        "interpretation": "Descriptive valid-response means; sampling noise and missingness can change this pattern.",
    }


def infer_threshold(
    cells: Iterable[CellSummary], *, target: float = 0.5,
    direction: Literal["increasing", "decreasing"] | None = None,
) -> dict:
    """Invert simultaneous completion bands on one ordered experimental axis.

    Passing ``direction`` DECLARES a scientific single-crossing assumption; it
    is never learned from the sample. Increasing means strictly below target
    before crossing and at/above thereafter; decreasing reverses the inequalities.
    A constant curve or a target plateau is allowed; a unique equality point is
    not assumed. Without this declaration, return grid evidence and abstain from
    assigning a threshold. No interpolation, fitted logistic curve, or midpoint
    is fabricated. See the methods document for coverage and censoring semantics.
    """
    target = _probability(target, "target")
    if not 0 < target < 1:
        raise ValueError("threshold target must be strictly between 0 and 1")
    if direction not in (None, "increasing", "decreasing"):
        raise ValueError("direction must be None, increasing, or decreasing")
    rows = list(cells)
    if not rows or any(not isinstance(cell, CellSummary) for cell in rows):
        raise ValueError("provide at least one CellSummary")
    for cell in rows:
        _identifier(cell.cell_id, "cell_id")
        _number(cell.x, "x")
        _design(cell.alpha, cell.family_size)
        if cell.interval_method != "hoeffding_bonferroni" or cell.independent_unit != "episode":
            raise ValueError("threshold inference requires episode-level Hoeffding summaries")
    if len({cell.cell_id for cell in rows}) != len(rows):
        raise ValueError("duplicate cell_id")
    if len({cell.x for cell in rows}) != len(rows):
        raise ValueError("x values must be unique within a threshold curve; split other conditions")
    if len({(cell.alpha, cell.family_size) for cell in rows}) != 1:
        raise ValueError("all cells must use the same alpha and predeclared family_size")
    if rows[0].family_size < len(rows):
        raise ValueError("family_size is smaller than the number of cells being inverted")
    rows.sort(key=lambda cell: cell.x)
    pattern = _empirical_pattern(rows, target)
    flags = []
    if any(cell.unavailable_episodes for cell in rows):
        flags.append("unavailable_outcomes_widen_completion_bands")
    if pattern["label"] == "all_flat":
        flags.append("observed_flat_curve_is_not_evidence_of_population_flatness")
    if pattern["label"] == "multiple_crossings":
        flags.append("observed_multiple_crossings")
    if pattern["exact_target_tie_cells"]:
        flags.append("observed_exact_target_ties_do_not_prove_population_equality")
    grid = []
    for cell in rows:
        band = cell.completion_interval
        relation = "below" if band.upper < target else "above" if band.lower > target else "target_compatible"
        grid.append({"cell_id": cell.cell_id, "x": cell.x, "valid_mean": cell.valid_mean,
                     "completion_interval": band.as_dict(), "relation_to_target": relation})
    result = {
        "status": "assumption_not_declared", "target": target, "direction": direction,
        "confidence_level": 1 - rows[0].alpha, "family_size": rows[0].family_size,
        "method": "inversion_of_simultaneous_hoeffding_completion_bands",
        "empirical_pattern": pattern, "grid": grid, "flags": flags,
        "target_compatible_cell_ids": [cell["cell_id"] for cell in grid if cell["relation_to_target"] == "target_compatible"],
        "candidate_first_crossing_cells": [], "location_envelope": None,
        "left_censoring_possible": None, "right_censoring_possible": None,
        "never_reaches_target_possible": None, "point_estimate": None,
        "assumptions": [
            "Fixed predeclared cells, episode counts, target, and comparison family; no outcome-based stopping.",
            "Independent episodes within each cell; dependence between cells is allowed by Bonferroni.",
            "Unavailable scores admit bounded hypothetical complete outcomes; failure rates remain separate outcomes.",
        ],
    }
    if direction is None:
        result["flags"].append("single_crossing_not_assumed_no_threshold_inference")
        return result
    result["assumptions"].append(
        f"A {direction} single crossing of the POPULATION mean at the specified target is assumed over the axis; not established by these data."
    )
    opposite = "decreasing_crossing" if direction == "increasing" else "increasing_crossing"
    if pattern["label"] == opposite:
        result["flags"].append("observed_crossing_reverses_declared_direction")
    # For increasing, a pre-crossing mean is < target, and a reached mean >=
    # target. For decreasing the inequalities reverse. Exact boundary equality
    # is explicitly counted as reaching the target, never broken at random.
    before_possible = [
        cell.completion_interval.lower < target if direction == "increasing"
        else cell.completion_interval.upper > target for cell in rows
    ]
    after_possible = [
        cell.completion_interval.upper >= target if direction == "increasing"
        else cell.completion_interval.lower <= target for cell in rows
    ]
    candidates = [k for k in range(len(rows) + 1)
                  if all(before_possible[:k]) and all(after_possible[k:])]
    if not candidates:
        result["status"] = "incompatible_with_assumption"
        result["flags"].append("no_single_crossing_pattern_is_compatible_with_simultaneous_bands")
        return result
    first, last = candidates[0], candidates[-1]
    left, right = first == 0, last == len(rows)
    result.update({
        "candidate_first_crossing_cells": [
            {"cell_id": rows[k].cell_id, "x": rows[k].x} for k in candidates if k < len(rows)
        ],
        "location_envelope": {
            "lower": None if left else rows[first - 1].x,
            "upper": None if right else rows[last].x,
            "finite_endpoints_inclusive": True,
            "interpretation": "Conservative location enclosure conditional on the stated single-crossing and sampling assumptions; includes grid uncertainty.",
        },
        "left_censoring_possible": left, "right_censoring_possible": right,
        "never_reaches_target_possible": right,
    })
    if left and right:
        result["status"] = "unresolved"
    elif left:
        result["status"] = "left_censored"
    elif right:
        result["status"] = "right_censored"
    else:
        result["status"] = "bounded"
    result["flags"].append("no_location_inside_an_untested_grid_gap_is_identified")
    return result

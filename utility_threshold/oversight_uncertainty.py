"""Private priorities and bounded-error certificates for the base oversight game.

This module implements the *algebra* in :mod:`utility_threshold.core` with
exact rational arithmetic. Finite floats are interpreted by their decimal
text (``0.15`` means exactly 3/20); returned Fractions must be retained when
checking a switching boundary. See ``docs/research/oversight-bounds.md`` for
the information structure, proofs, numerical convention, and limitations.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from fractions import Fraction
from math import isfinite
from typing import Literal, Sequence

from .core import Action, GameParams, GameState

Number = int | float | Fraction | Decimal
_COST_SLOPE = Fraction(1, 2)
_DETECTION_SLOPE = Fraction(3, 20)
_SATURATION = 1 / _DETECTION_SLOPE


def _fraction(value: Number, name: str) -> Fraction:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number, not a boolean")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError(f"{name} must be finite")
        return Fraction(value)
    if isinstance(value, float) and isfinite(value):
        return Fraction(str(value))
    raise ValueError(f"{name} must be a finite int, float, Decimal, or Fraction")


def _nonnegative(value: Number, name: str) -> Fraction:
    result = _fraction(value, name)
    if result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def _probability(value: Number, name: str) -> Fraction:
    result = _fraction(value, name)
    if not 0 <= result <= 1:
        raise ValueError(f"{name} must lie in [0, 1]")
    return result


def _json_value(value: object) -> object:
    """Exact, JSON-safe certificates; no Infinity and no silent rounding."""
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    return value


class _Certificate:
    def to_dict(self) -> dict[str, object]:
        """Return exact numerator/denominator pairs suitable for JSON records."""
        return _json_value(self)  # type: ignore[return-value]


@dataclass(frozen=True)
class PrivateValue(_Certificate):
    """One privately known resource value and its ex ante probability."""

    v: Number
    probability: Number

    def __post_init__(self) -> None:
        object.__setattr__(self, "v", _nonnegative(self.v, "v"))
        object.__setattr__(self, "probability", _probability(self.probability, "probability"))


@dataclass(frozen=True)
class TypeDistribution(_Certificate):
    """A finite, exactly normalized prior; no fitted or implicit probabilities.

    Use ``from_weights`` to explicitly normalize counts or relative weights.
    Zero-probability entries are permitted and reported but do not affect risk.
    """

    types: tuple[PrivateValue, ...]

    def __post_init__(self) -> None:
        types = tuple(self.types)
        if not types or not all(isinstance(item, PrivateValue) for item in types):
            raise ValueError("types must be a nonempty sequence of PrivateValue entries")
        if sum((item.probability for item in types), Fraction()) != 1:
            raise ValueError("type probabilities must sum exactly to 1; use from_weights explicitly")
        object.__setattr__(self, "types", types)

    @classmethod
    def from_weights(cls, values_and_weights: Sequence[tuple[Number, Number]]) -> TypeDistribution:
        """Normalize declared non-negative weights, retaining exact ratios."""
        items = tuple((v, _nonnegative(weight, "weight")) for v, weight in values_and_weights)
        total = sum((weight for _, weight in items), Fraction())
        if total <= 0:
            raise ValueError("weights must have positive total")
        return cls(tuple(PrivateValue(v, weight / total) for v, weight in items))


@dataclass(frozen=True)
class _Params:
    R: Fraction
    g: Fraction
    p: Fraction
    L: Fraction
    cost_scale: Fraction


def _params(prm: GameParams) -> _Params:
    if not isinstance(prm, GameParams):
        raise ValueError("prm must be a GameParams instance")
    return _Params(
        _fraction(prm.R, "R"), _fraction(prm.g, "g"), _fraction(prm.p, "p"),
        _fraction(prm.L, "L"), _fraction(prm.defense_cost_scale, "defense_cost_scale"),
    )


def _detection(defense: Fraction) -> Fraction:
    return min(Fraction(1), _DETECTION_SLOPE * defense)


def _threshold(v: Fraction, prm: _Params) -> Fraction:
    benefit = v * prm.R - prm.g
    if benefit <= 0:
        return Fraction()
    if benefit <= _COST_SLOPE * _SATURATION + prm.p:
        return benefit / (_COST_SLOPE + _DETECTION_SLOPE * prm.p)
    return (benefit - prm.p) / _COST_SLOPE


@dataclass(frozen=True)
class TypeResponse(_Certificate):
    v: Fraction
    probability: Fraction
    action: Action
    attack_utility: Fraction
    cooperate_utility: Fraction
    safety_margin: Fraction
    human_utility: Fraction


@dataclass(frozen=True)
class DefenseEvaluation(_Certificate):
    defense: Fraction
    detection_probability: Fraction
    attack_probability: Fraction
    unblocked_attack_probability: Fraction
    expected_human_utility: Fraction
    responses: tuple[TypeResponse, ...]


def _evaluate(distribution: TypeDistribution, defense: Fraction, prm: _Params) -> DefenseEvaluation:
    q = _detection(defense)
    defense_cost = prm.cost_scale * defense**2
    responses = []
    for item in distribution.types:
        attack = item.v * prm.R - _COST_SLOPE * defense - q * prm.p
        margin = prm.g - attack
        action: Action = "COOPERATE" if margin >= 0 else "ATTACK"
        human = -defense_cost - ((1 - q) * prm.L if action == "ATTACK" else 0)
        responses.append(TypeResponse(
            item.v, item.probability, action, attack, prm.g, margin, human,
        ))
    attack_probability = sum(
        (item.probability for item in responses if item.action == "ATTACK"), Fraction(),
    )
    welfare = sum((item.probability * item.human_utility for item in responses), Fraction())
    return DefenseEvaluation(
        defense, q, attack_probability, (1 - q) * attack_probability, welfare, tuple(responses),
    )


def evaluate_private_values(
    distribution: TypeDistribution, defense: Number, prm: GameParams,
) -> DefenseEvaluation:
    """Evaluate one public defense; each type knows its own v and maximizes utility.

    Ties select cooperation. Attack probability is over private types, *not*
    a predicted frequency for language models or a confidence interval.
    """
    if not isinstance(distribution, TypeDistribution):
        raise ValueError("distribution must be a TypeDistribution")
    return _evaluate(distribution, _nonnegative(defense, "defense"), _params(prm))


@dataclass(frozen=True)
class TypeThreshold(_Certificate):
    v: Fraction
    probability: Fraction
    defense: Fraction
    within_budget: bool


@dataclass(frozen=True)
class DefenseCandidate(_Certificate):
    evaluation: DefenseEvaluation
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PrivateDefenseSolution(_Certificate):
    best: DefenseEvaluation
    max_defense: Fraction
    type_thresholds: tuple[TypeThreshold, ...]
    candidates: tuple[DefenseCandidate, ...]
    optimality_basis: str
    leader_tie_break: str = "maximum welfare, then minimum attack probability, then minimum defense"
    follower_tie_break: str = "COOPERATE"

    @property
    def defense(self) -> Fraction:
        return self.best.defense

    @property
    def attack_probability(self) -> Fraction:
        return self.best.attack_probability

    @property
    def expected_human_utility(self) -> Fraction:
        return self.best.expected_human_utility


def solve_private_value_defense(
    distribution: TypeDistribution, prm: GameParams, max_defense: Number = 10,
) -> PrivateDefenseSolution:
    """Globally maximize expected human utility in the declared exact model.

    Every private-type threshold and the detection kink partitions the defense
    interval. On an interval with attacking mass A below detection saturation,
    the only interior candidate is 0.15*L*A/(2*cost_scale). At each threshold
    the human payoff jumps upward or stays fixed because ties cooperate.
    Endpoints therefore dominate any omitted one-sided supremum.
    """
    if not isinstance(distribution, TypeDistribution):
        raise ValueError("distribution must be a TypeDistribution")
    exact = _params(prm)
    maximum = _nonnegative(max_defense, "max_defense")
    thresholds = tuple(
        TypeThreshold(item.v, item.probability, root, root <= maximum)
        for item in distribution.types
        for root in [_threshold(item.v, exact)]
    )
    reasons: dict[Fraction, set[str]] = {}

    def add(defense: Fraction, reason: str) -> None:
        reasons.setdefault(defense, set()).add(reason)

    add(Fraction(), "lower_endpoint")
    add(maximum, "upper_endpoint")
    if _SATURATION <= maximum:
        add(_SATURATION, "detection_saturation")
    for index, threshold in enumerate(thresholds):
        if threshold.within_budget:
            add(threshold.defense, f"type_threshold_{index}")
    boundaries = sorted(reasons)
    if exact.cost_scale > 0:
        for left, right in zip(boundaries, boundaries[1:]):
            middle = (left + right) / 2
            if middle >= _SATURATION:
                continue
            active_mass = _evaluate(distribution, middle, exact).attack_probability
            stationary = _DETECTION_SLOPE * exact.L * active_mass / (2 * exact.cost_scale)
            if left < stationary < right:
                add(stationary, "active_type_mass_stationary_point")
    candidates = tuple(
        DefenseCandidate(_evaluate(distribution, defense, exact), tuple(sorted(reason)))
        for defense, reason in sorted(reasons.items())
    )
    best = max(
        (candidate.evaluation for candidate in candidates),
        key=lambda evaluation: (
            evaluation.expected_human_utility, -evaluation.attack_probability, -evaluation.defense,
        ),
    )
    return PrivateDefenseSolution(
        best, maximum, thresholds, candidates,
        "endpoints, every type threshold, detection saturation, and each constant-active-mass "
        "interval's quadratic stationary point; exact rational arithmetic",
    )


@dataclass(frozen=True)
class AttackRiskSolution(_Certificate):
    feasible: bool
    target_attack_probability: Fraction
    max_defense: Fraction
    minimum_defense: Fraction | None
    evaluation: DefenseEvaluation | None
    best_achievable_attack_probability: Fraction
    budget_evaluation: DefenseEvaluation
    reason: str


def minimum_defense_for_attack_probability(
    distribution: TypeDistribution, prm: GameParams, target_attack_probability: Number,
    max_defense: Number = 10,
) -> AttackRiskSolution:
    """Find the least defense with model attack probability <= the target.

    This is a chance requirement under the supplied prior, not a worst-case
    guarantee over unknown priors. The exact type thresholds suffice because
    attack probability is a nonincreasing step function.
    """
    if not isinstance(distribution, TypeDistribution):
        raise ValueError("distribution must be a TypeDistribution")
    exact = _params(prm)
    maximum = _nonnegative(max_defense, "max_defense")
    target = _probability(target_attack_probability, "target_attack_probability")
    budget = _evaluate(distribution, maximum, exact)
    if budget.attack_probability > target:
        return AttackRiskSolution(
            False, target, maximum, None, None, budget.attack_probability, budget,
            "The target is infeasible within the declared defense budget and type distribution.",
        )
    defenses = {Fraction(), maximum}
    for item in distribution.types:
        root = _threshold(item.v, exact)
        if root <= maximum:
            defenses.add(root)
    for defense in sorted(defenses):
        evaluation = _evaluate(distribution, defense, exact)
        if evaluation.attack_probability <= target:
            return AttackRiskSolution(
                True, target, maximum, defense, evaluation, budget.attack_probability, budget,
                "Minimum feasible defense among exact type thresholds and the lower endpoint.",
            )
    raise AssertionError("feasible budget must occur among evaluated defenses")


@dataclass(frozen=True)
class ClosedInterval(_Certificate):
    lower: Number
    upper: Number

    def __post_init__(self) -> None:
        lower, upper = _fraction(self.lower, "lower"), _fraction(self.upper, "upper")
        if lower > upper:
            raise ValueError("interval lower must not exceed upper")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)


def _check_interval(interval: ClosedInterval, name: str, lower: int | None = None,
                    upper: int | None = None, strictly_positive: bool = False) -> None:
    if not isinstance(interval, ClosedInterval):
        raise ValueError(f"{name} must be a ClosedInterval")
    if lower is not None and interval.lower < lower:
        raise ValueError(f"{name} must be at least {lower}")
    if upper is not None and interval.upper > upper:
        raise ValueError(f"{name} must be at most {upper}")
    if strictly_positive and interval.lower <= 0:
        raise ValueError(f"{name} must be strictly positive")


@dataclass(frozen=True)
class MarginUncertainty(_Certificate):
    """A Cartesian product of intervals, not a probability distribution.

    Every combination is admitted. This declares no statistical independence;
    correlated or constrained parameters need their actual joint set instead.
    """

    v: ClosedInterval
    R: ClosedInterval
    g: ClosedInterval
    penalty: ClosedInterval
    detection: ClosedInterval
    attack_cost: ClosedInterval

    def __post_init__(self) -> None:
        _check_interval(self.v, "v", lower=0)
        _check_interval(self.R, "R", strictly_positive=True)
        _check_interval(self.g, "g")
        _check_interval(self.penalty, "penalty", lower=0)
        _check_interval(self.detection, "detection", lower=0, upper=1)
        _check_interval(self.attack_cost, "attack_cost", lower=0)


@dataclass(frozen=True)
class RobustMarginCertificate(_Certificate):
    minimum_margin: Fraction
    maximum_margin: Fraction
    required_margin: Fraction
    uniformly_cooperative: bool
    required_margin_certified: bool
    uniformly_attacking: bool
    worst_case_cooperate_utility: Fraction
    worst_case_attack_utility: Fraction
    maximin_action: Action
    minimum_witness: dict[str, Fraction]
    maximum_witness: dict[str, Fraction]
    uncertainty_model: str
    follower_tie_break: str = "COOPERATE"


def worst_case_margin(
    uncertainty: MarginUncertainty, required_margin: Number = 0,
) -> RobustMarginCertificate:
    """Exact margin extrema on the declared box, with attained witnesses.

    A maximin action compares each action's worst utility. It is reported
    separately and does NOT certify that cooperation wins at every point.
    """
    if not isinstance(uncertainty, MarginUncertainty):
        raise ValueError("uncertainty must be MarginUncertainty")
    u = uncertainty
    required = _nonnegative(required_margin, "required_margin")
    minimum = u.g.lower + u.attack_cost.lower + u.detection.lower * u.penalty.lower - u.v.upper * u.R.upper
    maximum = u.g.upper + u.attack_cost.upper + u.detection.upper * u.penalty.upper - u.v.lower * u.R.lower
    cooperate_worst = u.g.lower
    attack_worst = u.v.lower * u.R.lower - u.attack_cost.upper - u.detection.upper * u.penalty.upper
    return RobustMarginCertificate(
        minimum, maximum, required, minimum >= 0, minimum >= required, maximum < 0,
        cooperate_worst, attack_worst,
        "COOPERATE" if cooperate_worst >= attack_worst else "ATTACK",
        {"v": u.v.upper, "R": u.R.upper, "g": u.g.lower, "penalty": u.penalty.lower,
         "detection": u.detection.lower, "attack_cost": u.attack_cost.lower},
        {"v": u.v.lower, "R": u.R.lower, "g": u.g.upper, "penalty": u.penalty.upper,
         "detection": u.detection.upper, "attack_cost": u.attack_cost.upper},
        "Cartesian product of the six declared intervals",
    )


def worst_case_margin_at_defense(
    *, v: ClosedInterval, R: ClosedInterval, g: ClosedInterval,
    penalty: ClosedInterval, defense: ClosedInterval,
    detection_slope: ClosedInterval = ClosedInterval(Fraction(3, 20), Fraction(3, 20)),
    attack_cost_slope: ClosedInterval = ClosedInterval(Fraction(1, 2), Fraction(1, 2)),
    required_margin: Number = 0,
) -> RobustMarginCertificate:
    """Exact bounds with c=a*d and q=min(1,b*d), including uncertain execution.

    The independent inputs are v,R,g,penalty,defense,a,b. Cost and detection
    share defense and must not be independently varied. Monotonicity ensures
    both extrema occur at the same lower/upper defense endpoint, making these
    bounds exact for this specified dependence as well as for the simpler box.
    """
    _check_interval(defense, "defense", lower=0)
    _check_interval(detection_slope, "detection_slope", lower=0)
    _check_interval(attack_cost_slope, "attack_cost_slope", lower=0)
    q = ClosedInterval(
        min(1, detection_slope.lower * defense.lower),
        min(1, detection_slope.upper * defense.upper),
    )
    c = ClosedInterval(attack_cost_slope.lower * defense.lower, attack_cost_slope.upper * defense.upper)
    base = worst_case_margin(MarginUncertainty(v, R, g, penalty, q, c), required_margin)
    return RobustMarginCertificate(
        base.minimum_margin, base.maximum_margin, base.required_margin,
        base.uniformly_cooperative, base.required_margin_certified, base.uniformly_attacking,
        base.worst_case_cooperate_utility, base.worst_case_attack_utility, base.maximin_action,
        {**base.minimum_witness, "defense": defense.lower, "detection_slope": detection_slope.lower,
         "attack_cost_slope": attack_cost_slope.lower},
        {**base.maximum_witness, "defense": defense.upper, "detection_slope": detection_slope.upper,
         "attack_cost_slope": attack_cost_slope.upper},
        "Independent input intervals with shared defense: c=a*d and q=min(1,b*d)",
    )


@dataclass(frozen=True)
class ParameterDistance(_Certificate):
    parameter: str
    adverse_direction: Literal["increase", "decrease"]
    distance_to_tie: Fraction | None
    boundary_value: Fraction | None
    attack_possible_beyond_boundary: bool
    explanation: str


@dataclass(frozen=True)
class FragilityReport(_Certificate):
    nominal_margin: Fraction
    distances: tuple[ParameterDistance, ...]
    interpretation: str = (
        "One parameter changes at a time; distance is to a tie, where cooperation still wins. "
        "A strict crossing is required for attack. Distances have different units and are not additive."
    )


def one_parameter_distances(state: GameState, prm: GameParams) -> FragilityReport:
    """Exact adverse distance to m=0 for an initially cooperative state.

    Detection and attack-cost entries treat those quantities as independently
    perturbed calibration values. The defense entry instead moves both using
    the built-in response functions. None means no reachable tie in the domain;
    an already tied parameter with zero effect has distance zero but cannot cross.
    """
    if not isinstance(state, GameState):
        raise ValueError("state must be a GameState")
    exact = _params(prm)
    v, defense = _nonnegative(state.v, "v"), _nonnegative(state.d, "d")
    q, cost = _detection(defense), _COST_SLOPE * defense
    margin = exact.g + cost + q * exact.p - v * exact.R
    if margin < 0:
        raise ValueError("one_parameter_distances requires a nominally cooperative state")
    records: list[ParameterDistance] = []

    def increasing(parameter: str, current: Fraction, coefficient: Fraction) -> None:
        if coefficient == 0:
            records.append(ParameterDistance(
                parameter, "increase", Fraction() if margin == 0 else None,
                current if margin == 0 else None, False, "No effect on margin.",
            ))
        else:
            distance = margin / coefficient
            records.append(ParameterDistance(parameter, "increase", distance, current + distance, True,
                                             "Any strict increase beyond this boundary makes the margin negative."))

    def decreasing(parameter: str, current: Fraction, coefficient: Fraction,
                   nonnegative_domain: bool = True) -> None:
        if coefficient == 0:
            records.append(ParameterDistance(
                parameter, "decrease", Fraction() if margin == 0 else None,
                current if margin == 0 else None, False, "No effect on margin.",
            ))
            return
        distance = margin / coefficient
        boundary = current - distance
        if nonnegative_domain and boundary < 0:
            records.append(ParameterDistance(parameter, "decrease", None, None, False,
                                             "The margin stays positive throughout the non-negative domain."))
            return
        can_cross = not nonnegative_domain or boundary > 0
        records.append(ParameterDistance(parameter, "decrease", distance, boundary, can_cross,
                                         "A strict decrease past this boundary causes attack." if can_cross else
                                         "The tie is at zero; attack cannot be reached in the admissible domain."))

    increasing("v", v, exact.R)
    increasing("R", exact.R, v)
    decreasing("g", exact.g, Fraction(1), nonnegative_domain=False)
    decreasing("penalty", exact.p, q)
    decreasing("detection", q, exact.p)
    decreasing("attack_cost", cost, Fraction(1))
    benefit = v * exact.R - exact.g
    if benefit < 0:
        records.append(ParameterDistance("defense", "decrease", None, None, False,
                                         "Cooperation is strictly preferred even at zero defense."))
    else:
        root = _threshold(v, exact)
        records.append(ParameterDistance("defense", "decrease", defense - root, root, root > 0,
                                         "Both attack cost and detection change together; a strict decrease past "
                                         "the threshold causes attack." if root > 0 else
                                         "The tie is at zero defense; no admissible decrease can cause attack."))
    return FragilityReport(margin, tuple(records))

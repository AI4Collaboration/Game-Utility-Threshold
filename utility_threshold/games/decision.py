"""Risk-, ambiguity-, and uncertainty-aware strategic decision analysis."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, isclose, log
from types import MappingProxyType
from typing import Mapping, Protocol

from .base import Payoff, Player, Profile, SymmetricTwoByTwoGame
from .beliefs import ActionBelief
from .uncertainty import DiscreteDistribution, PayoffState, UncertainPayoffGame, WeightedOutcome


@dataclass(frozen=True)
class StateActionBelief:
    """Possibly correlated belief over payoff state and opponent action."""

    state_ids: tuple[str, ...]
    actions: tuple[str, ...]
    probabilities: Mapping[tuple[str, str], float]

    def __post_init__(self) -> None:
        expected = {(state_id, action) for state_id in self.state_ids for action in self.actions}
        if set(self.probabilities) != expected:
            raise ValueError("joint belief must contain every state-action pair")
        if any(value < 0 or value > 1 for value in self.probabilities.values()):
            raise ValueError("joint probabilities must be between zero and one")
        if not isclose(sum(self.probabilities.values()), 1.0, abs_tol=1e-9):
            raise ValueError("joint probabilities must sum to one")
        object.__setattr__(self, "probabilities", MappingProxyType(dict(self.probabilities)))

    @classmethod
    def independent(cls, game: UncertainPayoffGame, action_belief: ActionBelief) -> StateActionBelief:
        if action_belief.actions != game.actions:
            raise ValueError("action belief must use the uncertain game's actions")
        return cls(
            state_ids=tuple(state.state_id for state in game.states),
            actions=game.actions,
            probabilities={
                (state.state_id, action): state.probability * action_belief.probability(action)
                for state in game.states
                for action in game.actions
            },
        )

    def probability(self, state_id: str, action: str) -> float:
        try:
            return self.probabilities[(state_id, action)]
        except KeyError as exc:
            raise ValueError(f"unknown state-action pair {(state_id, action)!r}") from exc

    def state_marginal(self) -> dict[str, float]:
        return {
            state_id: sum(self.probability(state_id, action) for action in self.actions)
            for state_id in self.state_ids
        }

    def action_marginal(self) -> ActionBelief:
        return ActionBelief(
            self.actions,
            {
                action: sum(self.probability(state_id, action) for state_id in self.state_ids)
                for action in self.actions
            },
        )

    def record(self) -> dict[str, object]:
        return {
            "state_ids": self.state_ids,
            "actions": self.actions,
            "probabilities": [
                {"state_id": state_id, "opponent_action": action, "probability": self.probability(state_id, action)}
                for state_id in self.state_ids
                for action in self.actions
            ],
            "state_marginal": self.state_marginal(),
            "action_marginal": self.action_marginal().record(),
        }


@dataclass(frozen=True)
class RiskEvaluation:
    criterion: str
    score: float
    expected_utility: float
    variance: float
    standard_deviation: float
    worst_case: float
    best_case: float
    lower_tail_cvar: float
    parameters: Mapping[str, float]

    def record(self) -> dict[str, object]:
        return {
            "criterion": self.criterion,
            "score": self.score,
            "expected_utility": self.expected_utility,
            "variance": self.variance,
            "standard_deviation": self.standard_deviation,
            "worst_case": self.worst_case,
            "best_case": self.best_case,
            "lower_tail_cvar": self.lower_tail_cvar,
            "parameters": dict(self.parameters),
        }


class RiskCriterion(Protocol):
    name: str

    def evaluate(self, lottery: DiscreteDistribution[float]) -> RiskEvaluation: ...


def _summary(
    criterion: str,
    score: float,
    lottery: DiscreteDistribution[float],
    parameters: Mapping[str, float] | None = None,
) -> RiskEvaluation:
    values = [outcome.value for outcome in lottery.outcomes]
    return RiskEvaluation(
        criterion=criterion,
        score=score,
        expected_utility=lottery.expected(),
        variance=lottery.variance(),
        standard_deviation=lottery.standard_deviation(),
        worst_case=min(values),
        best_case=max(values),
        lower_tail_cvar=lottery.lower_tail_cvar(0.1),
        parameters=MappingProxyType(dict(parameters or {})),
    )


@dataclass(frozen=True)
class ExpectedValueCriterion:
    name: str = "expected_value"

    def evaluate(self, lottery: DiscreteDistribution[float]) -> RiskEvaluation:
        return _summary(self.name, lottery.expected(), lottery)


@dataclass(frozen=True)
class MeanVarianceCriterion:
    risk_aversion: float = 0.1
    name: str = "mean_variance"

    def __post_init__(self) -> None:
        if self.risk_aversion < 0:
            raise ValueError("risk_aversion must be non-negative")

    def evaluate(self, lottery: DiscreteDistribution[float]) -> RiskEvaluation:
        score = lottery.expected() - self.risk_aversion * lottery.variance()
        return _summary(self.name, score, lottery, {"risk_aversion": self.risk_aversion})


@dataclass(frozen=True)
class CARACriterion:
    """Constant-absolute-risk-aversion certainty equivalent."""

    risk_aversion: float = 0.2
    name: str = "cara_certainty_equivalent"

    def __post_init__(self) -> None:
        if self.risk_aversion <= 0:
            raise ValueError("CARA risk_aversion must be positive")

    def evaluate(self, lottery: DiscreteDistribution[float]) -> RiskEvaluation:
        transformed = [(-self.risk_aversion * outcome.value, outcome.probability) for outcome in lottery.outcomes]
        maximum = max(value for value, _ in transformed)
        log_expectation = maximum + log(sum(probability * exp(value - maximum) for value, probability in transformed))
        certainty_equivalent = -log_expectation / self.risk_aversion
        return _summary(
            self.name,
            certainty_equivalent,
            lottery,
            {"risk_aversion": self.risk_aversion, "certainty_equivalent": certainty_equivalent},
        )


@dataclass(frozen=True)
class LowerCVaRCriterion:
    alpha: float = 0.1
    name: str = "lower_tail_cvar"

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha <= 1.0:
            raise ValueError("CVaR alpha must be in (0, 1]")

    def evaluate(self, lottery: DiscreteDistribution[float]) -> RiskEvaluation:
        score = lottery.lower_tail_cvar(self.alpha)
        return _summary(self.name, score, lottery, {"alpha": self.alpha})


@dataclass(frozen=True)
class MaximinCriterion:
    name: str = "maximin"

    def evaluate(self, lottery: DiscreteDistribution[float]) -> RiskEvaluation:
        score = min(outcome.value for outcome in lottery.outcomes)
        return _summary(self.name, score, lottery)


@dataclass(frozen=True)
class ProspectValueCriterion:
    """Reference-dependent subjective value with asymmetric loss aversion."""

    reference_point: float = 0.0
    gain_curvature: float = 0.88
    loss_curvature: float = 0.88
    loss_aversion: float = 2.25
    name: str = "prospect_value"

    def __post_init__(self) -> None:
        if self.gain_curvature <= 0 or self.loss_curvature <= 0 or self.loss_aversion <= 0:
            raise ValueError("prospect-value parameters must be positive")

    def _value(self, utility: float) -> float:
        delta = utility - self.reference_point
        if delta >= 0:
            return delta ** self.gain_curvature
        return -self.loss_aversion * ((-delta) ** self.loss_curvature)

    def evaluate(self, lottery: DiscreteDistribution[float]) -> RiskEvaluation:
        score = lottery.expected(self._value)
        return _summary(
            self.name,
            score,
            lottery,
            {
                "reference_point": self.reference_point,
                "gain_curvature": self.gain_curvature,
                "loss_curvature": self.loss_curvature,
                "loss_aversion": self.loss_aversion,
            },
        )


@dataclass(frozen=True)
class DecisionAnalysis:
    game_id: str
    player: Player
    criterion: str
    opponent_belief: ActionBelief
    joint_belief: StateActionBelief
    lotteries: Mapping[str, DiscreteDistribution[float]]
    evaluations: Mapping[str, RiskEvaluation]
    catastrophe_probabilities: Mapping[str, float]
    optimal_actions: tuple[str, ...]
    selected_action: str
    safe_action_margin: float

    def record(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "player": self.player,
            "criterion": self.criterion,
            "opponent_belief": self.opponent_belief.record(),
            "joint_belief": self.joint_belief.record(),
            "lotteries": {
                action: lottery.record() for action, lottery in self.lotteries.items()
            },
            "evaluations": {
                action: evaluation.record() for action, evaluation in self.evaluations.items()
            },
            "catastrophe_probabilities": dict(self.catastrophe_probabilities),
            "optimal_actions": self.optimal_actions,
            "selected_action": self.selected_action,
            "safe_action_margin": self.safe_action_margin,
        }


def action_lottery(
    game: UncertainPayoffGame,
    player: Player,
    own_action: str,
    joint_belief: StateActionBelief,
) -> DiscreteDistribution[float]:
    if own_action not in game.actions:
        raise ValueError(f"unknown action {own_action!r}")
    if joint_belief.state_ids != tuple(state.state_id for state in game.states) or joint_belief.actions != game.actions:
        raise ValueError("joint belief does not match uncertain game")
    states = {state.state_id: state for state in game.states}
    outcomes: list[WeightedOutcome[float]] = []
    for state_id in joint_belief.state_ids:
        state = states[state_id]
        for opponent_action in game.actions:
            probability = joint_belief.probability(state_id, opponent_action)
            profile: Profile = (
                (own_action, opponent_action) if player == "row" else (opponent_action, own_action)
            )
            payoff = state.game.payoff(profile)
            utility = payoff.row if player == "row" else payoff.column
            outcomes.append(WeightedOutcome(
                f"{state_id}|opponent={opponent_action}",
                probability,
                utility,
                {
                    "state_id": state_id,
                    "opponent_action": opponent_action,
                    "profile": profile,
                    "catastrophic": profile in state.game.catastrophic_profiles,
                },
            ))
    return DiscreteDistribution(tuple(outcomes))


def analyze_decision(
    game: UncertainPayoffGame,
    player: Player,
    opponent_belief: ActionBelief,
    criterion: RiskCriterion = ExpectedValueCriterion(),
    *,
    joint_belief: StateActionBelief | None = None,
) -> DecisionAnalysis:
    joint = joint_belief or StateActionBelief.independent(game, opponent_belief)
    if joint.action_marginal().probabilities != opponent_belief.probabilities:
        # A correlated joint belief is authoritative; expose its action marginal
        # as the actual opponent belief used in the analysis.
        opponent_belief = joint.action_marginal()
    lotteries = {action: action_lottery(game, player, action, joint) for action in game.actions}
    evaluations = {action: criterion.evaluate(lottery) for action, lottery in lotteries.items()}
    best_score = max(evaluation.score for evaluation in evaluations.values())
    optimal = tuple(action for action in game.actions if isclose(evaluations[action].score, best_score, abs_tol=1e-9))
    selected = game.cooperative_action if game.cooperative_action in optimal else optimal[0]
    catastrophe_probabilities = {}
    state_lookup = {state.state_id: state for state in game.states}
    for own_action in game.actions:
        probability = 0.0
        for state_id in joint.state_ids:
            for opponent_action in game.actions:
                profile = (own_action, opponent_action) if player == "row" else (opponent_action, own_action)
                if profile in state_lookup[state_id].game.catastrophic_profiles:
                    probability += joint.probability(state_id, opponent_action)
        catastrophe_probabilities[own_action] = probability
    margin = evaluations[game.cooperative_action].score - evaluations[game.competitive_action].score
    return DecisionAnalysis(
        game_id=game.game_id,
        player=player,
        criterion=criterion.name,
        opponent_belief=opponent_belief,
        joint_belief=joint,
        lotteries=MappingProxyType(lotteries),
        evaluations=MappingProxyType(evaluations),
        catastrophe_probabilities=MappingProxyType(catastrophe_probabilities),
        optimal_actions=optimal,
        selected_action=selected,
        safe_action_margin=margin,
    )


@dataclass(frozen=True)
class AmbiguousActionBelief:
    """Interval-valued belief about the opponent's competitive-action probability."""

    cooperative_action: str
    competitive_action: str
    minimum_competitive_probability: float
    maximum_competitive_probability: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.minimum_competitive_probability <= self.maximum_competitive_probability <= 1.0:
            raise ValueError("ambiguity interval must satisfy 0 <= minimum <= maximum <= 1")

    def endpoint_beliefs(self) -> tuple[ActionBelief, ...]:
        values = (self.minimum_competitive_probability, self.maximum_competitive_probability)
        return tuple(
            ActionBelief.binary(self.cooperative_action, self.competitive_action, value)
            for value in dict.fromkeys(values)
        )

    def record(self) -> dict[str, object]:
        return {
            "cooperative_action": self.cooperative_action,
            "competitive_action": self.competitive_action,
            "minimum_competitive_probability": self.minimum_competitive_probability,
            "maximum_competitive_probability": self.maximum_competitive_probability,
        }


@dataclass(frozen=True)
class RobustDecisionAnalysis:
    ambiguity: AmbiguousActionBelief
    endpoint_analyses: tuple[DecisionAnalysis, ...]
    worst_case_scores: Mapping[str, float]
    optimal_actions: tuple[str, ...]
    selected_action: str
    robust_safe_action_margin: float

    def record(self) -> dict[str, object]:
        return {
            "ambiguity": self.ambiguity.record(),
            "endpoint_analyses": [analysis.record() for analysis in self.endpoint_analyses],
            "worst_case_scores": dict(self.worst_case_scores),
            "optimal_actions": self.optimal_actions,
            "selected_action": self.selected_action,
            "robust_safe_action_margin": self.robust_safe_action_margin,
        }


def analyze_ambiguity(
    game: UncertainPayoffGame,
    player: Player,
    ambiguity: AmbiguousActionBelief,
    criterion: RiskCriterion = ExpectedValueCriterion(),
) -> RobustDecisionAnalysis:
    if (ambiguity.cooperative_action, ambiguity.competitive_action) != game.actions:
        raise ValueError("ambiguity actions must match the uncertain game")
    analyses = tuple(
        analyze_decision(game, player, belief, criterion)
        for belief in ambiguity.endpoint_beliefs()
    )
    worst = {
        action: min(analysis.evaluations[action].score for analysis in analyses)
        for action in game.actions
    }
    best = max(worst.values())
    optimal = tuple(action for action in game.actions if isclose(worst[action], best, abs_tol=1e-9))
    selected = game.cooperative_action if game.cooperative_action in optimal else optimal[0]
    return RobustDecisionAnalysis(
        ambiguity=ambiguity,
        endpoint_analyses=analyses,
        worst_case_scores=MappingProxyType(worst),
        optimal_actions=optimal,
        selected_action=selected,
        robust_safe_action_margin=worst[game.cooperative_action] - worst[game.competitive_action],
    )


def add_competitive_action_cost(game: UncertainPayoffGame, cost: float) -> UncertainPayoffGame:
    """Apply an additional deterministic cost whenever a player competes."""
    if cost < 0:
        raise ValueError("competitive action cost must be non-negative")
    states: list[PayoffState] = []
    for state in game.states:
        original = state.game
        adjusted_payoffs: dict[Profile, Payoff] = {}
        for profile in original.profiles:
            payoff = original.payoff(profile)
            adjusted_payoffs[profile] = Payoff(
                payoff.row - (cost if profile[0] == original.competitive_action else 0.0),
                payoff.column - (cost if profile[1] == original.competitive_action else 0.0),
            )
        adjusted = SymmetricTwoByTwoGame(
            game_id=f"{original.game_id}_cost_{cost:g}",
            name=original.name,
            family=original.family,
            actions=original.actions,
            cooperative_action=original.cooperative_action,
            competitive_action=original.competitive_action,
            payoffs=adjusted_payoffs,
            description=f"{original.description} Additional competitive-action cost: {cost:g}.",
            catastrophic_profiles=original.catastrophic_profiles,
        )
        states.append(PayoffState(
            state.state_id,
            state.probability,
            adjusted,
            state.description,
            {**dict(state.parameters), "additional_competitive_cost": cost},
        ))
    return UncertainPayoffGame(f"{game.game_id}_cost_{cost:g}", game.name, tuple(states))


@dataclass(frozen=True)
class RiskAdjustedThreshold:
    threshold: float | None
    criterion: str
    player: Player
    lower_bound: float
    upper_bound: float
    lower_margin: float
    upper_margin: float
    iterations: int
    tolerance: float

    @property
    def feasible(self) -> bool:
        return self.threshold is not None

    def record(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "feasible": self.feasible,
            "criterion": self.criterion,
            "player": self.player,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "lower_margin": self.lower_margin,
            "upper_margin": self.upper_margin,
            "iterations": self.iterations,
            "tolerance": self.tolerance,
        }


def solve_risk_adjusted_threshold(
    game: UncertainPayoffGame,
    player: Player,
    opponent_belief: ActionBelief,
    criterion: RiskCriterion = ExpectedValueCriterion(),
    *,
    max_cost: float = 100.0,
    tolerance: float = 1e-7,
) -> RiskAdjustedThreshold:
    """Find the least added competitive-action cost with a non-negative safe margin."""
    if max_cost < 0:
        raise ValueError("max_cost must be non-negative")
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")

    def margin(cost: float) -> float:
        adjusted = add_competitive_action_cost(game, cost)
        return analyze_decision(adjusted, player, opponent_belief, criterion).safe_action_margin

    lower = 0.0
    upper = max_cost
    lower_margin = margin(lower)
    upper_margin = margin(upper)
    if lower_margin >= 0:
        return RiskAdjustedThreshold(0.0, criterion.name, player, lower, upper, lower_margin, upper_margin, 0, tolerance)
    if upper_margin < 0:
        return RiskAdjustedThreshold(None, criterion.name, player, lower, upper, lower_margin, upper_margin, 0, tolerance)
    iterations = 0
    while upper - lower > tolerance:
        middle = (lower + upper) / 2.0
        if margin(middle) >= 0:
            upper = middle
        else:
            lower = middle
        iterations += 1
    return RiskAdjustedThreshold(
        upper,
        criterion.name,
        player,
        0.0,
        max_cost,
        lower_margin,
        upper_margin,
        iterations,
        tolerance,
    )

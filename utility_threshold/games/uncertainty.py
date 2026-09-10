"""Exact discrete uncertainty over game payoffs and catastrophic outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose, log
from types import MappingProxyType
from typing import Callable, Generic, Iterable, Mapping, TypeVar

from .base import Payoff, Player, Profile, SymmetricTwoByTwoGame, TwoByTwoGame

T = TypeVar("T")


@dataclass(frozen=True)
class WeightedOutcome(Generic[T]):
    """One named outcome in a finite probability distribution."""

    label: str
    probability: float
    value: T
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("outcome labels must be non-empty")
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("outcome probability must be between zero and one")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class DiscreteDistribution(Generic[T]):
    """A validated finite distribution with exact summary operations."""

    outcomes: tuple[WeightedOutcome[T], ...]

    def __post_init__(self) -> None:
        if not self.outcomes:
            raise ValueError("a distribution needs at least one outcome")
        labels = [outcome.label for outcome in self.outcomes]
        if len(labels) != len(set(labels)):
            raise ValueError("distribution outcome labels must be unique")
        if not isclose(sum(outcome.probability for outcome in self.outcomes), 1.0, abs_tol=1e-9):
            raise ValueError("distribution probabilities must sum to one")

    @classmethod
    def certain(cls, value: T, label: str = "certain") -> DiscreteDistribution[T]:
        return cls((WeightedOutcome(label, 1.0, value),))

    def expected(self, value_fn: Callable[[T], float] = float) -> float:
        return sum(outcome.probability * value_fn(outcome.value) for outcome in self.outcomes)

    def variance(self, value_fn: Callable[[T], float] = float) -> float:
        mean = self.expected(value_fn)
        return sum(
            outcome.probability * (value_fn(outcome.value) - mean) ** 2
            for outcome in self.outcomes
        )

    def standard_deviation(self, value_fn: Callable[[T], float] = float) -> float:
        return self.variance(value_fn) ** 0.5

    @property
    def entropy(self) -> float:
        """Shannon entropy in nats."""
        return -sum(
            outcome.probability * log(outcome.probability)
            for outcome in self.outcomes
            if outcome.probability > 0
        )

    def quantile(self, probability: float, value_fn: Callable[[T], float] = float) -> float:
        """Return the left-continuous lower quantile."""
        if not 0.0 <= probability <= 1.0:
            raise ValueError("quantile probability must be between zero and one")
        ordered = sorted(self.outcomes, key=lambda outcome: value_fn(outcome.value))
        if probability == 0:
            return value_fn(ordered[0].value)
        cumulative = 0.0
        for outcome in ordered:
            cumulative += outcome.probability
            if cumulative + 1e-12 >= probability:
                return value_fn(outcome.value)
        return value_fn(ordered[-1].value)

    def lower_tail_cvar(self, alpha: float, value_fn: Callable[[T], float] = float) -> float:
        """Mean of the worst ``alpha`` probability mass, including fractional atoms."""
        if not 0.0 < alpha <= 1.0:
            raise ValueError("CVaR alpha must be in (0, 1]")
        remaining = alpha
        weighted_sum = 0.0
        for outcome in sorted(self.outcomes, key=lambda candidate: value_fn(candidate.value)):
            mass = min(remaining, outcome.probability)
            weighted_sum += mass * value_fn(outcome.value)
            remaining -= mass
            if remaining <= 1e-12:
                break
        return weighted_sum / alpha

    def probability(self, predicate: Callable[[T], bool]) -> float:
        return sum(outcome.probability for outcome in self.outcomes if predicate(outcome.value))

    def record(self, value_fn: Callable[[T], object] | None = None) -> list[dict[str, object]]:
        serializer = value_fn or (lambda value: value)
        return [
            {
                "label": outcome.label,
                "probability": outcome.probability,
                "value": serializer(outcome.value),
                "metadata": dict(outcome.metadata),
            }
            for outcome in self.outcomes
        ]


@dataclass(frozen=True)
class PayoffState:
    """One possible complete payoff matrix in an uncertain game."""

    state_id: str
    probability: float
    game: TwoByTwoGame
    description: str = ""
    parameters: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.state_id.strip():
            raise ValueError("state_id must be non-empty")
        if not 0.0 <= self.probability <= 1.0:
            raise ValueError("state probability must be between zero and one")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True)
class UncertainPayoffGame:
    """A common game form with a probability distribution over payoff matrices."""

    game_id: str
    name: str
    states: tuple[PayoffState, ...]

    def __post_init__(self) -> None:
        if not self.states:
            raise ValueError("an uncertain game needs at least one payoff state")
        state_ids = [state.state_id for state in self.states]
        if len(state_ids) != len(set(state_ids)):
            raise ValueError("payoff state ids must be unique")
        if not isclose(sum(state.probability for state in self.states), 1.0, abs_tol=1e-9):
            raise ValueError("payoff state probabilities must sum to one")
        reference = self.states[0].game
        for state in self.states[1:]:
            game = state.game
            if (
                game.actions != reference.actions
                or game.cooperative_action != reference.cooperative_action
                or game.competitive_action != reference.competitive_action
                or game.family != reference.family
            ):
                raise ValueError("all payoff states must share the same game form and action semantics")

    @property
    def actions(self) -> tuple[str, str]:
        return self.states[0].game.actions

    @property
    def cooperative_action(self) -> str:
        return self.states[0].game.cooperative_action

    @property
    def competitive_action(self) -> str:
        return self.states[0].game.competitive_action

    @property
    def family(self) -> str:
        return self.states[0].game.family

    @property
    def state_entropy(self) -> float:
        return self.state_distribution.entropy

    @property
    def state_distribution(self) -> DiscreteDistribution[TwoByTwoGame]:
        return DiscreteDistribution(tuple(
            WeightedOutcome(
                state.state_id,
                state.probability,
                state.game,
                {"description": state.description, "parameters": dict(state.parameters)},
            )
            for state in self.states
        ))

    def payoff_distribution(self, profile: Profile, player: Player) -> DiscreteDistribution[float]:
        if profile not in self.states[0].game.profiles:
            raise ValueError(f"invalid profile {profile!r}")
        return DiscreteDistribution(tuple(
            WeightedOutcome(
                state.state_id,
                state.probability,
                state.game.payoff(profile).row if player == "row" else state.game.payoff(profile).column,
                {"description": state.description, "parameters": dict(state.parameters)},
            )
            for state in self.states
        ))

    def expected_payoff(self, profile: Profile) -> Payoff:
        row = self.payoff_distribution(profile, "row").expected()
        column = self.payoff_distribution(profile, "column").expected()
        return Payoff(row, column)

    def catastrophe_probability(self, profile: Profile) -> float:
        return sum(
            state.probability
            for state in self.states
            if profile in state.game.catastrophic_profiles
        )

    def expected_game(self) -> TwoByTwoGame:
        reference = self.states[0].game
        catastrophic = frozenset(
            profile
            for profile in reference.profiles
            if self.catastrophe_probability(profile) > 0
        )
        game_type = SymmetricTwoByTwoGame if reference.is_symmetric else TwoByTwoGame
        return game_type(
            game_id=f"{self.game_id}_expected",
            name=f"{self.name} (expected payoffs)",
            family=reference.family,
            actions=reference.actions,
            cooperative_action=reference.cooperative_action,
            competitive_action=reference.competitive_action,
            payoffs={profile: self.expected_payoff(profile) for profile in reference.profiles},
            description=(
                f"Probability-weighted expected game over {len(self.states)} payoff states."
            ),
            catastrophic_profiles=catastrophic,
        )

    def record(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "name": self.name,
            "family": self.family,
            "actions": self.actions,
            "state_entropy_nats": self.state_entropy,
            "states": [
                {
                    "state_id": state.state_id,
                    "probability": state.probability,
                    "description": state.description,
                    "parameters": dict(state.parameters),
                    "payoff_matrix": list(state.game.matrix_records()),
                }
                for state in self.states
            ],
            "expected_payoff_matrix": list(self.expected_game().matrix_records()),
        }


def payoff_states(states: Iterable[PayoffState], *, game_id: str, name: str) -> UncertainPayoffGame:
    """Convenience constructor that freezes an iterable of payoff states."""
    return UncertainPayoffGame(game_id=game_id, name=name, states=tuple(states))

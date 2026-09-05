"""Reusable normal-form machinery for symmetric two-player, two-action games.

The original project models a leader choosing oversight and a follower making a
single threshold decision.  This module supplies the missing *game*: both
players have actions, every joint action has a payoff, and strategic claims can
be checked directly from the matrix.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from types import MappingProxyType
from typing import Iterable, Literal, Mapping

Player = Literal["row", "column"]
Profile = tuple[str, str]
WelfareCriterion = Literal["utilitarian", "egalitarian", "nash_product"]


@dataclass(frozen=True)
class Payoff:
    """Utilities received by the row and column players at one outcome."""

    row: float
    column: float

    @property
    def total(self) -> float:
        return self.row + self.column

    @property
    def minimum(self) -> float:
        return min(self.row, self.column)


@dataclass(frozen=True)
class SymmetricTwoByTwoGame:
    """A validated symmetric 2x2 normal-form game.

    Action strings are deliberately scenario-specific (for example,
    ``PAUSE_FOR_AUDIT`` and ``RACE_TO_DEPLOY``).  ``cooperative_action`` and
    ``competitive_action`` preserve their game-theoretic roles without forcing
    vague COOPERATE/ATTACK labels onto every application.
    """

    game_id: str
    name: str
    family: str
    actions: tuple[str, str]
    cooperative_action: str
    competitive_action: str
    payoffs: Mapping[Profile, Payoff]
    description: str = ""
    catastrophic_profiles: frozenset[Profile] = frozenset()

    def __post_init__(self) -> None:
        if len(self.actions) != 2 or len(set(self.actions)) != 2:
            raise ValueError("a 2x2 game needs exactly two distinct actions")
        if self.cooperative_action not in self.actions or self.competitive_action not in self.actions:
            raise ValueError("cooperative and competitive actions must occur in actions")

        expected = {(row, column) for row in self.actions for column in self.actions}
        if set(self.payoffs) != expected:
            missing = expected - set(self.payoffs)
            extra = set(self.payoffs) - expected
            raise ValueError(f"payoff matrix must contain all four profiles; missing={missing}, extra={extra}")

        copied = {profile: payoff for profile, payoff in self.payoffs.items()}
        for row, column in expected:
            forward = copied[(row, column)]
            reverse = copied[(column, row)]
            if not isclose(forward.row, reverse.column) or not isclose(forward.column, reverse.row):
                raise ValueError("payoffs are not symmetric under exchange of players")
        if not set(self.catastrophic_profiles) <= expected:
            raise ValueError("catastrophic profiles must occur in the payoff matrix")
        object.__setattr__(self, "payoffs", MappingProxyType(copied))

    @property
    def profiles(self) -> tuple[Profile, ...]:
        return tuple((row, column) for row in self.actions for column in self.actions)

    def payoff(self, profile: Profile) -> Payoff:
        try:
            return self.payoffs[profile]
        except KeyError as exc:
            raise ValueError(f"invalid profile {profile!r} for actions {self.actions!r}") from exc

    def utility(self, player: Player, own_action: str, opponent_action: str) -> float:
        """Return a player's utility using actions from that player's perspective."""
        profile = (own_action, opponent_action) if player == "row" else (opponent_action, own_action)
        outcome = self.payoff(profile)
        return outcome.row if player == "row" else outcome.column

    def action_utilities(self, player: Player, opponent_action: str) -> dict[str, float]:
        if opponent_action not in self.actions:
            raise ValueError(f"unknown opponent action {opponent_action!r}")
        return {action: self.utility(player, action, opponent_action) for action in self.actions}

    def best_responses(self, player: Player, opponent_action: str, tolerance: float = 1e-9) -> tuple[str, ...]:
        utilities = self.action_utilities(player, opponent_action)
        best = max(utilities.values())
        return tuple(action for action in self.actions if utilities[action] >= best - tolerance)

    def is_nash(self, profile: Profile, tolerance: float = 1e-9) -> bool:
        row_action, column_action = profile
        return (
            row_action in self.best_responses("row", column_action, tolerance)
            and column_action in self.best_responses("column", row_action, tolerance)
        )

    def pure_nash_equilibria(self, tolerance: float = 1e-9) -> tuple[Profile, ...]:
        return tuple(profile for profile in self.profiles if self.is_nash(profile, tolerance))

    def dominant_actions(self, player: Player, strict: bool = False, tolerance: float = 1e-9) -> tuple[str, ...]:
        dominant: list[str] = []
        for action in self.actions:
            comparisons = []
            alternatives = [candidate for candidate in self.actions if candidate != action]
            for opponent_action in self.actions:
                action_value = self.utility(player, action, opponent_action)
                alternative_value = max(self.utility(player, candidate, opponent_action) for candidate in alternatives)
                comparisons.append(
                    action_value > alternative_value + tolerance
                    if strict
                    else action_value >= alternative_value - tolerance
                )
            if all(comparisons):
                dominant.append(action)
        return tuple(dominant)

    def regret(self, profile: Profile, player: Player) -> float:
        row_action, column_action = profile
        own = row_action if player == "row" else column_action
        opponent = column_action if player == "row" else row_action
        current = self.utility(player, own, opponent)
        return max(self.action_utilities(player, opponent).values()) - current

    def welfare(self, profile: Profile, criterion: WelfareCriterion = "utilitarian") -> float:
        payoff = self.payoff(profile)
        if criterion == "utilitarian":
            return payoff.total
        if criterion == "egalitarian":
            return payoff.minimum
        if criterion == "nash_product":
            # Nash welfare assumes non-negative gains. Scenario utilities can
            # be negative, so use the game-wide worst payoff as a disclosed
            # disagreement baseline rather than allowing two large losses to
            # produce a misleadingly large positive product.
            disagreement = min(
                utility
                for candidate in self.payoffs.values()
                for utility in (candidate.row, candidate.column)
            )
            return (payoff.row - disagreement) * (payoff.column - disagreement)
        raise ValueError(f"unknown welfare criterion {criterion!r}")

    def welfare_optimal_profiles(self, criterion: WelfareCriterion = "utilitarian", tolerance: float = 1e-9) -> tuple[Profile, ...]:
        values = {profile: self.welfare(profile, criterion) for profile in self.profiles}
        best = max(values.values())
        return tuple(profile for profile in self.profiles if values[profile] >= best - tolerance)

    def pareto_efficient_profiles(self) -> tuple[Profile, ...]:
        efficient: list[Profile] = []
        for candidate in self.profiles:
            value = self.payoff(candidate)
            dominated = False
            for challenger in self.profiles:
                other = self.payoff(challenger)
                weakly_better = other.row >= value.row and other.column >= value.column
                strictly_better = other.row > value.row or other.column > value.column
                if weakly_better and strictly_better:
                    dominated = True
                    break
            if not dominated:
                efficient.append(candidate)
        return tuple(efficient)

    def symmetric_mixed_equilibrium(self, tolerance: float = 1e-9) -> Mapping[str, float] | None:
        """Return a fully mixed symmetric equilibrium, when one exists.

        The probability is chosen so that a player is indifferent between both
        actions. Degenerate boundary solutions are omitted because the pure
        equilibrium API already represents them without ambiguity.
        """
        first, second = self.actions
        u_first_first = self.utility("row", first, first)
        u_first_second = self.utility("row", first, second)
        u_second_first = self.utility("row", second, first)
        u_second_second = self.utility("row", second, second)
        denominator = u_first_first - u_second_first - u_first_second + u_second_second
        if isclose(denominator, 0.0, abs_tol=tolerance):
            return None
        probability_first = (u_second_second - u_first_second) / denominator
        if probability_first <= tolerance or probability_first >= 1.0 - tolerance:
            return None
        return MappingProxyType({first: probability_first, second: 1.0 - probability_first})

    def expected_utility(
        self,
        player: Player,
        own_distribution: Mapping[str, float],
        opponent_distribution: Mapping[str, float],
    ) -> float:
        self._validate_distribution(own_distribution)
        self._validate_distribution(opponent_distribution)
        return sum(
            own_probability
            * opponent_probability
            * self.utility(player, own_action, opponent_action)
            for own_action, own_probability in own_distribution.items()
            for opponent_action, opponent_probability in opponent_distribution.items()
        )

    def catastrophe_probability(
        self,
        row_distribution: Mapping[str, float],
        column_distribution: Mapping[str, float],
    ) -> float:
        self._validate_distribution(row_distribution)
        self._validate_distribution(column_distribution)
        return sum(
            row_distribution[row] * column_distribution[column]
            for row, column in self.catastrophic_profiles
        )

    def matrix_records(self) -> tuple[dict[str, object], ...]:
        """JSON-friendly payoff records for logs, prompts, and result files."""
        return tuple(
            {
                "row_action": row,
                "column_action": column,
                "row_utility": self.payoff((row, column)).row,
                "column_utility": self.payoff((row, column)).column,
                "catastrophic": (row, column) in self.catastrophic_profiles,
            }
            for row, column in self.profiles
        )

    def _validate_distribution(self, distribution: Mapping[str, float]) -> None:
        if set(distribution) != set(self.actions):
            raise ValueError(f"distribution must assign both actions {self.actions!r}")
        if any(probability < 0 for probability in distribution.values()):
            raise ValueError("probabilities must be non-negative")
        if not isclose(sum(distribution.values()), 1.0, abs_tol=1e-9):
            raise ValueError("probabilities must sum to one")


def format_payoff_matrix(game: SymmetricTwoByTwoGame) -> str:
    """Render a compact plain-text matrix suitable for prompts and terminals."""
    first, second = game.actions

    def cell(row: str, column: str) -> str:
        payoff = game.payoff((row, column))
        return f"({payoff.row:g}, {payoff.column:g})"

    return "\n".join(
        (
            f"row\\column | {first} | {second}",
            f"{first} | {cell(first, first)} | {cell(first, second)}",
            f"{second} | {cell(second, first)} | {cell(second, second)}",
        )
    )


def unique_actions(actions: Iterable[str]) -> tuple[str, str]:
    """Validate and normalize a public two-action argument."""
    normalized = tuple(str(action).strip().upper() for action in actions)
    if len(normalized) != 2 or len(set(normalized)) != 2 or any(not action for action in normalized):
        raise ValueError("actions must contain exactly two distinct non-empty labels")
    return normalized  # type: ignore[return-value]

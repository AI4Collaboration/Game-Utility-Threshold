"""Equilibrium-selection conflict for Battle of the Sexes coordination."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .base import Payoff, Player, Profile, TwoByTwoGame, unique_actions


@dataclass(frozen=True)
class BattleOfTheSexesParameters:
    """Shared magnitudes for opposed preferences over two coordinated outcomes."""

    preferred_coordination: float = 4.0
    concession_coordination: float = 3.0
    miscoordination: float = 0.0

    def __post_init__(self) -> None:
        if not (
            self.preferred_coordination
            > self.concession_coordination
            > self.miscoordination
        ):
            raise ValueError(
                "Battle of the Sexes requires preferred coordination > "
                "concession coordination > miscoordination"
            )

    @property
    def preference_advantage(self) -> float:
        return self.preferred_coordination - self.concession_coordination

    def preferred_action_belief_threshold(
        self, coordination_bonus: float = 0.0
    ) -> float:
        """Belief in one's preferred action needed to insist rather than concede."""
        if coordination_bonus < 0:
            raise ValueError("coordination_bonus must be non-negative")
        numerator = (
            self.concession_coordination
            + coordination_bonus
            - self.miscoordination
        )
        denominator = (
            self.preferred_coordination
            + self.concession_coordination
            + 2.0 * coordination_bonus
            - 2.0 * self.miscoordination
        )
        return numerator / denominator


@dataclass(frozen=True)
class BattleOfTheSexesReport:
    game_id: str
    family: str
    coordination_bonus: float
    row_preferred_profile: Profile
    column_preferred_profile: Profile
    pure_nash_equilibria: tuple[Profile, ...]
    mixed_equilibrium: Mapping[Player, Mapping[str, float]]
    mixed_coordination_probability: float
    mixed_miscoordination_probability: float
    mixed_catastrophe_probability: float
    mixed_expected_utilities: Payoff
    preferred_action_belief_threshold: float
    preference_advantage: float
    minimum_compensation_to_concede: float

    def record(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "family": self.family,
            "coordination_bonus": self.coordination_bonus,
            "threshold_kind": "belief_in_preferred_coordination",
            "preferred_action_belief_threshold": self.preferred_action_belief_threshold,
            "row_preferred_profile": self.row_preferred_profile,
            "column_preferred_profile": self.column_preferred_profile,
            "pure_nash_equilibria": self.pure_nash_equilibria,
            "mixed_equilibrium": {
                player: dict(distribution)
                for player, distribution in self.mixed_equilibrium.items()
            },
            "mixed_coordination_probability": self.mixed_coordination_probability,
            "mixed_miscoordination_probability": self.mixed_miscoordination_probability,
            "mixed_catastrophe_probability": self.mixed_catastrophe_probability,
            "mixed_expected_utilities": {
                "row": self.mixed_expected_utilities.row,
                "column": self.mixed_expected_utilities.column,
            },
            "preference_advantage": self.preference_advantage,
            "minimum_compensation_to_concede": self.minimum_compensation_to_concede,
        }


def battle_of_the_sexes(
    parameters: BattleOfTheSexesParameters = BattleOfTheSexesParameters(),
    *,
    intervention: float = 0.0,
    actions: tuple[str, str] = ("OPTION_A", "OPTION_B"),
    game_id: str = "battle_of_the_sexes",
    name: str = "Battle of the Sexes",
    description: str = (
        "Both players prefer coordination to mismatch, but each prefers a "
        "different coordinated outcome."
    ),
) -> TwoByTwoGame:
    """Build the asymmetric-payoff coordination game.

    ``intervention`` is a neutral coordination assurance bonus paid to both
    players at either diagonal outcome. It raises the cost of miscoordination
    without privileging either player's preferred equilibrium.
    """
    if intervention < 0:
        raise ValueError("intervention must be non-negative")
    first, second = unique_actions(actions)
    p = parameters
    return TwoByTwoGame(
        game_id=game_id,
        name=name,
        family="battle_of_the_sexes",
        actions=(first, second),
        cooperative_action=first,
        competitive_action=second,
        payoffs={
            (first, first): Payoff(
                p.preferred_coordination + intervention,
                p.concession_coordination + intervention,
            ),
            (first, second): Payoff(p.miscoordination, p.miscoordination),
            (second, first): Payoff(p.miscoordination, p.miscoordination),
            (second, second): Payoff(
                p.concession_coordination + intervention,
                p.preferred_coordination + intervention,
            ),
        },
        description=description,
    )


def battle_of_the_sexes_report(
    parameters: BattleOfTheSexesParameters = BattleOfTheSexesParameters(),
    *,
    intervention: float = 0.0,
    actions: tuple[str, str] = ("OPTION_A", "OPTION_B"),
    game_id: str = "battle_of_the_sexes",
    name: str = "Battle of the Sexes",
    description: str = (
        "Both players prefer coordination to mismatch, but each prefers a "
        "different coordinated outcome."
    ),
) -> BattleOfTheSexesReport:
    game = battle_of_the_sexes(
        parameters,
        intervention=intervention,
        actions=actions,
        game_id=game_id,
        name=name,
        description=description,
    )
    mixed = game.mixed_equilibrium()
    if mixed is None:  # Defensive: strict parameter validation makes this unreachable.
        raise ValueError("Battle of the Sexes requires a fully mixed equilibrium")
    row_expected = game.expected_utility("row", mixed["row"], mixed["column"])
    column_expected = game.expected_utility(
        "column", mixed["column"], mixed["row"]
    )
    return BattleOfTheSexesReport(
        game_id=game.game_id,
        family=game.family,
        coordination_bonus=intervention,
        row_preferred_profile=(game.actions[0], game.actions[0]),
        column_preferred_profile=(game.actions[1], game.actions[1]),
        pure_nash_equilibria=game.pure_nash_equilibria(),
        mixed_equilibrium=MappingProxyType(
            {
                player: MappingProxyType(dict(distribution))
                for player, distribution in mixed.items()
            }
        ),
        mixed_coordination_probability=game.coordination_probability(
            mixed["row"], mixed["column"]
        ),
        mixed_miscoordination_probability=1.0
        - game.coordination_probability(mixed["row"], mixed["column"]),
        mixed_catastrophe_probability=game.catastrophe_probability(
            mixed["row"], mixed["column"]
        ),
        mixed_expected_utilities=Payoff(row_expected, column_expected),
        preferred_action_belief_threshold=parameters.preferred_action_belief_threshold(
            intervention
        ),
        preference_advantage=parameters.preference_advantage,
        minimum_compensation_to_concede=parameters.preference_advantage,
    )

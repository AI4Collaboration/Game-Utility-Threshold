"""Family-aware experimental treatment designs shared by every runner."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol

from .base import Profile, TwoByTwoGame
from .mechanisms import SidePaymentMechanism, cooperation_subsidy, coordination_subsidy


class GameForm(Protocol):
    family: str
    actions: tuple[str, str]
    cooperative_action: str
    competitive_action: str


@dataclass(frozen=True)
class TreatmentDesign:
    """A focal agreement and mediator lottery grounded in a game's structure."""

    target_profile: Profile
    mediator_distribution: Mapping[Profile, float]
    mediator_objective: str
    rationale: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mediator_distribution",
            MappingProxyType(dict(self.mediator_distribution)),
        )

    def record(self) -> dict[str, object]:
        return {
            "target_profile": self.target_profile,
            "mediator_distribution": [
                {"profile": profile, "probability": probability}
                for profile, probability in self.mediator_distribution.items()
            ],
            "mediator_objective": self.mediator_objective,
            "rationale": self.rationale,
        }


def treatment_design(game: GameForm, *, focal_index: int = 0) -> TreatmentDesign:
    """Return a balanced intervention target for a canonical game family."""
    first, second = game.actions
    if game.family == "chicken":
        anti_coordination = ((first, second), (second, first))
        return TreatmentDesign(
            target_profile=anti_coordination[focal_index % 2],
            mediator_distribution={anti_coordination[0]: 0.5, anti_coordination[1]: 0.5},
            mediator_objective="fair_anti_coordination",
            rationale="Avoid mutual escalation while alternating who bears the de-escalation cost.",
        )
    if game.family == "battle_of_the_sexes":
        coordination = ((first, first), (second, second))
        return TreatmentDesign(
            target_profile=coordination[focal_index % 2],
            mediator_distribution={coordination[0]: 0.5, coordination[1]: 0.5},
            mediator_objective="fair_equilibrium_selection",
            rationale="Select a compatible protocol without systematically privileging either player.",
        )
    target = (game.cooperative_action, game.cooperative_action)
    return TreatmentDesign(
        target_profile=target,
        mediator_distribution={target: 1.0},
        mediator_objective=(
            "payoff_dominant_assurance" if game.family == "stag_hunt" else "mutual_safety"
        ),
        rationale=(
            "Supply reciprocal assurance for the payoff-dominant containment outcome."
            if game.family == "stag_hunt"
            else "Coordinate on the jointly safe outcome."
        ),
    )


def treatment_subsidy(game: TwoByTwoGame, amount: float) -> SidePaymentMechanism:
    """Choose an external subsidy whose semantics match the game family."""
    if game.family == "battle_of_the_sexes":
        return coordination_subsidy(game, amount)
    return cooperation_subsidy(game, amount)

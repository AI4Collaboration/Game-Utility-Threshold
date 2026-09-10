"""Mechanism thresholds shared by the canonical game families."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .base import Profile, SymmetricTwoByTwoGame


@dataclass(frozen=True)
class InterventionPolicy:
    """Observable components that change the utility of a competitive action.

    The total intervention is

    ``direct_cost + detection_probability * sanction + internalized_harm``.

    This keeps institutional enforcement and an agent's own safety objective
    distinct in traces while allowing both to enter the same decision
    threshold.
    """

    direct_cost: float = 0.0
    detection_probability: float = 0.0
    sanction: float = 0.0
    internalized_harm: float = 0.0

    def __post_init__(self) -> None:
        if self.direct_cost < 0 or self.sanction < 0 or self.internalized_harm < 0:
            raise ValueError("intervention components must be non-negative")
        if not 0.0 <= self.detection_probability <= 1.0:
            raise ValueError("detection_probability must be between zero and one")

    @property
    def expected_cost(self) -> float:
        return self.direct_cost + self.detection_probability * self.sanction + self.internalized_harm

    def record(self) -> dict[str, float]:
        return {
            "direct_cost": self.direct_cost,
            "detection_probability": self.detection_probability,
            "sanction": self.sanction,
            "expected_sanction": self.detection_probability * self.sanction,
            "internalized_harm": self.internalized_harm,
            "expected_cost": self.expected_cost,
        }

    def minimum_detection_probability(self, target_threshold: float) -> float | None:
        """Least monitoring probability that reaches a target, or ``None`` if infeasible."""
        residual = target_threshold - self.direct_cost - self.internalized_harm
        if residual <= 0:
            return 0.0
        if self.sanction <= 0:
            return None
        required = residual / self.sanction
        return required if required <= 1.0 else None

    def minimum_sanction(self, target_threshold: float) -> float | None:
        """Least sanction that reaches a target at the configured monitoring rate."""
        residual = target_threshold - self.direct_cost - self.internalized_harm
        if residual <= 0:
            return 0.0
        if self.detection_probability <= 0:
            return None
        return residual / self.detection_probability


@dataclass(frozen=True)
class UtilityThresholdReport:
    """Complete strategic consequences of a competitive-action intervention."""

    game_id: str
    family: str
    intervention: float
    threshold_against_cooperation: float
    threshold_against_competition: float
    cooperation_margin_against_cooperation: float
    cooperation_margin_against_competition: float
    regime: str
    pure_nash_equilibria: tuple[Profile, ...]
    symmetric_mixed_equilibrium: Mapping[str, float] | None
    symmetric_catastrophe_probability: float

    @property
    def minimum_intervention_for_cooperation_dominance(self) -> float:
        return max(self.threshold_against_cooperation, self.threshold_against_competition, 0.0)

    @property
    def cooperation_is_strictly_dominant(self) -> bool:
        return (
            self.cooperation_margin_against_cooperation > 0
            and self.cooperation_margin_against_competition > 0
        )

    def record(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "family": self.family,
            "intervention": self.intervention,
            "threshold_kind": "action_incentive",
            "threshold_against_cooperation": self.threshold_against_cooperation,
            "threshold_against_competition": self.threshold_against_competition,
            "minimum_intervention_for_cooperation_dominance": (
                self.minimum_intervention_for_cooperation_dominance
            ),
            "cooperation_margin_against_cooperation": (
                self.cooperation_margin_against_cooperation
            ),
            "cooperation_margin_against_competition": (
                self.cooperation_margin_against_competition
            ),
            "regime": self.regime,
            "pure_nash_equilibria": self.pure_nash_equilibria,
            "symmetric_mixed_equilibrium": (
                dict(self.symmetric_mixed_equilibrium)
                if self.symmetric_mixed_equilibrium
                else None
            ),
            "symmetric_catastrophe_probability": (
                self.symmetric_catastrophe_probability
            ),
        }


def strategic_regime(
    game: SymmetricTwoByTwoGame,
    cooperation_margin_against_cooperation: float,
    cooperation_margin_against_competition: float,
    tolerance: float = 1e-9,
) -> str:
    if abs(cooperation_margin_against_cooperation) <= tolerance or abs(cooperation_margin_against_competition) <= tolerance:
        return "boundary"
    prefers_cooperation_if_cooperation = cooperation_margin_against_cooperation > 0
    prefers_cooperation_if_competition = cooperation_margin_against_competition > 0
    if prefers_cooperation_if_cooperation and prefers_cooperation_if_competition:
        return "cooperation_dominant"
    if not prefers_cooperation_if_cooperation and not prefers_cooperation_if_competition:
        return "competition_dominant"
    if not prefers_cooperation_if_cooperation and prefers_cooperation_if_competition:
        return "anti_coordination"
    return "coordination"


def build_threshold_report(
    game: SymmetricTwoByTwoGame,
    intervention: float,
    threshold_against_cooperation: float,
    threshold_against_competition: float,
) -> UtilityThresholdReport:
    margin_cooperation = intervention - threshold_against_cooperation
    margin_competition = intervention - threshold_against_competition
    mixed = game.symmetric_mixed_equilibrium()
    catastrophe_probability = game.catastrophe_probability(mixed, mixed) if mixed is not None else 0.0
    return UtilityThresholdReport(
        game_id=game.game_id,
        family=game.family,
        intervention=intervention,
        threshold_against_cooperation=threshold_against_cooperation,
        threshold_against_competition=threshold_against_competition,
        cooperation_margin_against_cooperation=margin_cooperation,
        cooperation_margin_against_competition=margin_competition,
        regime=strategic_regime(game, margin_cooperation, margin_competition),
        pure_nash_equilibria=game.pure_nash_equilibria(),
        symmetric_mixed_equilibrium=MappingProxyType(dict(mixed)) if mixed is not None else None,
        symmetric_catastrophe_probability=catastrophe_probability,
    )

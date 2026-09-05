"""Mechanism thresholds shared by the canonical game families."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .base import Profile, SymmetricTwoByTwoGame


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

"""A complete, mechanism-aware Chicken (Hawk-Dove) implementation."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Payoff, SymmetricTwoByTwoGame, unique_actions
from .thresholds import UtilityThresholdReport, build_threshold_report


@dataclass(frozen=True)
class ChickenParameters:
    """Base payoffs using the conventional ``T > R > S > P`` ordering."""

    temptation: float = 4.0
    reward: float = 3.0
    sucker: float = 1.0
    catastrophe: float = -10.0

    def __post_init__(self) -> None:
        if not self.temptation > self.reward > self.sucker > self.catastrophe:
            raise ValueError("Chicken requires temptation > reward > sucker > catastrophe")

    @property
    def threshold_against_cooperation(self) -> float:
        """Cost needed to remove the temptation to escalate against a yielding opponent."""
        return self.temptation - self.reward

    @property
    def threshold_against_escalation(self) -> float:
        """Cost needed to prefer yielding when the opponent escalates (normally negative)."""
        return self.catastrophe - self.sucker

    @property
    def cooperation_dominance_threshold(self) -> float:
        return max(self.threshold_against_cooperation, self.threshold_against_escalation, 0.0)


def chicken(
    parameters: ChickenParameters = ChickenParameters(),
    *,
    intervention: float = 0.0,
    actions: tuple[str, str] = ("YIELD", "ESCALATE"),
    game_id: str = "chicken",
    name: str = "Chicken",
    description: str = "Each player wants the other to yield, while mutual escalation is catastrophic.",
) -> SymmetricTwoByTwoGame:
    """Build an intervention-adjusted Chicken game.

    The expected intervention cost is charged whenever a player escalates.  It
    can therefore move the game from anti-coordination to safe-action
    dominance without changing the underlying catastrophe payoff.
    """
    if intervention < 0:
        raise ValueError("intervention must be non-negative")
    yield_action, escalate = unique_actions(actions)
    p = parameters
    return SymmetricTwoByTwoGame(
        game_id=game_id,
        name=name,
        family="chicken",
        actions=(yield_action, escalate),
        cooperative_action=yield_action,
        competitive_action=escalate,
        payoffs={
            (yield_action, yield_action): Payoff(p.reward, p.reward),
            (yield_action, escalate): Payoff(p.sucker, p.temptation - intervention),
            (escalate, yield_action): Payoff(p.temptation - intervention, p.sucker),
            (escalate, escalate): Payoff(p.catastrophe - intervention, p.catastrophe - intervention),
        },
        description=description,
        catastrophic_profiles=frozenset({(escalate, escalate)}),
    )


def chicken_threshold_report(
    parameters: ChickenParameters = ChickenParameters(),
    *,
    intervention: float = 0.0,
    actions: tuple[str, str] = ("YIELD", "ESCALATE"),
    game_id: str = "chicken",
    name: str = "Chicken",
    description: str = "Each player wants the other to yield, while mutual escalation is catastrophic.",
) -> UtilityThresholdReport:
    game = chicken(
        parameters,
        intervention=intervention,
        actions=actions,
        game_id=game_id,
        name=name,
        description=description,
    )
    return build_threshold_report(
        game,
        intervention,
        parameters.threshold_against_cooperation,
        parameters.threshold_against_escalation,
    )

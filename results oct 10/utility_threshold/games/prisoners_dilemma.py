"""A complete, mechanism-aware Prisoner's Dilemma implementation."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Payoff, SymmetricTwoByTwoGame, unique_actions
from .thresholds import UtilityThresholdReport, build_threshold_report


@dataclass(frozen=True)
class PrisonersDilemmaParameters:
    """Base payoffs using the conventional ``T > R > P > S`` ordering."""

    temptation: float = 5.0
    reward: float = 3.0
    punishment: float = 1.0
    sucker: float = 0.0

    def __post_init__(self) -> None:
        if not self.temptation > self.reward > self.punishment > self.sucker:
            raise ValueError("Prisoner's Dilemma requires temptation > reward > punishment > sucker")

    @property
    def threshold_against_cooperation(self) -> float:
        """Cost needed to remove the temptation to exploit a cooperator."""
        return self.temptation - self.reward

    @property
    def threshold_against_defection(self) -> float:
        """Cost needed to prefer cooperation when the opponent defects."""
        return self.punishment - self.sucker

    @property
    def cooperation_dominance_threshold(self) -> float:
        return max(self.threshold_against_cooperation, self.threshold_against_defection)


def prisoners_dilemma(
    parameters: PrisonersDilemmaParameters = PrisonersDilemmaParameters(),
    *,
    intervention: float = 0.0,
    actions: tuple[str, str] = ("COOPERATE", "DEFECT"),
    game_id: str = "prisoners_dilemma",
    name: str = "Prisoner's Dilemma",
    description: str = "Mutual cooperation is collectively best, but unilateral defection is individually tempting.",
) -> SymmetricTwoByTwoGame:
    """Build an intervention-adjusted Prisoner's Dilemma.

    ``intervention`` is the expected utility cost paid by each player choosing
    the competitive action.  It may represent monitoring-weighted sanctions,
    deployment friction, loss of access, or an internalized safety penalty.
    """
    if intervention < 0:
        raise ValueError("intervention must be non-negative")
    cooperate, defect = unique_actions(actions)
    p = parameters
    return SymmetricTwoByTwoGame(
        game_id=game_id,
        name=name,
        family="prisoners_dilemma",
        actions=(cooperate, defect),
        cooperative_action=cooperate,
        competitive_action=defect,
        payoffs={
            (cooperate, cooperate): Payoff(p.reward, p.reward),
            (cooperate, defect): Payoff(p.sucker, p.temptation - intervention),
            (defect, cooperate): Payoff(p.temptation - intervention, p.sucker),
            (defect, defect): Payoff(p.punishment - intervention, p.punishment - intervention),
        },
        description=description,
    )


def prisoners_dilemma_threshold_report(
    parameters: PrisonersDilemmaParameters = PrisonersDilemmaParameters(),
    *,
    intervention: float = 0.0,
    actions: tuple[str, str] = ("COOPERATE", "DEFECT"),
    game_id: str = "prisoners_dilemma",
    name: str = "Prisoner's Dilemma",
    description: str = "Mutual cooperation is collectively best, but unilateral defection is individually tempting.",
) -> UtilityThresholdReport:
    game = prisoners_dilemma(
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
        parameters.threshold_against_defection,
    )

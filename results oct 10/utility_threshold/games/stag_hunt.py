"""Assurance thresholds and complete normal-form support for Stag Hunt."""

from __future__ import annotations

from dataclasses import dataclass, fields

from .base import SymmetricTwoByTwoGame, Payoff, unique_actions
from .thresholds import UtilityThresholdReport, build_threshold_report


@dataclass(frozen=True)
class StagHuntParameters:
    """Payoffs ordered as ``R > T > P > S`` for assurance coordination.

    ``R`` is mutual high-value cooperation, ``T`` is the safe action against a
    cooperator, ``P`` is mutual safety, and ``S`` is failed unilateral
    cooperation. This ordering gives payoff-dominant and risk-dominant pure
    equilibria without importing Prisoner's Dilemma incentives.
    """

    mutual_cooperation: float = 4.0
    safe_against_cooperation: float = 3.0
    mutual_safety: float = 2.0
    failed_cooperation: float = 0.0

    def __post_init__(self) -> None:
        if not (
            self.mutual_cooperation
            > self.safe_against_cooperation
            > self.mutual_safety
            > self.failed_cooperation
        ):
            raise ValueError(
                "Stag Hunt requires mutual cooperation > safe against "
                "cooperation > mutual safety > failed cooperation"
            )

    @property
    def threshold_against_cooperation(self) -> float:
        """Subsidy at which cooperation ties safety against a cooperator."""
        return self.safe_against_cooperation - self.mutual_cooperation

    @property
    def threshold_against_safety(self) -> float:
        """Subsidy needed to insure unilateral cooperation against safety."""
        return self.mutual_safety - self.failed_cooperation

    @property
    def cooperation_dominance_threshold(self) -> float:
        return max(
            self.threshold_against_cooperation,
            self.threshold_against_safety,
            0.0,
        )

    def assurance_threshold(self, cooperation_subsidy: float = 0.0) -> float:
        """Minimum belief in counterpart cooperation for cooperation to pay."""
        if cooperation_subsidy < 0:
            raise ValueError("cooperation_subsidy must be non-negative")
        numerator = (
            self.mutual_safety
            - self.failed_cooperation
            - cooperation_subsidy
        )
        denominator = (
            self.mutual_cooperation
            - self.safe_against_cooperation
            + self.mutual_safety
            - self.failed_cooperation
        )
        return min(1.0, max(0.0, numerator / denominator))

    def risk_dominant_action(
        self,
        actions: tuple[str, str] = ("COOPERATE", "SAFE"),
        *,
        cooperation_subsidy: float = 0.0,
    ) -> str:
        cooperate, safe = unique_actions(actions)
        return (
            cooperate
            if self.assurance_threshold(cooperation_subsidy) <= 0.5
            else safe
        )


@dataclass(frozen=True)
class StagHuntReport(UtilityThresholdReport):
    """Action-incentive and belief thresholds for assurance coordination."""

    assurance_belief_threshold: float
    risk_dominance_margin: float
    payoff_dominant_profile: tuple[str, str]
    risk_dominant_profile: tuple[str, str]
    mixed_miscoordination_probability: float
    mixed_catastrophe_probability: float

    def record(self) -> dict[str, object]:
        record = super().record()
        record.update(
            {
                "threshold_kind": "assurance_belief_and_action_incentive",
                "assurance_belief_threshold": self.assurance_belief_threshold,
                "risk_dominance_margin": self.risk_dominance_margin,
                "payoff_dominant_profile": self.payoff_dominant_profile,
                "risk_dominant_profile": self.risk_dominant_profile,
                "mixed_miscoordination_probability": (
                    self.mixed_miscoordination_probability
                ),
                "mixed_catastrophe_probability": (
                    self.mixed_catastrophe_probability
                ),
            }
        )
        return record


def stag_hunt(
    parameters: StagHuntParameters = StagHuntParameters(),
    *,
    intervention: float = 0.0,
    actions: tuple[str, str] = ("COOPERATE", "SAFE"),
    game_id: str = "stag_hunt",
    name: str = "Stag Hunt",
    description: str = (
        "High-value cooperation succeeds only with reciprocal assurance; a "
        "lower-value safe action is individually robust."
    ),
) -> SymmetricTwoByTwoGame:
    """Build a Stag Hunt with a subsidy on the cooperative action.

    ``intervention`` is an assurance benefit received whenever a player takes
    the high-value cooperative action. It may represent insurance, escrow,
    verified readiness, or a guaranteed cooperation payment.
    """
    if intervention < 0:
        raise ValueError("intervention must be non-negative")
    cooperate, safe = unique_actions(actions)
    p = parameters
    return SymmetricTwoByTwoGame(
        game_id=game_id,
        name=name,
        family="stag_hunt",
        actions=(cooperate, safe),
        cooperative_action=cooperate,
        competitive_action=safe,
        payoffs={
            (cooperate, cooperate): Payoff(
                p.mutual_cooperation + intervention,
                p.mutual_cooperation + intervention,
            ),
            (cooperate, safe): Payoff(
                p.failed_cooperation + intervention,
                p.safe_against_cooperation,
            ),
            (safe, cooperate): Payoff(
                p.safe_against_cooperation,
                p.failed_cooperation + intervention,
            ),
            (safe, safe): Payoff(p.mutual_safety, p.mutual_safety),
        },
        description=description,
    )


def stag_hunt_threshold_report(
    parameters: StagHuntParameters = StagHuntParameters(),
    *,
    intervention: float = 0.0,
    actions: tuple[str, str] = ("COOPERATE", "SAFE"),
    game_id: str = "stag_hunt",
    name: str = "Stag Hunt",
    description: str = (
        "High-value cooperation succeeds only with reciprocal assurance; a "
        "lower-value safe action is individually robust."
    ),
) -> StagHuntReport:
    game = stag_hunt(
        parameters,
        intervention=intervention,
        actions=actions,
        game_id=game_id,
        name=name,
        description=description,
    )
    base = build_threshold_report(
        game,
        intervention,
        parameters.threshold_against_cooperation,
        parameters.threshold_against_safety,
    )
    assurance = parameters.assurance_threshold(intervention)
    risk_dominant_action = parameters.risk_dominant_action(
        game.actions,
        cooperation_subsidy=intervention,
    )
    mixed = game.symmetric_mixed_equilibrium()
    miscoordination = (
        2.0 * mixed[game.actions[0]] * mixed[game.actions[1]]
        if mixed is not None
        else 0.0
    )
    inherited = {
        field.name: getattr(base, field.name)
        for field in fields(UtilityThresholdReport)
    }
    return StagHuntReport(
        **inherited,
        assurance_belief_threshold=assurance,
        risk_dominance_margin=0.5 - assurance,
        payoff_dominant_profile=(game.actions[0], game.actions[0]),
        risk_dominant_profile=(risk_dominant_action, risk_dominant_action),
        mixed_miscoordination_probability=miscoordination,
        mixed_catastrophe_probability=base.symmetric_catastrophe_probability,
    )

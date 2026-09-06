"""Information, reputation, mediation, and institutional composition.

These mechanisms are executable objects rather than prompt labels.  Cheap talk
updates explicit beliefs, reputation accumulates uncertain evidence, and a
mediator is audited against the obedience constraints of a correlated
equilibrium.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose
from random import Random
from types import MappingProxyType
from typing import Mapping

from .base import Player, Profile, SymmetricTwoByTwoGame
from .beliefs import ActionBelief, AsymmetricBeliefs, BeliefUpdate, binary_communication_model
from .mechanisms import Mechanism, MechanismApplication, MechanismInput, as_application


def _other(player: Player) -> Player:
    return "column" if player == "row" else "row"


@dataclass(frozen=True)
class CommunicationOutcome:
    """Both players' posterior beliefs after a simultaneous cheap-talk round."""

    messages: Mapping[Player, str]
    sender_credibility: Mapping[Player, float]
    row_update: BeliefUpdate
    column_update: BeliefUpdate

    def __post_init__(self) -> None:
        object.__setattr__(self, "messages", MappingProxyType(dict(self.messages)))
        object.__setattr__(
            self,
            "sender_credibility",
            MappingProxyType(dict(self.sender_credibility)),
        )

    @property
    def posteriors(self) -> AsymmetricBeliefs:
        return AsymmetricBeliefs(
            row_about_column=self.row_update.posterior,
            column_about_row=self.column_update.posterior,
        )

    def record(self) -> dict[str, object]:
        return {
            "mechanism_id": "pre_play_communication",
            "binding": False,
            "simultaneous": True,
            "messages": dict(self.messages),
            "sender_credibility": dict(self.sender_credibility),
            "row_observes_column": self.row_update.record(),
            "column_observes_row": self.column_update.record(),
            "posteriors": self.posteriors.record(),
        }


@dataclass(frozen=True)
class NonBindingCommunication:
    """A calibrated cheap-talk round in which each player claims an action."""

    row_message: str
    column_message: str
    row_credibility: float = 0.75
    column_credibility: float = 0.75
    mechanism_id: str = "pre_play_communication"

    def __post_init__(self) -> None:
        for name, credibility in (
            ("row_credibility", self.row_credibility),
            ("column_credibility", self.column_credibility),
        ):
            if not 0.0 <= credibility <= 1.0:
                raise ValueError(f"{name} must be between zero and one")

    def run(self, priors: AsymmetricBeliefs) -> CommunicationOutcome:
        actions = priors.row_about_column.actions
        if self.row_message not in actions or self.column_message not in actions:
            raise ValueError("messages must claim an action covered by the priors")

        row_observation_model = binary_communication_model(
            actions[0], actions[1], credibility=self.column_credibility
        )
        column_observation_model = binary_communication_model(
            actions[0], actions[1], credibility=self.row_credibility
        )
        row_update = row_observation_model.observe(
            priors.row_about_column, f"MESSAGE_{self.column_message}"
        )
        column_update = column_observation_model.observe(
            priors.column_about_row, f"MESSAGE_{self.row_message}"
        )
        return CommunicationOutcome(
            messages={"row": self.row_message, "column": self.column_message},
            sender_credibility={
                "row": self.row_credibility,
                "column": self.column_credibility,
            },
            row_update=row_update,
            column_update=column_update,
        )


@dataclass(frozen=True)
class ReputationEvidence:
    """Soft evidence that a subject took the cooperative action."""

    round_index: int
    cooperative_probability: float
    weight: float = 1.0
    source: str = "direct_monitoring"
    signal: str = ""

    def __post_init__(self) -> None:
        if self.round_index < 0:
            raise ValueError("round_index must be non-negative")
        if not 0.0 <= self.cooperative_probability <= 1.0:
            raise ValueError("cooperative_probability must be between zero and one")
        if self.weight < 0:
            raise ValueError("evidence weight must be non-negative")

    def record(self) -> dict[str, object]:
        return {
            "round_index": self.round_index,
            "cooperative_probability": self.cooperative_probability,
            "competitive_probability": 1.0 - self.cooperative_probability,
            "weight": self.weight,
            "source": self.source,
            "signal": self.signal,
        }


@dataclass(frozen=True)
class BetaReputation:
    """A decaying Beta posterior over a player's probability of cooperation."""

    alpha: float = 1.0
    beta: float = 1.0
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    decay: float = 1.0
    evidence: tuple[ReputationEvidence, ...] = ()

    def __post_init__(self) -> None:
        if self.alpha <= 0 or self.beta <= 0:
            raise ValueError("reputation parameters must be positive")
        if self.prior_alpha <= 0 or self.prior_beta <= 0:
            raise ValueError("reputation prior parameters must be positive")
        if self.alpha < self.prior_alpha or self.beta < self.prior_beta:
            raise ValueError("posterior parameters cannot be below the prior")
        if not 0.0 <= self.decay <= 1.0:
            raise ValueError("reputation decay must be between zero and one")

    @property
    def cooperation_probability(self) -> float:
        return self.alpha / (self.alpha + self.beta)

    @property
    def variance(self) -> float:
        total = self.alpha + self.beta
        return self.alpha * self.beta / (total * total * (total + 1.0))

    @property
    def effective_evidence(self) -> float:
        return (self.alpha - self.prior_alpha) + (self.beta - self.prior_beta)

    def update(self, observation: ReputationEvidence) -> BetaReputation:
        retained_alpha = self.prior_alpha + self.decay * (self.alpha - self.prior_alpha)
        retained_beta = self.prior_beta + self.decay * (self.beta - self.prior_beta)
        return BetaReputation(
            alpha=retained_alpha + observation.weight * observation.cooperative_probability,
            beta=retained_beta + observation.weight * (1.0 - observation.cooperative_probability),
            prior_alpha=self.prior_alpha,
            prior_beta=self.prior_beta,
            decay=self.decay,
            evidence=self.evidence + (observation,),
        )

    def action_belief(self, cooperative_action: str, competitive_action: str) -> ActionBelief:
        return ActionBelief.binary(
            cooperative_action,
            competitive_action,
            competitive_probability=1.0 - self.cooperation_probability,
        )

    def record(self) -> dict[str, object]:
        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "prior_alpha": self.prior_alpha,
            "prior_beta": self.prior_beta,
            "decay": self.decay,
            "cooperation_probability": self.cooperation_probability,
            "posterior_variance": self.variance,
            "effective_evidence": self.effective_evidence,
            "evidence": [item.record() for item in self.evidence],
        }


@dataclass(frozen=True)
class ReputationLedger:
    """Public or private player-specific reputation state."""

    row: BetaReputation = field(default_factory=BetaReputation)
    column: BetaReputation = field(default_factory=BetaReputation)

    def for_player(self, player: Player) -> BetaReputation:
        return self.row if player == "row" else self.column

    def update(self, subject: Player, observation: ReputationEvidence) -> ReputationLedger:
        if subject == "row":
            return ReputationLedger(row=self.row.update(observation), column=self.column)
        return ReputationLedger(row=self.row, column=self.column.update(observation))

    def asymmetric_beliefs(self, game: SymmetricTwoByTwoGame) -> AsymmetricBeliefs:
        return AsymmetricBeliefs(
            row_about_column=self.column.action_belief(
                game.cooperative_action, game.competitive_action
            ),
            column_about_row=self.row.action_belief(
                game.cooperative_action, game.competitive_action
            ),
        )

    def record(self) -> dict[str, object]:
        return {"row": self.row.record(), "column": self.column.record()}


@dataclass(frozen=True)
class ObedienceConstraint:
    """One conditional no-deviation constraint for a mediator recommendation."""

    player: Player
    recommended_action: str
    alternative_action: str | None
    recommendation_probability: float
    obey_utility: float
    deviation_utility: float
    obedience_margin: float

    @property
    def satisfied(self) -> bool:
        return self.obedience_margin >= -1e-9

    def record(self) -> dict[str, object]:
        return {
            "player": self.player,
            "recommended_action": self.recommended_action,
            "alternative_action": self.alternative_action,
            "recommendation_probability": self.recommendation_probability,
            "obey_utility": self.obey_utility,
            "deviation_utility": self.deviation_utility,
            "obedience_margin": self.obedience_margin,
            "satisfied": self.satisfied,
        }


@dataclass(frozen=True)
class MediationAnalysis:
    mechanism_id: str
    recommendation_distribution: Mapping[Profile, float]
    constraints: tuple[ObedienceConstraint, ...]
    objective: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "recommendation_distribution",
            MappingProxyType(dict(self.recommendation_distribution)),
        )

    @property
    def is_correlated_equilibrium(self) -> bool:
        return all(constraint.satisfied for constraint in self.constraints)

    @property
    def maximum_deviation_gain(self) -> float:
        return max((-constraint.obedience_margin for constraint in self.constraints), default=0.0)

    def record(self) -> dict[str, object]:
        return {
            "mechanism_id": self.mechanism_id,
            "objective": self.objective,
            "recommendation_distribution": [
                {"profile": profile, "probability": probability}
                for profile, probability in self.recommendation_distribution.items()
            ],
            "constraints": [constraint.record() for constraint in self.constraints],
            "is_correlated_equilibrium": self.is_correlated_equilibrium,
            "maximum_deviation_gain": self.maximum_deviation_gain,
        }


@dataclass(frozen=True)
class MediatorDraw:
    seed: int
    random_draw: float
    row_recommendation: str
    column_recommendation: str

    @property
    def profile(self) -> Profile:
        return self.row_recommendation, self.column_recommendation

    def private_record(self, player: Player) -> dict[str, object]:
        recommendation = self.row_recommendation if player == "row" else self.column_recommendation
        return {
            "mechanism_id": "trusted_mediator",
            "player": player,
            "private_recommendation": recommendation,
            "seed": self.seed,
        }

    def audit_record(self) -> dict[str, object]:
        return {
            "mechanism_id": "trusted_mediator",
            "seed": self.seed,
            "random_draw": self.random_draw,
            "joint_recommendation": self.profile,
        }


@dataclass(frozen=True)
class TrustedMediator:
    """Privately recommend a joint action and audit incentive compatibility."""

    distribution: Mapping[Profile, float]
    objective: str = "declared_distribution"
    mechanism_id: str = "trusted_mediator"

    def __post_init__(self) -> None:
        if not self.distribution:
            raise ValueError("mediator distribution cannot be empty")
        if any(probability < 0 or probability > 1 for probability in self.distribution.values()):
            raise ValueError("mediator probabilities must be between zero and one")
        if not isclose(sum(self.distribution.values()), 1.0, abs_tol=1e-9):
            raise ValueError("mediator probabilities must sum to one")
        object.__setattr__(self, "distribution", MappingProxyType(dict(self.distribution)))

    def analyze(self, game: MechanismInput) -> MediationAnalysis:
        application = as_application(game)
        if not set(self.distribution) <= set(application.allowed_profiles):
            raise ValueError("mediator can only recommend profiles allowed by prior mechanisms")

        constraints: list[ObedienceConstraint] = []
        for player in ("row", "column"):
            player_index = 0 if player == "row" else 1
            opponent_index = 1 - player_index
            for recommendation in application.permitted_actions[player]:
                relevant = {
                    profile: probability
                    for profile, probability in self.distribution.items()
                    if profile[player_index] == recommendation and probability > 0
                }
                recommendation_probability = sum(relevant.values())
                if recommendation_probability <= 0:
                    continue
                alternatives = tuple(
                    action
                    for action in application.permitted_actions[player]
                    if action != recommendation
                )
                if not alternatives:
                    obey = sum(
                        probability
                        * application.utility(player, recommendation, profile[opponent_index])
                        for profile, probability in relevant.items()
                    ) / recommendation_probability
                    constraints.append(
                        ObedienceConstraint(
                            player=player,
                            recommended_action=recommendation,
                            alternative_action=None,
                            recommendation_probability=recommendation_probability,
                            obey_utility=obey,
                            deviation_utility=obey,
                            obedience_margin=0.0,
                        )
                    )
                    continue
                for alternative in alternatives:
                    obey = sum(
                        probability
                        * application.utility(player, recommendation, profile[opponent_index])
                        for profile, probability in relevant.items()
                    ) / recommendation_probability
                    deviate = sum(
                        probability
                        * application.utility(player, alternative, profile[opponent_index])
                        for profile, probability in relevant.items()
                    ) / recommendation_probability
                    constraints.append(
                        ObedienceConstraint(
                            player=player,
                            recommended_action=recommendation,
                            alternative_action=alternative,
                            recommendation_probability=recommendation_probability,
                            obey_utility=obey,
                            deviation_utility=deviate,
                            obedience_margin=obey - deviate,
                        )
                    )
        return MediationAnalysis(
            mechanism_id=self.mechanism_id,
            recommendation_distribution=self.distribution,
            constraints=tuple(constraints),
            objective=self.objective,
        )

    def draw(self, *, seed: int) -> MediatorDraw:
        draw = Random(seed).random()
        cumulative = 0.0
        selected = next(iter(self.distribution))
        for profile, probability in self.distribution.items():
            cumulative += probability
            selected = profile
            if draw <= cumulative:
                break
        return MediatorDraw(
            seed=seed,
            random_draw=draw,
            row_recommendation=selected[0],
            column_recommendation=selected[1],
        )


def fair_welfare_mediator(game: MechanismInput) -> TrustedMediator:
    """Distribute recommendations uniformly over utilitarian optima."""
    application = as_application(game)
    welfare = {
        profile: application.payoff(profile).total
        for profile in application.allowed_profiles
    }
    maximum = max(welfare.values())
    optima = tuple(profile for profile, value in welfare.items() if isclose(value, maximum, abs_tol=1e-9))
    probability = 1.0 / len(optima)
    return TrustedMediator(
        {profile: probability for profile in optima},
        objective="uniform_over_utilitarian_optima",
    )


@dataclass(frozen=True)
class InstitutionalEnvironment:
    """Complete output of a composable institutional mechanism stack."""

    game: MechanismApplication
    communication: CommunicationOutcome | None = None
    mediation: MediationAnalysis | None = None
    reputation: ReputationLedger | None = None

    def record(self) -> dict[str, object]:
        return {
            "adjusted_game": self.game.record(),
            "communication": self.communication.record() if self.communication else None,
            "mediation": self.mediation.record() if self.mediation else None,
            "reputation": self.reputation.record() if self.reputation else None,
        }


@dataclass(frozen=True)
class MechanismStack:
    """Compose payoff, information, mediation, and reputation mechanisms."""

    payoff_mechanisms: tuple[Mechanism, ...] = ()
    communication: NonBindingCommunication | None = None
    mediator: TrustedMediator | None = None

    def apply(
        self,
        game: SymmetricTwoByTwoGame,
        *,
        priors: AsymmetricBeliefs | None = None,
        reputation: ReputationLedger | None = None,
    ) -> InstitutionalEnvironment:
        application = as_application(game)
        for mechanism in self.payoff_mechanisms:
            application = mechanism.apply(application)
        if self.communication is not None and priors is None:
            raise ValueError("communication requires player-specific prior beliefs")
        communication = self.communication.run(priors) if self.communication is not None and priors else None
        mediation = self.mediator.analyze(application) if self.mediator is not None else None
        return InstitutionalEnvironment(
            game=application,
            communication=communication,
            mediation=mediation,
            reputation=reputation,
        )

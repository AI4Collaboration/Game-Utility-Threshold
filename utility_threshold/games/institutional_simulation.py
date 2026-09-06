"""Repeated play with latent payoffs and realized institutional events."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Mapping, Protocol

from .base import Payoff, Player, Profile
from .beliefs import ActionBelief, AsymmetricBeliefs, imperfect_monitoring_model
from .decision import ExpectedValueCriterion, RiskCriterion, RiskEvaluation
from .institutions import (
    MechanismStack,
    MediatorDraw,
    ReputationEvidence,
    ReputationLedger,
)
from .mechanisms import (
    BindingCommitment,
    ContractPenalty,
    MechanismApplication,
    SidePaymentMechanism,
)
from .uncertainty import DiscreteDistribution, PayoffState, UncertainPayoffGame, WeightedOutcome


@dataclass(frozen=True)
class InstitutionalChoice:
    action: str
    criterion: str
    action_evaluations: Mapping[str, RiskEvaluation]
    catastrophe_probabilities: Mapping[str, float]
    optimal_actions: tuple[str, ...]
    mediator_recommendation: str | None
    obeyed_mediator: bool
    decision_basis: str

    def record(self) -> dict[str, object]:
        return {
            "action": self.action,
            "criterion": self.criterion,
            "action_evaluations": {
                action: evaluation.record()
                for action, evaluation in self.action_evaluations.items()
            },
            "catastrophe_probabilities": dict(self.catastrophe_probabilities),
            "optimal_actions": self.optimal_actions,
            "mediator_recommendation": self.mediator_recommendation,
            "obeyed_mediator": self.obeyed_mediator,
            "decision_basis": self.decision_basis,
        }


@dataclass(frozen=True)
class InstitutionalRoundContext:
    uncertain_game: UncertainPayoffGame
    state_applications: tuple[tuple[PayoffState, MechanismApplication], ...]
    player: Player
    round_index: int
    opponent_belief: ActionBelief
    reputation: ReputationLedger
    mediator_recommendation: str | None
    history: tuple[InstitutionalRoundResult, ...]

    @property
    def permitted_actions(self) -> tuple[str, ...]:
        return self.state_applications[0][1].permitted_actions[self.player]


class InstitutionalStrategy(Protocol):
    def choose(self, context: InstitutionalRoundContext, rng: Random) -> InstitutionalChoice: ...


@dataclass(frozen=True)
class RiskAwareInstitutionalStrategy:
    """Evaluate exact payoff lotteries under a player-specific action belief."""

    criterion: RiskCriterion = field(default_factory=ExpectedValueCriterion)
    follow_mediator: bool = True

    def choose(self, context: InstitutionalRoundContext, rng: Random) -> InstitutionalChoice:
        _ = rng
        lotteries: dict[str, DiscreteDistribution[float]] = {}
        evaluations: dict[str, RiskEvaluation] = {}
        catastrophe_probabilities: dict[str, float] = {}
        for own_action in context.permitted_actions:
            outcomes: list[WeightedOutcome[float]] = []
            catastrophe_probability = 0.0
            for state, application in context.state_applications:
                for opponent_action in context.uncertain_game.actions:
                    probability = state.probability * context.opponent_belief.probability(opponent_action)
                    outcomes.append(
                        WeightedOutcome(
                            label=f"{state.state_id}:{opponent_action}",
                            probability=probability,
                            value=application.utility(
                                context.player, own_action, opponent_action
                            ),
                            metadata={
                                "state_id": state.state_id,
                                "opponent_action": opponent_action,
                            },
                        )
                    )
                    profile = (
                        (own_action, opponent_action)
                        if context.player == "row"
                        else (opponent_action, own_action)
                    )
                    if profile in state.game.catastrophic_profiles:
                        catastrophe_probability += probability
            lottery = DiscreteDistribution(tuple(outcomes))
            lotteries[own_action] = lottery
            evaluations[own_action] = self.criterion.evaluate(lottery)
            catastrophe_probabilities[own_action] = catastrophe_probability

        maximum = max(evaluation.score for evaluation in evaluations.values())
        optimal = tuple(
            action
            for action in context.permitted_actions
            if evaluations[action].score >= maximum - 1e-9
        )
        selected = (
            context.uncertain_game.cooperative_action
            if context.uncertain_game.cooperative_action in optimal
            else optimal[0]
        )
        obeyed = False
        basis = "risk_adjusted_best_response"
        recommendation = context.mediator_recommendation
        if self.follow_mediator and recommendation is not None:
            if recommendation not in context.permitted_actions:
                raise ValueError("mediator recommended an action prohibited by a commitment")
            selected = recommendation
            obeyed = True
            basis = "trusted_mediator_recommendation"
        return InstitutionalChoice(
            action=selected,
            criterion=self.criterion.name,
            action_evaluations=evaluations,
            catastrophe_probabilities=catastrophe_probabilities,
            optimal_actions=optimal,
            mediator_recommendation=recommendation,
            obeyed_mediator=obeyed,
            decision_basis=basis,
        )


@dataclass(frozen=True)
class FixedInstitutionalStrategy:
    """Always select one semantic action, useful as an experimental control."""

    action_kind: str

    def __post_init__(self) -> None:
        if self.action_kind not in {"cooperative", "competitive"}:
            raise ValueError("action_kind must be cooperative or competitive")

    def choose(self, context: InstitutionalRoundContext, rng: Random) -> InstitutionalChoice:
        _ = rng
        action = (
            context.uncertain_game.cooperative_action
            if self.action_kind == "cooperative"
            else context.uncertain_game.competitive_action
        )
        if action not in context.permitted_actions:
            raise ValueError(f"fixed strategy action {action!r} is prohibited")
        return InstitutionalChoice(
            action=action,
            criterion="fixed_control",
            action_evaluations={},
            catastrophe_probabilities={},
            optimal_actions=(action,),
            mediator_recommendation=context.mediator_recommendation,
            obeyed_mediator=False,
            decision_basis=f"fixed_{self.action_kind}_control",
        )


@dataclass(frozen=True)
class PenaltyEvent:
    player: Player
    mechanism_index: int
    deviated: bool
    signal_probability: float
    detection_draw: float
    violation_signalled: bool
    false_positive: bool
    enforcement_probability: float
    enforcement_draw: float | None
    enforced: bool
    penalty: float

    def record(self) -> dict[str, object]:
        return {
            "player": self.player,
            "mechanism_index": self.mechanism_index,
            "deviated": self.deviated,
            "signal_probability": self.signal_probability,
            "detection_draw": self.detection_draw,
            "violation_signalled": self.violation_signalled,
            "false_positive": self.false_positive,
            "enforcement_probability": self.enforcement_probability,
            "enforcement_draw": self.enforcement_draw,
            "enforced": self.enforced,
            "penalty": self.penalty,
        }


@dataclass(frozen=True)
class MonitoringEvent:
    observer: Player
    subject: Player
    actual_action: str
    random_draw: float
    signal: str
    likelihood: float
    belief_update: Mapping[str, object]

    def record(self) -> dict[str, object]:
        return {
            "observer": self.observer,
            "subject": self.subject,
            "actual_action": self.actual_action,
            "random_draw": self.random_draw,
            "signal": self.signal,
            "likelihood": self.likelihood,
            "belief_update": dict(self.belief_update),
        }


@dataclass(frozen=True)
class InstitutionalRoundResult:
    round_index: int
    state_id: str
    state_probability: float
    state_draw: float
    row_choice: InstitutionalChoice
    column_choice: InstitutionalChoice
    base_payoff: Payoff
    transfers: Payoff
    penalties: Payoff
    realized_payoff: Payoff
    catastrophic: bool
    penalty_events: tuple[PenaltyEvent, ...]
    monitoring_events: tuple[MonitoringEvent, ...]
    beliefs_before: AsymmetricBeliefs
    decision_beliefs: AsymmetricBeliefs
    beliefs_after: AsymmetricBeliefs
    reputation_after: ReputationLedger
    mediator_draw: MediatorDraw | None
    communication_record: Mapping[str, object] | None

    @property
    def profile(self) -> Profile:
        return self.row_choice.action, self.column_choice.action

    def record(self) -> dict[str, object]:
        return {
            "round_index": self.round_index,
            "state_id": self.state_id,
            "state_probability": self.state_probability,
            "state_draw": self.state_draw,
            "row_choice": self.row_choice.record(),
            "column_choice": self.column_choice.record(),
            "profile": self.profile,
            "base_payoff": {"row": self.base_payoff.row, "column": self.base_payoff.column},
            "transfers": {"row": self.transfers.row, "column": self.transfers.column},
            "penalties": {"row": self.penalties.row, "column": self.penalties.column},
            "realized_payoff": {
                "row": self.realized_payoff.row,
                "column": self.realized_payoff.column,
            },
            "catastrophic": self.catastrophic,
            "penalty_events": [event.record() for event in self.penalty_events],
            "monitoring_events": [event.record() for event in self.monitoring_events],
            "beliefs_before": self.beliefs_before.record(),
            "communication": dict(self.communication_record) if self.communication_record else None,
            "decision_beliefs": self.decision_beliefs.record(),
            "beliefs_after": self.beliefs_after.record(),
            "reputation_after": self.reputation_after.record(),
            "mediator": self.mediator_draw.audit_record() if self.mediator_draw else None,
        }


@dataclass(frozen=True)
class InstitutionalMatchResult:
    game_id: str
    row_strategy: str
    column_strategy: str
    seed: int
    rules: Mapping[str, object]
    rounds: tuple[InstitutionalRoundResult, ...]

    @property
    def row_total_utility(self) -> float:
        return sum(result.realized_payoff.row for result in self.rounds)

    @property
    def column_total_utility(self) -> float:
        return sum(result.realized_payoff.column for result in self.rounds)

    @property
    def catastrophe_rate(self) -> float:
        return sum(result.catastrophic for result in self.rounds) / len(self.rounds)

    @property
    def row_competitive_rate(self) -> float:
        return sum(
            result.row_choice.action == self.rules["competitive_action"]
            for result in self.rounds
        ) / len(self.rounds)

    @property
    def column_competitive_rate(self) -> float:
        return sum(
            result.column_choice.action == self.rules["competitive_action"]
            for result in self.rounds
        ) / len(self.rounds)

    def record(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "row_strategy": self.row_strategy,
            "column_strategy": self.column_strategy,
            "seed": self.seed,
            "round_count": len(self.rounds),
            "row_total_utility": self.row_total_utility,
            "column_total_utility": self.column_total_utility,
            "catastrophe_rate": self.catastrophe_rate,
            "row_competitive_rate": self.row_competitive_rate,
            "column_competitive_rate": self.column_competitive_rate,
            "rules": dict(self.rules),
            "rounds": [result.record() for result in self.rounds],
        }


@dataclass(frozen=True)
class InstitutionalRules:
    stack: MechanismStack = field(default_factory=MechanismStack)
    monitoring_true_positive_rate: float = 0.85
    monitoring_false_positive_rate: float = 0.10
    reputation_evidence_weight: float = 1.0

    def __post_init__(self) -> None:
        for value in (
            self.monitoring_true_positive_rate,
            self.monitoring_false_positive_rate,
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError("monitoring rates must be between zero and one")
        if self.reputation_evidence_weight < 0:
            raise ValueError("reputation_evidence_weight must be non-negative")

    def record(self, game: UncertainPayoffGame) -> dict[str, object]:
        return {
            "competitive_action": game.competitive_action,
            "payoff_mechanisms": [
                getattr(mechanism, "mechanism_id", type(mechanism).__name__)
                for mechanism in self.stack.payoff_mechanisms
            ],
            "communication": self.stack.communication.mechanism_id if self.stack.communication else None,
            "mediator": self.stack.mediator.mechanism_id if self.stack.mediator else None,
            "monitoring_true_positive_rate": self.monitoring_true_positive_rate,
            "monitoring_false_positive_rate": self.monitoring_false_positive_rate,
            "reputation_evidence_weight": self.reputation_evidence_weight,
        }


def _state_applications(
    game: UncertainPayoffGame,
    stack: MechanismStack,
) -> tuple[tuple[PayoffState, MechanismApplication], ...]:
    applications: list[tuple[PayoffState, MechanismApplication]] = []
    permitted: Mapping[Player, tuple[str, ...]] | None = None
    for state in game.states:
        application = MechanismApplication.baseline(state.game)
        for mechanism in stack.payoff_mechanisms:
            application = mechanism.apply(application)
        if permitted is not None and application.permitted_actions != permitted:
            raise ValueError("mechanisms must permit the same actions in every payoff state")
        permitted = application.permitted_actions
        if stack.mediator is not None:
            stack.mediator.analyze(application)
        applications.append((state, application))
    return tuple(applications)


def _draw_state(game: UncertainPayoffGame, rng: Random) -> tuple[PayoffState, float]:
    draw = rng.random()
    cumulative = 0.0
    selected = game.states[-1]
    for state in game.states:
        cumulative += state.probability
        if draw <= cumulative:
            selected = state
            break
    return selected, draw


def _realize_mechanisms(
    profile: Profile,
    mechanisms: tuple[Mechanism, ...],
    rng: Random,
) -> tuple[Payoff, Payoff, tuple[PenaltyEvent, ...]]:
    transfers = Payoff(0.0, 0.0)
    row_penalty = 0.0
    column_penalty = 0.0
    penalty_events: list[PenaltyEvent] = []
    for index, mechanism in enumerate(mechanisms):
        if isinstance(mechanism, BindingCommitment):
            continue
        if isinstance(mechanism, SidePaymentMechanism):
            transfer = mechanism.transfers[profile]
            transfers = Payoff(
                transfers.row + transfer.row,
                transfers.column + transfer.column,
            )
            continue
        if not isinstance(mechanism, ContractPenalty):
            raise TypeError(
                f"institutional simulation cannot realize {type(mechanism).__name__}"
            )
        for player, action_index in (("row", 0), ("column", 1)):
            deviated = profile[action_index] != mechanism.agreed_profile[action_index]
            signal_probability = (
                mechanism.deviation_detection_probability
                if deviated
                else mechanism.false_positive_probability
            )
            detection_draw = rng.random()
            signalled = detection_draw < signal_probability
            enforcement_draw = rng.random() if signalled else None
            enforced = bool(
                signalled
                and enforcement_draw is not None
                and enforcement_draw < mechanism.enforcement_probability
            )
            amount = mechanism.penalty if enforced else 0.0
            if player == "row":
                row_penalty += amount
            else:
                column_penalty += amount
            penalty_events.append(
                PenaltyEvent(
                    player=player,
                    mechanism_index=index,
                    deviated=deviated,
                    signal_probability=signal_probability,
                    detection_draw=detection_draw,
                    violation_signalled=signalled,
                    false_positive=signalled and not deviated,
                    enforcement_probability=mechanism.enforcement_probability,
                    enforcement_draw=enforcement_draw,
                    enforced=enforced,
                    penalty=amount,
                )
            )
    return transfers, Payoff(row_penalty, column_penalty), tuple(penalty_events)


def _monitor(
    *,
    observer: Player,
    subject: Player,
    actual_action: str,
    prior: ActionBelief,
    game: UncertainPayoffGame,
    true_positive_rate: float,
    false_positive_rate: float,
    rng: Random,
) -> tuple[MonitoringEvent, ActionBelief]:
    model = imperfect_monitoring_model(
        game.cooperative_action,
        game.competitive_action,
        true_positive_rate=true_positive_rate,
        false_positive_rate=false_positive_rate,
    )
    draw = rng.random()
    first_signal = model.signals[0]
    first_probability = model.likelihood(first_signal, actual_action)
    signal = first_signal if draw < first_probability else model.signals[1]
    update = model.observe(prior, signal)
    return (
        MonitoringEvent(
            observer=observer,
            subject=subject,
            actual_action=actual_action,
            random_draw=draw,
            signal=signal,
            likelihood=model.likelihood(signal, actual_action),
            belief_update=update.record(),
        ),
        update.posterior,
    )


def play_institutional_match(
    game: UncertainPayoffGame,
    row_strategy: InstitutionalStrategy,
    column_strategy: InstitutionalStrategy,
    *,
    rules: InstitutionalRules = InstitutionalRules(),
    rounds: int = 100,
    seed: int = 0,
    initial_beliefs: AsymmetricBeliefs | None = None,
    initial_reputation: ReputationLedger = ReputationLedger(),
    row_name: str | None = None,
    column_name: str | None = None,
) -> InstitutionalMatchResult:
    """Play repeated simultaneous rounds and retain every stochastic draw."""

    if rounds <= 0:
        raise ValueError("rounds must be positive")
    neutral = ActionBelief.binary(
        game.cooperative_action,
        game.competitive_action,
        competitive_probability=0.5,
    )
    beliefs = initial_beliefs or AsymmetricBeliefs(neutral, neutral)
    if beliefs.row_about_column.actions != game.actions:
        raise ValueError("initial beliefs must match the game actions")
    applications = _state_applications(game, rules.stack)
    rng = Random(seed)
    reputation = initial_reputation
    history: list[InstitutionalRoundResult] = []

    for round_index in range(rounds):
        beliefs_before = beliefs
        communication = (
            rules.stack.communication.run(beliefs_before)
            if rules.stack.communication is not None
            else None
        )
        decision_beliefs = communication.posteriors if communication else beliefs_before
        mediator_draw = (
            rules.stack.mediator.draw(seed=rng.randrange(0, 2**63))
            if rules.stack.mediator is not None
            else None
        )
        frozen_history = tuple(history)
        row_choice = row_strategy.choose(
            InstitutionalRoundContext(
                uncertain_game=game,
                state_applications=applications,
                player="row",
                round_index=round_index,
                opponent_belief=decision_beliefs.row_about_column,
                reputation=reputation,
                mediator_recommendation=(
                    mediator_draw.row_recommendation if mediator_draw else None
                ),
                history=frozen_history,
            ),
            rng,
        )
        column_choice = column_strategy.choose(
            InstitutionalRoundContext(
                uncertain_game=game,
                state_applications=applications,
                player="column",
                round_index=round_index,
                opponent_belief=decision_beliefs.column_about_row,
                reputation=reputation,
                mediator_recommendation=(
                    mediator_draw.column_recommendation if mediator_draw else None
                ),
                history=frozen_history,
            ),
            rng,
        )
        profile = (row_choice.action, column_choice.action)
        if profile not in applications[0][1].allowed_profiles:
            raise ValueError(f"strategies produced prohibited profile {profile!r}")

        state, state_draw = _draw_state(game, rng)
        base_payoff = state.game.payoff(profile)
        transfers, penalties, penalty_events = _realize_mechanisms(
            profile, rules.stack.payoff_mechanisms, rng
        )
        realized = Payoff(
            base_payoff.row + transfers.row - penalties.row,
            base_payoff.column + transfers.column - penalties.column,
        )

        row_monitoring, row_posterior = _monitor(
            observer="row",
            subject="column",
            actual_action=column_choice.action,
            prior=decision_beliefs.row_about_column,
            game=game,
            true_positive_rate=rules.monitoring_true_positive_rate,
            false_positive_rate=rules.monitoring_false_positive_rate,
            rng=rng,
        )
        column_monitoring, column_posterior = _monitor(
            observer="column",
            subject="row",
            actual_action=row_choice.action,
            prior=decision_beliefs.column_about_row,
            game=game,
            true_positive_rate=rules.monitoring_true_positive_rate,
            false_positive_rate=rules.monitoring_false_positive_rate,
            rng=rng,
        )
        beliefs = AsymmetricBeliefs(row_posterior, column_posterior)
        reputation = reputation.update(
            "column",
            ReputationEvidence(
                round_index,
                row_posterior.probability(game.cooperative_action),
                rules.reputation_evidence_weight,
                "imperfect_monitoring",
                row_monitoring.signal,
            ),
        ).update(
            "row",
            ReputationEvidence(
                round_index,
                column_posterior.probability(game.cooperative_action),
                rules.reputation_evidence_weight,
                "imperfect_monitoring",
                column_monitoring.signal,
            ),
        )
        history.append(
            InstitutionalRoundResult(
                round_index=round_index,
                state_id=state.state_id,
                state_probability=state.probability,
                state_draw=state_draw,
                row_choice=row_choice,
                column_choice=column_choice,
                base_payoff=base_payoff,
                transfers=transfers,
                penalties=penalties,
                realized_payoff=realized,
                catastrophic=profile in state.game.catastrophic_profiles,
                penalty_events=penalty_events,
                monitoring_events=(row_monitoring, column_monitoring),
                beliefs_before=beliefs_before,
                decision_beliefs=decision_beliefs,
                beliefs_after=beliefs,
                reputation_after=reputation,
                mediator_draw=mediator_draw,
                communication_record=communication.record() if communication else None,
            )
        )
    return InstitutionalMatchResult(
        game_id=game.game_id,
        row_strategy=row_name or type(row_strategy).__name__,
        column_strategy=column_name or type(column_strategy).__name__,
        seed=seed,
        rules=rules.record(game),
        rounds=tuple(history),
    )

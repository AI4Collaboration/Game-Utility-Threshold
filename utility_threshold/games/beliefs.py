"""Bayesian action beliefs, communication signals, and imperfect monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, log
from types import MappingProxyType
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ActionBelief:
    """A probability distribution over another player's available actions."""

    actions: tuple[str, ...]
    probabilities: Mapping[str, float]

    def __post_init__(self) -> None:
        if not self.actions or len(self.actions) != len(set(self.actions)):
            raise ValueError("belief actions must be non-empty and unique")
        if set(self.probabilities) != set(self.actions):
            raise ValueError("belief must assign a probability to every action")
        if any(probability < 0 or probability > 1 for probability in self.probabilities.values()):
            raise ValueError("belief probabilities must be between zero and one")
        if not isclose(sum(self.probabilities.values()), 1.0, abs_tol=1e-9):
            raise ValueError("belief probabilities must sum to one")
        object.__setattr__(self, "probabilities", MappingProxyType(dict(self.probabilities)))

    @classmethod
    def binary(cls, cooperative_action: str, competitive_action: str, competitive_probability: float) -> ActionBelief:
        if not 0.0 <= competitive_probability <= 1.0:
            raise ValueError("competitive_probability must be between zero and one")
        return cls(
            actions=(cooperative_action, competitive_action),
            probabilities={
                cooperative_action: 1.0 - competitive_probability,
                competitive_action: competitive_probability,
            },
        )

    @property
    def entropy(self) -> float:
        return -sum(
            probability * log(probability)
            for probability in self.probabilities.values()
            if probability > 0
        )

    def probability(self, action: str) -> float:
        try:
            return self.probabilities[action]
        except KeyError as exc:
            raise ValueError(f"unknown action {action!r}") from exc

    def record(self) -> dict[str, object]:
        return {
            "actions": self.actions,
            "probabilities": dict(self.probabilities),
            "entropy_nats": self.entropy,
        }


@dataclass(frozen=True)
class SignalModel:
    """Likelihood model ``P(signal | opponent action)``."""

    actions: tuple[str, ...]
    signals: tuple[str, ...]
    likelihoods: Mapping[tuple[str, str], float]
    model_id: str = "signal_model"
    description: str = ""

    def __post_init__(self) -> None:
        if not self.actions or len(self.actions) != len(set(self.actions)):
            raise ValueError("signal model actions must be non-empty and unique")
        if not self.signals or len(self.signals) != len(set(self.signals)):
            raise ValueError("signal model signals must be non-empty and unique")
        expected = {(signal, action) for signal in self.signals for action in self.actions}
        if set(self.likelihoods) != expected:
            raise ValueError("likelihood table must contain every signal-action pair")
        if any(value < 0 or value > 1 for value in self.likelihoods.values()):
            raise ValueError("signal likelihoods must be between zero and one")
        for action in self.actions:
            total = sum(self.likelihoods[(signal, action)] for signal in self.signals)
            if not isclose(total, 1.0, abs_tol=1e-9):
                raise ValueError(f"signal likelihoods conditional on {action!r} must sum to one")
        object.__setattr__(self, "likelihoods", MappingProxyType(dict(self.likelihoods)))

    def likelihood(self, signal: str, action: str) -> float:
        try:
            return self.likelihoods[(signal, action)]
        except KeyError as exc:
            raise ValueError(f"unknown signal-action pair {(signal, action)!r}") from exc

    def observe(self, prior: ActionBelief, signal: str) -> BeliefUpdate:
        if prior.actions != self.actions:
            raise ValueError("prior and signal model actions must match in the same order")
        if signal not in self.signals:
            raise ValueError(f"unknown signal {signal!r}")
        unnormalized = {
            action: prior.probability(action) * self.likelihood(signal, action)
            for action in self.actions
        }
        evidence = sum(unnormalized.values())
        if evidence <= 0:
            raise ValueError("signal has zero probability under the prior")
        posterior = ActionBelief(
            self.actions,
            {action: mass / evidence for action, mass in unnormalized.items()},
        )
        information_gain = sum(
            probability * log(probability / prior.probability(action))
            for action, probability in posterior.probabilities.items()
            if probability > 0 and prior.probability(action) > 0
        )
        return BeliefUpdate(
            model_id=self.model_id,
            signal=signal,
            prior=prior,
            posterior=posterior,
            signal_likelihoods=MappingProxyType({
                action: self.likelihood(signal, action) for action in self.actions
            }),
            evidence_probability=evidence,
            information_gain_nats=information_gain,
        )

    def record(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "description": self.description,
            "actions": self.actions,
            "signals": self.signals,
            "likelihoods": [
                {"signal": signal, "action": action, "probability": self.likelihood(signal, action)}
                for signal in self.signals
                for action in self.actions
            ],
        }


@dataclass(frozen=True)
class BeliefUpdate:
    model_id: str
    signal: str
    prior: ActionBelief
    posterior: ActionBelief
    signal_likelihoods: Mapping[str, float]
    evidence_probability: float
    information_gain_nats: float

    def record(self) -> dict[str, object]:
        return {
            "model_id": self.model_id,
            "signal": self.signal,
            "signal_likelihoods": dict(self.signal_likelihoods),
            "evidence_probability": self.evidence_probability,
            "information_gain_nats": self.information_gain_nats,
            "prior": self.prior.record(),
            "posterior": self.posterior.record(),
            "entropy_reduction_nats": self.prior.entropy - self.posterior.entropy,
        }


@dataclass(frozen=True)
class BeliefTracker:
    """Immutable sequential Bayesian update history."""

    initial: ActionBelief
    updates: tuple[BeliefUpdate, ...] = ()

    @property
    def current(self) -> ActionBelief:
        return self.updates[-1].posterior if self.updates else self.initial

    @property
    def cumulative_information_gain_nats(self) -> float:
        return sum(update.information_gain_nats for update in self.updates)

    def observe(self, model: SignalModel, signal: str) -> BeliefTracker:
        update = model.observe(self.current, signal)
        return BeliefTracker(self.initial, self.updates + (update,))

    def observe_many(self, observations: Iterable[tuple[SignalModel, str]]) -> BeliefTracker:
        tracker = self
        for model, signal in observations:
            tracker = tracker.observe(model, signal)
        return tracker

    def record(self) -> dict[str, object]:
        return {
            "initial": self.initial.record(),
            "updates": [update.record() for update in self.updates],
            "current": self.current.record(),
            "cumulative_information_gain_nats": self.cumulative_information_gain_nats,
        }


@dataclass(frozen=True)
class AsymmetricBeliefs:
    """Each player may hold a different belief about the other's next action."""

    row_about_column: ActionBelief
    column_about_row: ActionBelief

    def __post_init__(self) -> None:
        if self.row_about_column.actions != self.column_about_row.actions:
            raise ValueError("both players' beliefs must cover the same action set")

    def for_player(self, player: str) -> ActionBelief:
        if player == "row":
            return self.row_about_column
        if player == "column":
            return self.column_about_row
        raise ValueError("player must be row or column")

    def record(self) -> dict[str, object]:
        return {
            "row_about_column": self.row_about_column.record(),
            "column_about_row": self.column_about_row.record(),
        }


def binary_communication_model(
    cooperative_action: str,
    competitive_action: str,
    *,
    credibility: float,
) -> SignalModel:
    """A symmetric cheap-talk channel with truthful-message probability ``credibility``."""
    if not 0.0 <= credibility <= 1.0:
        raise ValueError("credibility must be between zero and one")
    actions = (cooperative_action, competitive_action)
    signals = tuple(f"MESSAGE_{action}" for action in actions)
    return SignalModel(
        actions=actions,
        signals=signals,
        likelihoods={
            (signals[0], cooperative_action): credibility,
            (signals[1], cooperative_action): 1.0 - credibility,
            (signals[0], competitive_action): 1.0 - credibility,
            (signals[1], competitive_action): credibility,
        },
        model_id="non_binding_communication",
        description="Cheap-talk message about intended action with calibrated credibility.",
    )


def imperfect_monitoring_model(
    cooperative_action: str,
    competitive_action: str,
    *,
    true_positive_rate: float,
    false_positive_rate: float,
) -> SignalModel:
    """Binary monitoring channel that may miss competition or raise false alarms."""
    if not 0.0 <= true_positive_rate <= 1.0 or not 0.0 <= false_positive_rate <= 1.0:
        raise ValueError("monitoring rates must be between zero and one")
    cooperative_signal = "SIGNAL_COOPERATIVE"
    competitive_signal = "SIGNAL_COMPETITIVE"
    return SignalModel(
        actions=(cooperative_action, competitive_action),
        signals=(cooperative_signal, competitive_signal),
        likelihoods={
            (cooperative_signal, cooperative_action): 1.0 - false_positive_rate,
            (competitive_signal, cooperative_action): false_positive_rate,
            (cooperative_signal, competitive_action): 1.0 - true_positive_rate,
            (competitive_signal, competitive_action): true_positive_rate,
        },
        model_id="imperfect_monitoring",
        description="Noisy observation of the opponent's cooperative or competitive action.",
    )

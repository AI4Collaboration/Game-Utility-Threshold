"""Baseline, probabilistic, and proof-carrying agents for the base game."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Protocol

from .core import Action, DecisionCertificate, GameParams, GameState, safety_margin, threshold_action, verify_threshold_decision


class Agent(Protocol):
    def choose(self, state: GameState, prm: GameParams) -> Action: ...


class CooperateBot:
    def choose(self, state: GameState, prm: GameParams) -> Action:
        return "COOPERATE"


class DefectBot:
    def choose(self, state: GameState, prm: GameParams) -> Action:
        return "ATTACK"


class ThresholdBot:
    def choose(self, state: GameState, prm: GameParams) -> Action:
        return threshold_action(state, prm)


@dataclass
class ProbabilisticThresholdBot:
    """A deterministic pseudo-random policy with a smooth threshold response."""

    temperature: float = 0.5
    seed: int = 0

    def attack_probability(self, state: GameState, prm: GameParams) -> float:
        if self.temperature <= 0:
            raise ValueError("temperature must be positive")
        scaled_margin = max(-60.0, min(60.0, safety_margin(state, prm) / self.temperature))
        return 1.0 / (1.0 + exp(scaled_margin))

    def choose(self, state: GameState, prm: GameParams) -> Action:
        # Stable reproducibility is important when comparing Inspect traces.
        draw = ((int(state.v * 1_000) * 31 + int(state.d * 1_000) * 17 + self.seed) % 10_000) / 10_000
        return "ATTACK" if draw < self.attack_probability(state, prm) else "COOPERATE"


class ProofCarryingThresholdBot:
    """A threshold agent that exposes its decision witness for each action."""

    certificate: DecisionCertificate | None = None

    def choose(self, state: GameState, prm: GameParams) -> Action:
        action = threshold_action(state, prm)
        self.certificate = verify_threshold_decision(state, prm, action)
        return action


class DUPOCVerifier(ProofCarryingThresholdBot):
    """Deterministic Utility Proof of Cooperation (DUPOC).

    The policy's primary audit claim is that cooperation is chosen exactly when
    its certified utility weakly exceeds attack utility. It still emits ATTACK
    in unsafe states, preventing a verifier label from hiding a bad margin.
    """


class CUPODVerifier(ProofCarryingThresholdBot):
    """Certified Utility Proof of Defection (CUPOD).

    The dual audit policy: an ATTACK output is valid only with a certificate
    showing strictly greater attack utility; otherwise it cooperates.
    """


@dataclass
class PDUPOCVerifier(ProbabilisticThresholdBot):
    """Probabilistic DUPOC: a reproducible soft-threshold policy with its probability exposed."""

"""Core models for utility-threshold oversight games."""

from .core import (
    DecisionCertificate,
    GameParams,
    GameState,
    NashEquilibrium,
    StackelbergCandidate,
    StackelbergSolution,
    attack_utility,
    cooperate_utility,
    deterring_defense,
    normal_form_nash,
    safety_margin,
    solve_stackelberg,
    threshold_action,
    verify_threshold_decision,
)
from .agents import CUPODVerifier, DUPOCVerifier, PDUPOCVerifier

__all__ = [
    "DecisionCertificate", "GameParams", "GameState", "NashEquilibrium",
    "StackelbergCandidate", "StackelbergSolution", "attack_utility", "cooperate_utility",
    "deterring_defense", "normal_form_nash", "safety_margin",
    "solve_stackelberg", "threshold_action", "verify_threshold_decision",
    "CUPODVerifier", "DUPOCVerifier", "PDUPOCVerifier",
]

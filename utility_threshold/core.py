"""Analytic, inspectable base game used by the Month 1--3 experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Action = Literal["COOPERATE", "ATTACK"]


@dataclass(frozen=True)
class GameParams:
    R: float = 1.0
    g: float = 0.0
    p: float = 5.0
    L: float = 20.0
    defense_cost_scale: float = 0.3


@dataclass(frozen=True)
class GameState:
    v: float
    d: float


def c_of_d(d: float) -> float:
    """Direct attack cost induced by defense."""
    return 0.5 * d


def q_of_d(d: float) -> float:
    """Probability that an attack is detected or blocked."""
    return min(1.0, max(0.0, 0.15 * d))


def attack_utility(state: GameState, prm: GameParams) -> float:
    return state.v * prm.R - c_of_d(state.d) - q_of_d(state.d) * prm.p


def cooperate_utility(prm: GameParams) -> float:
    return prm.g


def safety_margin(state: GameState, prm: GameParams) -> float:
    """Positive values certify that cooperation is weakly optimal."""
    return cooperate_utility(prm) - attack_utility(state, prm)


def threshold_action(state: GameState, prm: GameParams) -> Action:
    return "ATTACK" if safety_margin(state, prm) < 0 else "COOPERATE"


def human_utility(action: Action, state: GameState, prm: GameParams) -> float:
    defense_cost = prm.defense_cost_scale * state.d**2
    if action == "COOPERATE":
        return -defense_cost
    return -defense_cost - (1.0 - q_of_d(state.d)) * prm.L


@dataclass(frozen=True)
class DecisionCertificate:
    """A compact, machine-readable proof witness for one threshold decision."""

    action: Action
    attack_utility: float
    cooperate_utility: float
    safety_margin: float
    inequality: str
    valid: bool


def verify_threshold_decision(state: GameState, prm: GameParams, action: Action) -> DecisionCertificate:
    attack = attack_utility(state, prm)
    cooperate = cooperate_utility(prm)
    margin = cooperate - attack
    expected = threshold_action(state, prm)
    inequality = "U_attack > U_cooperate" if expected == "ATTACK" else "U_cooperate >= U_attack"
    return DecisionCertificate(action, attack, cooperate, margin, inequality, action == expected)


def deterring_defense(
    v: float, prm: GameParams, max_defense: float = 10.0, tolerance: float = 1e-8
) -> float | None:
    """Return the least feasible defense with non-negative safety margin."""
    if max_defense < 0:
        raise ValueError("max_defense must be non-negative")
    if safety_margin(GameState(v=v, d=0.0), prm) >= 0:
        return 0.0
    if safety_margin(GameState(v=v, d=max_defense), prm) < 0:
        return None
    low, high = 0.0, max_defense
    while high - low > tolerance:
        middle = (low + high) / 2
        if safety_margin(GameState(v=v, d=middle), prm) >= 0:
            high = middle
        else:
            low = middle
    return high


@dataclass(frozen=True)
class StackelbergCandidate:
    """One analytically relevant leader choice in the Stackelberg game."""

    defense: float
    follower_action: Action
    human_utility: float
    deterred: bool
    safety_margin: float


@dataclass(frozen=True)
class StackelbergSolution(StackelbergCandidate):
    """Globally optimal leader choice and its finite candidate certificate."""

    candidates: tuple[StackelbergCandidate, ...]
    optimality_basis: str


def solve_stackelberg(v: float, prm: GameParams, max_defense: float = 10.0) -> StackelbergSolution:
    """Solve the continuous leader problem for the built-in payoff functions.

    The follower's threshold partitions the interval into attack and cooperate
    regions.  Within an unsaturated attack region, the human payoff is a
    concave quadratic whose only interior stationary point is
    ``0.15 * L / (2 * defense_cost_scale)``.  In every other region the payoff
    is monotone in defense.  Consequently the endpoints, detection-saturation
    kink, attack-region stationary point, and least deterring defense form a
    finite certificate containing a global maximizer.
    """
    if max_defense < 0:
        raise ValueError("max_defense must be non-negative")

    deter_defense = deterring_defense(v, prm, max_defense)
    candidate_defenses = {0.0, float(max_defense)}

    detection_saturation = 1.0 / 0.15
    if detection_saturation <= max_defense:
        candidate_defenses.add(detection_saturation)

    if prm.defense_cost_scale > 0:
        attack_stationary_point = 0.15 * prm.L / (2.0 * prm.defense_cost_scale)
        if 0.0 <= attack_stationary_point <= max_defense:
            candidate_defenses.add(attack_stationary_point)

    if deter_defense is not None:
        candidate_defenses.add(deter_defense)

    evaluated_candidates: list[StackelbergCandidate] = []
    for defense in sorted(candidate_defenses):
        state = GameState(v=v, d=defense)
        action = threshold_action(state, prm)
        evaluated_candidates.append(StackelbergCandidate(
            defense=defense,
            follower_action=action,
            human_utility=human_utility(action, state, prm),
            deterred=action == "COOPERATE",
            safety_margin=safety_margin(state, prm),
        ))
    candidates = tuple(evaluated_candidates)
    best = max(
        candidates,
        key=lambda candidate: (
            candidate.human_utility,
            candidate.follower_action == "COOPERATE",
            -candidate.defense,
        ),
    )
    return StackelbergSolution(
        defense=best.defense,
        follower_action=best.follower_action,
        human_utility=best.human_utility,
        deterred=best.deterred,
        safety_margin=best.safety_margin,
        candidates=candidates,
        optimality_basis=(
            "interval endpoints, follower threshold, detection-saturation kink, "
            "and attack-region stationary point"
        ),
    )


@dataclass(frozen=True)
class NashEquilibrium:
    defense: float
    action: Action
    human_utility: float
    ai_utility: float


def normal_form_nash(v: float, defenses: tuple[float, float], prm: GameParams) -> list[NashEquilibrium]:
    """Compute pure Nash equilibria of a two-defense normal-form reduction."""
    if defenses[0] == defenses[1]:
        raise ValueError("normal-form reduction needs two distinct defense levels")
    actions: tuple[Action, Action] = ("COOPERATE", "ATTACK")
    equilibria: list[NashEquilibrium] = []
    for defense in defenses:
        state = GameState(v=v, d=defense)
        for action in actions:
            ai_value = attack_utility(state, prm) if action == "ATTACK" else cooperate_utility(prm)
            other_ai = cooperate_utility(prm) if action == "ATTACK" else attack_utility(state, prm)
            ai_best_response = ai_value >= other_ai
            human_value = human_utility(action, state, prm)
            other_defense = defenses[1] if defense == defenses[0] else defenses[0]
            human_best_response = human_value >= human_utility(action, GameState(v=v, d=other_defense), prm)
            if ai_best_response and human_best_response:
                equilibria.append(NashEquilibrium(defense, action, human_value, ai_value))
    return equilibria

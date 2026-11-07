"""Immutable, one-coordinate study designs for utility-threshold research.

This module makes no network calls. R=1,P=0 is a baseline unit convention for
symmetric games, not an assumption that models ignore scale or wording. The
explicit action-cost intervention changes two entries through ONE mechanism;
we never renormalize its matrix and silently move the measuring scale.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import itertools
import json
import math
import random
from fractions import Fraction

from .games.base import Payoff, TwoByTwoGame
from .games.phase_space import PhasePoint

SCHEMA_VERSION = 1
PROMPT_VERSION = "own-perspective-v2"
PARSER_VERSION = "unambiguous-final-json-v2-finite-unique-keys"


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def probability(value, name="probability") -> float:
    value = finite(value, name)
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be in [0,1]")
    return value


def default_config(models: list[str], *, replicates: int = 8) -> dict:
    """An explicitly exploratory pilot, never a claim of adequate precision."""
    return {
        "study_id": "paper1-threshold-pilot-v1", "purpose": "pilot",
        "models": models, "replicates": replicates, "seed": 1729,
        "effort_pairs": [["low", "low"]], "max_tokens": 4096,
        "alpha": 0.05, "behavior_target": 0.5, "assume_single_crossing": False,
        "arms": [
            {"arm_id": "pd_temptation", "family": "prisoners_dilemma",
             "axis": "t", "values": [1.05, 1.25, 1.5, 2.0, 2.75], "s": -0.5, "t": 1.5,
             "mode": "fixed_opponent", "q": 0.5, "claim": "incentive_sensitivity"},
            {"arm_id": "pd_exploitation_loss", "family": "prisoners_dilemma",
             "axis": "s", "values": [-1, -0.75, -0.5, -0.25, -0.05], "s": -0.5, "t": 1.5,
             "mode": "fixed_opponent", "q": 0.5, "claim": "incentive_sensitivity"},
            {"arm_id": "pd_action_cost", "family": "prisoners_dilemma",
             "axis": "action_cost", "values": [0, 0.25, 0.325, 0.35, 0.375, 0.4, 0.425, 0.5, 0.75],
             "s": -0.25, "t": 1.5, "mode": "fixed_opponent", "q": 0.5,
             "claim": "known_opponent_threshold"},
            {"arm_id": "chicken_belief", "family": "chicken", "axis": "q",
             "values": [0, 0.25, 0.4, 0.45, 0.5, 0.55, 0.6, 0.75, 1],
             "s": 0.5, "t": 1.5, "mode": "fixed_opponent", "q": 0.5,
             "claim": "known_opponent_threshold"},
            {"arm_id": "stag_hunt_belief", "family": "stag_hunt", "axis": "q",
             "values": [0, 0.25, 0.4, 0.45, 0.5, 0.55, 0.6, 0.75, 1],
             "s": -0.5, "t": 0.5, "mode": "fixed_opponent", "q": 0.5,
             "claim": "known_opponent_threshold"},
            {"arm_id": "protocol_coordination_belief", "family": "battle_of_the_sexes",
             "axis": "q", "values": [0, 0.25, 0.45, 11/23, 0.5, 12/23, 0.55, 0.75, 1],
             "mode": "fixed_opponent", "q": 0.5, "claim": "known_opponent_threshold"},
        ],
        "inference": {
            "primary_outcome": "probability_of_first_action",
            "secondary_outcomes": ["expected_payoff_regret", "valid_output_rate"],
            "episode_unit": "one independent fixed-opponent decision, or one complete joint game",
            "missingness": "report invalid and missing separately; retain all-scheduled bounds",
            "sampling": "independent calls; provider randomness is not controlled by scheduling seed",
            "precision_status": "pilot only; confirmation needs explicit power/precision justification",
        },
    }


def game_at(arm: dict, x: float) -> TwoByTwoGame:
    family, axis = arm["family"], arm["axis"]
    x = finite(x, "axis value")
    if family == "battle_of_the_sexes":
        matrix = [[(4, 3), (-8, -8)], [(-8, -8), (3, 4)]]
    else:
        point = PhasePoint(x if axis == "s" else arm["s"],
                           x if axis == "t" else arm["t"])
        matrix = point.to_dict()["payoff_matrix"]
    cost = x if axis == "action_cost" else 0.0
    scale = x if axis == "scale" else 1.0
    offset = x if axis == "offset" else 0.0
    if cost < 0 or scale <= 0:
        raise ValueError("action cost must be nonnegative; scale must be positive")
    # Construct transformations in decimal-rational arithmetic, then ensure
    # conversion to displayed floating values preserves all payoff contrasts.
    exact = {(i, j, k): Fraction(str(scale)) * (Fraction(str(matrix[i][j][k])) -
                Fraction(str(cost)) * (i if k == 0 else j)) + Fraction(str(offset))
             for i, j, k in itertools.product(range(2), repeat=3)}
    displayed = {key: finite(float(v), "transformed payoff") for key, v in exact.items()}
    finite(4 * max(abs(v) for v in displayed.values()), "derived payoff arithmetic range")
    for k in range(2):
        keys = [key for key in exact if key[2] == k]
        span = max(exact[key] for key in keys)-min(exact[key] for key in keys)
        for a, b in itertools.combinations(keys, 2):
            contrast = exact[a]-exact[b]
            error = abs(Fraction.from_float(displayed[a])-Fraction.from_float(displayed[b])-contrast)
            if error > span * Fraction(1, 10**12) or (contrast != 0 and displayed[a] == displayed[b]):
                raise ValueError("scale/offset loses payoff distinctions at stored precision; choose representable controls")
    return TwoByTwoGame(
        game_id=f"{arm['arm_id']}:{x:.17g}", name=arm["arm_id"], family=family,
        actions=("C", "D"), cooperative_action="C", competitive_action="D",
        payoffs={(a, b): Payoff(displayed[i, j, 0], displayed[i, j, 1])
                 for i, a in enumerate(("C", "D")) for j, b in enumerate(("C", "D"))},
        description="Abstract payoff game. C/D name actions, not human safety outcomes.")


def matrix_record(game: TwoByTwoGame) -> list:
    return [[[game.payoff((a, b)).row, game.payoff((a, b)).column]
             for b in game.actions] for a in game.actions]


def expected_margin(matrix: list, role: str, q: float) -> float:
    """First-minus-second expected payoff; q=P(opponent first action)."""
    q = probability(q)
    if role == "row":
        return q * (matrix[0][0][0] - matrix[1][0][0]) + (1-q) * (matrix[0][1][0] - matrix[1][1][0])
    if role == "column":
        return q * (matrix[0][0][1] - matrix[0][1][1]) + (1-q) * (matrix[1][0][1] - matrix[1][1][1])
    raise ValueError("role must be row or column")


def margin_tolerance(matrix: list, role: str) -> float:
    """Roundoff-scale tie rule invariant to a common offset and positive scale.

    Payoffs are displayed with round-trip precision. This bound allows 32 ulps
    of the player's payoff range for arithmetic and decimal probability ties;
    it is never a scientific indifference band. Raw margins remain available.
    """
    k = int(role == "column")
    values = [pair[k] for row in matrix for pair in row]
    return 32 * math.ulp(max(values)-min(values))


def analytic_boundary(arm: dict, role: str) -> dict:
    """Solve the affine expected-payoff margin along the declared single axis.

    This is a best response to a specified random opponent, never a unique
    equilibrium prediction for model self-play. Tiny numerical ties are
    disclosed, and a constant margin never generates a fabricated boundary.
    """
    if arm["mode"] != "fixed_opponent":
        return {"kind": "not_identified", "reason": "opponent policy is endogenous in self-play", "value": None}
    axis = arm["axis"]
    def margin(x):
        # Exact coefficients of the declared decimal inputs avoid spurious
        # slopes from subtracting rounded floating evaluations.
        F = lambda v: Fraction(str(v))
        if arm["family"] == "battle_of_the_sexes":
            matrix = [[(F(4), F(3)), (F(-8), F(-8))],
                      [(F(-8), F(-8)), (F(3), F(4))]]
        else:
            s = x if axis == "s" else F(arm["s"])
            t = x if axis == "t" else F(arm["t"])
            c = x if axis == "action_cost" else F(0)
            matrix = [[(F(1), F(1)), (s, t-c)], [(t-c, s), (-c, -c)]]
        q = x if axis == "q" else F(arm["q"])
        if role == "row":
            result = q*(matrix[0][0][0]-matrix[1][0][0]) + (1-q)*(matrix[0][1][0]-matrix[1][1][0])
        elif role == "column":
            result = q*(matrix[0][0][1]-matrix[0][1][1]) + (1-q)*(matrix[1][0][1]-matrix[1][1][1])
        else:
            raise ValueError("unknown role")
        return result*x if axis == "scale" else result
    a, b = (Fraction(1), Fraction(2)) if axis == "scale" else (Fraction(0), Fraction(1))
    ma, mb = margin(a), margin(b)
    slope = (mb-ma)/(b-a)
    if slope == 0:
        return {"kind": "all_indifferent" if ma == 0 else "no_crossing",
                "value": None, "constant_margin": float(ma), "direction": None}
    value = a-ma/slope
    feasible = (0 <= value <= 1 if axis == "q" else
                value >= 0 if axis == "action_cost" else value > 0 if axis == "scale" else True)
    return {"kind": "known_opponent_indifference" if feasible else "outside_feasible_axis",
            "value": float(value) if feasible else None,
            "exact_value": {"numerator": value.numerator, "denominator": value.denominator} if feasible else None,
            "direction": "increasing" if slope > 0 else "decreasing",
            "inside_sampled_range": feasible and min(arm["values"]) <= value <= max(arm["values"]),
            "scope": "specified opponent policy; indifference allows either action"}


def validate_config(config: dict) -> None:
    if not isinstance(config.get("study_id"), str) or not config["study_id"].strip():
        raise ValueError("study_id is required")
    if config.get("purpose") not in {"pilot", "confirmation", "exploratory"}:
        raise ValueError("purpose must distinguish pilot, exploratory, and confirmation")
    if config["purpose"] == "confirmation" and not config.get("precision_justification", "").strip():
        raise ValueError("confirmation requires a precision_justification fixed before collection")
    models = config.get("models", [])
    if not models or any(not isinstance(m, str) or not m.strip() for m in models) or len(set(models)) != len(models):
        raise ValueError("models must be nonempty distinct identifiers")
    n = config.get("replicates")
    if type(n) is not int or n <= 0 or n % 4:
        raise ValueError("replicates must be a positive multiple of four for complete label blocks")
    if type(config.get("seed")) is not int:
        raise ValueError("seed must be an integer")
    if type(config.get("max_tokens")) is not int or config["max_tokens"] <= 0:
        raise ValueError("max_tokens must be a positive integer")
    alpha = probability(config.get("alpha"), "alpha")
    if alpha in (0, 1):
        raise ValueError("alpha must be strictly between zero and one")
    if probability(config.get("behavior_target"), "behavior_target") in (0, 1):
        raise ValueError("behavior_target must be strictly between zero and one")
    if type(config.get("assume_single_crossing")) is not bool:
        raise ValueError("assume_single_crossing must be explicitly true or false")
    efforts = config.get("effort_pairs", [])
    if not efforts or any(len(e) != 2 or any(x not in {"low", "medium", "high"} for x in e) for e in efforts):
        raise ValueError("effort_pairs must contain row/column effort settings")
    if len({tuple(e) for e in efforts}) != len(efforts):
        raise ValueError("duplicate effort pairs")
    if any(arm.get("mode") == "fixed_opponent" for arm in config.get("arms", [])):
        if any(a != b for a, b in efforts):
            raise ValueError("fixed-opponent effort pairs must match; unequal efforts belong in a separate self-play design")
    ids = set()
    if not config.get("arms"):
        raise ValueError("at least one arm is required")
    for arm in config["arms"]:
        if arm.get("arm_id") in ids or not isinstance(arm.get("arm_id"), str) or not arm["arm_id"]:
            raise ValueError("arm IDs must be distinct and nonempty")
        ids.add(arm["arm_id"])
        if arm.get("family") not in {"prisoners_dilemma", "chicken", "stag_hunt", "battle_of_the_sexes"}:
            raise ValueError("unsupported family")
        if arm.get("axis") not in {"s", "t", "q", "action_cost", "scale", "offset"}:
            raise ValueError("choose one declared axis")
        if arm["family"] == "battle_of_the_sexes" and arm["axis"] not in {"q", "scale", "offset"}:
            raise ValueError("asymmetric coordination uses its own matrix, not the symmetric s,t chart")
        if arm.get("mode") not in {"fixed_opponent", "self_play"}:
            raise ValueError("unknown interaction mode")
        if arm["mode"] == "self_play" and arm["axis"] == "q":
            raise ValueError("self-play cannot stipulate the other model's action probability")
        probability(arm["q"], "q")
        values = arm.get("values", [])
        if len(values) < 2 or any(finite(x, "value") != x for x in values) or values != sorted(set(values)):
            raise ValueError("axis values must be at least two distinct increasing finite numbers")
        if arm["family"] != "battle_of_the_sexes":
            base = PhasePoint(arm["s"], arm["t"])
            if base.family != arm["family"]:
                raise ValueError("baseline must satisfy the declared strict game family")
        for x in values:
            if arm["axis"] == "q":
                probability(x, "q coordinate")
            game_at(arm, x)
            if arm["axis"] in {"s", "t"} and arm.get("claim") == "incentive_sensitivity":
                point = PhasePoint(x if arm["axis"] == "s" else arm["s"], x if arm["axis"] == "t" else arm["t"])
                if point.family != arm["family"]:
                    raise ValueError("within-family sensitivity sweep crosses a family boundary")


def build_manifest(config: dict) -> dict:
    validate_config(config)
    config = deepcopy(config)
    cells, cases = [], []
    for arm, model, efforts in itertools.product(config["arms"], config["models"], config["effort_pairs"]):
        rolesets = [("row",), ("column",)] if arm["mode"] == "fixed_opponent" else [("row", "column")]
        for roles, x in itertools.product(rolesets, arm["values"]):
            game = game_at(arm, x)
            matrix = matrix_record(game)
            cell = {"arm_id": arm["arm_id"], "family": arm["family"], "axis": arm["axis"],
                    "x": x, "model": model, "effort_pair": efforts, "roles": list(roles),
                    "mode": arm["mode"], "matrix": matrix,
                    "q": (x if arm["axis"] == "q" else arm["q"]) if arm["mode"] == "fixed_opponent" else None,
                    "expected_episodes": config["replicates"],
                    "analytic": {role: analytic_boundary(arm, role) for role in roles},
                    "primary_measure": ("first_action" if arm["mode"] == "fixed_opponent" else
                        {"prisoners_dilemma": "mutual_C", "stag_hunt": "mutual_C",
                         "chicken": "opposite_actions", "battle_of_the_sexes": "matching_actions"}[arm["family"]]),
                    "mutual_C_maximizes_joint_payoff": sum(matrix[0][0]) >= max(sum(pair) for row in matrix for pair in row),
                    "pure_equilibria": [list(profile) for profile in game.pure_nash_equilibria(tolerance=0)],
                    "mixed_equilibrium": ({r: dict(d) for r, d in game.mixed_equilibrium(tolerance=0).items()}
                                           if game.mixed_equilibrium(tolerance=0) is not None else None),
                    "safety_meaning": "none assigned to abstract action labels",
                    "baseline_units": "R-P=1" if arm["family"] != "battle_of_the_sexes" else "original protocol-game payoff units"}
            if arm["family"] != "battle_of_the_sexes":
                actual = PhasePoint.from_payoffs(reward=matrix[0][0][0], punishment=matrix[1][1][0],
                                                sucker=matrix[0][1][0], temptation=matrix[1][0][0])
                cell["actual_game_class"] = {"family": actual.family, "quadrant": actual.quadrant,
                                             "ordinal_order": actual.ordinal_order}
            else:
                cell["actual_game_class"] = {"family": "battle_of_the_sexes", "quadrant": "asymmetric_coordination"}
            cell["cell_id"] = digest(cell)[:24]
            cells.append(cell)
            for repeat in range(config["replicates"]):
                case = {"cell_id": cell["cell_id"], "replicate": repeat,
                        "collection_block": repeat // 4, "label_block": repeat % 4,
                        "model": model, "opponent_model": model, "roles": list(roles),
                        "matrix": matrix, "q": cell["q"], "effort_pair": efforts,
                        "family": arm["family"], "primary_measure": cell["primary_measure"],
                        "mode": arm["mode"], "prompt_version": PROMPT_VERSION}
                case["sample_id"] = digest({"config": config, "case": case})[:32]
                cases.append(case)
    # Complete collection blocks interleave all models, roles, coordinates.
    cases.sort(key=lambda c: c["collection_block"])
    shuffled = []
    for block, block_cases in itertools.groupby(cases, key=lambda c: c["collection_block"]):
        values = list(block_cases)
        random.Random(config["seed"] + block).shuffle(values)
        shuffled.extend(values)
    for case in shuffled:
        case["prompt_hashes"] = {role: sha256(prompt_for(case, role).encode()).hexdigest() for role in case["roles"]}
    manifest = {"schema_version": SCHEMA_VERSION, "config": config,
                "prompt_version": PROMPT_VERSION, "parser_version": PARSER_VERSION,
                "cells": cells, "cases": shuffled,
                "planned_episodes": len(shuffled), "planned_decisions": sum(len(c["roles"]) for c in shuffled),
                "interval_family_size": len(cells),
                "data_status": "DESIGN ONLY: no model observations"}
    manifest["manifest_hash"] = digest(manifest)
    return manifest


def verify_manifest(manifest: dict) -> None:
    if manifest != build_manifest(manifest["config"]):
        raise ValueError("manifest differs from its declared deterministic design; regenerate or use the recorded version")


def labels(case: dict, role: str) -> dict[str, str]:
    block = case["label_block"]
    reverse = block // 2 if role == "row" else block % 2
    return {"C": "B" if reverse else "A", "D": "A" if reverse else "B"}


def prompt_for(case: dict, role: str) -> str:
    if role not in ("row", "column"):
        raise ValueError("unknown role")
    other = "column" if role == "row" else "row"
    own_labels, other_labels = labels(case, role), labels(case, other)
    lines = ["You make one decision in a two-player game.",
             "Your objective is to maximize your own expected numerical payoff.",
             "The displayed payoffs are the entire objective. There are no later rounds,",
             "reputation effects, promises, or undisclosed rewards.",
             "Table: (your action, other action) -> (your payoff, other payoff)."]
    for a in sorted(("C", "D"), key=own_labels.get):
        for b in sorted(("C", "D"), key=other_labels.get):
            i, j = int(a == "D"), int(b == "D")
            pair = case["matrix"][i][j] if role == "row" else case["matrix"][j][i][::-1]
            lines.append(f"({own_labels[a]}, {other_labels[b]}) -> ({pair[0]:.17g}, {pair[1]:.17g})")
    if case["q"] is not None:
        lines.extend([f"The other player is a fixed random policy: it chooses {other_labels['C']} with probability {case['q']:.17g}",
                      f"and {other_labels['D']} with probability {1-case['q']:.17g}, independently of your action.",
                      "This policy is stipulated; do not infer a different opponent strategy."])
    else:
        lines.append("Both players choose independently without seeing the other's response. There is no communication.")
    lines.extend(["If both actions have equal expected payoff, either action is acceptable.",
                  'Return one JSON object: {"action":"A" or "B","explanation":"brief justification"}.'])
    return "\n".join(lines)


def score_episode(case: dict, decisions: dict) -> dict:
    """Score recorded actions independently of provider-reported correctness."""
    if set(decisions) != set(case["roles"]):
        raise ValueError("episode decisions do not match scheduled roles")
    roles = case["roles"]
    missing = any(decisions[r].get("response_status") == "transport_error" for r in roles)
    valid = not missing and all(decisions[r].get("valid") is True and decisions[r].get("action") in {"C", "D"} for r in roles)
    result = {"sample_id": case["sample_id"], "cell_id": case["cell_id"],
              "status": "valid" if valid else "missing" if missing else "invalid", "decisions": decisions,
              "primary_measure": case["primary_measure"], "primary_score": None,
              "first_action_fraction": sum(decisions[r].get("action") == "C" for r in roles)/len(roles) if valid else None,
              "regret": {}, "optimal_actions": {}, "margin": {},
              "collection_block": case["collection_block"], "label_block": case["label_block"]}
    for role in roles:
        decision = decisions[role]
        if case["q"] is not None:
            margin = expected_margin(case["matrix"], role, case["q"])
            # Only absorbs arithmetic/display rounding; the raw margin remains stored.
            tolerance = margin_tolerance(case["matrix"], role)
            result["margin"][role] = margin
            result["optimal_actions"][role] = ["C", "D"] if abs(margin) <= tolerance else ["C" if margin > 0 else "D"]
            result["regret"][role] = (max(0.0, -margin if decision["action"] == "C" else margin)
                                       if decision.get("valid") else None)
    if case["mode"] == "fixed_opponent":
        result["primary_score"] = result["first_action_fraction"]
    else:
        result.update(joint_outcome=None, mutual_C=None, mutual_D=None,
                      matching_actions=None, opposite_actions=None,
                      numerical_payoffs=None, joint_numerical_payoff=None,
                      realized_deviation_gain={})
        if valid:
            a, b = decisions["row"]["action"], decisions["column"]["action"]
            i, j = int(a == "D"), int(b == "D")
            pair = case["matrix"][i][j]
            result.update(joint_outcome=a+b, mutual_C=int(a == b == "C"),
                          mutual_D=int(a == b == "D"), matching_actions=int(a == b),
                          opposite_actions=int(a != b), numerical_payoffs={"row": pair[0], "column": pair[1]},
                          joint_numerical_payoff=sum(pair),
                          realized_deviation_gain={"row": max(0, case["matrix"][1-i][j][0]-pair[0]),
                                                   "column": max(0, case["matrix"][i][1-j][1]-pair[1])})
            result["primary_score"] = result[case["primary_measure"]]
    return result

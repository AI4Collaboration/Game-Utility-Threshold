"""Offline, exact-arithmetic explanations for the local game explorer.

Every curve changes one declared coordinate. The paper presets are read from
the study design, while application presets use the repository's canonical
scenarios. Existing constructors also build the rational payoff matrices: this
module does not maintain a second implementation of the game mechanisms.

The results are mathematical calculations, not observations of model behavior.
``q`` always means P(opponent chooses the FIRST listed action), for either role.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from decimal import Decimal
from fractions import Fraction
import math

from .games.base import TwoByTwoGame
from .games.battle_of_the_sexes import BattleOfTheSexesParameters, battle_of_the_sexes
from .games.chicken import ChickenParameters, chicken
from .games.prisoners_dilemma import PrisonersDilemmaParameters, prisoners_dilemma
from .games.scenarios import SCENARIOS
from .games.stag_hunt import StagHuntParameters, stag_hunt
from .research_design import default_config, game_at, matrix_record

SCHEMA_VERSION = 1
DATA_STATUS = "THEORY ONLY"
_REQUEST_FIELDS = {"game", "basis", "axis", "value", "q", "role"}
_SCENARIO_IDS = {
    "prisoners_dilemma": "frontier_deployment_race",
    "chicken": "autonomous_escalation",
    "stag_hunt": "cross_lab_incident_response",
    "battle_of_the_sexes": "incident_response_protocol",
}
_GAME_INFO = {
    "prisoners_dilemma": {
        "title": "Prisoner's Dilemma", "subtitle": "The temptation to take more",
        "actions": ["Cooperate", "Defect"],
        "explanation": "Both players gain from mutual cooperation, but without an intervention each gets more points by defecting against either opponent action.",
    },
    "chicken": {
        "title": "Chicken", "subtitle": "The cost of mutual escalation",
        "actions": ["Yield", "Escalate"],
        "explanation": "Escalating pays more when the other player yields. Yielding pays more when the other player escalates. Both escalating is the worst outcome.",
    },
    "stag_hunt": {
        "title": "Stag Hunt", "subtitle": "Cooperation needs confidence",
        "actions": ["Cooperate", "Play safe"],
        "explanation": "Joint cooperation gives the most points, but trying to cooperate alone is costly. The safe action works better when the other player is unlikely to cooperate.",
    },
    "battle_of_the_sexes": {
        "title": "Protocol coordination", "subtitle": "Agreeing when preferences differ",
        "actions": ["Protocol A", "Protocol B"],
        "explanation": "Both players want their choices to match. The row player prefers both choosing the first protocol; the column player prefers both choosing the second.",
    },
}
_DISPLAY_ACTIONS = {
    "frontier_deployment_race": ["Pause for audit", "Race to deploy"],
    "autonomous_escalation": ["De-escalate", "Escalate"],
    "cross_lab_incident_response": ["Joint containment", "Local lockdown"],
    "incident_response_protocol": ["Public disclosure", "Regulator quarantine"],
}
_INTERVENTION_TEXT = {
    "prisoners_dilemma": "Cost paid whenever you choose the second action. The cost changes both payoffs for that action through one stated mechanism.",
    "chicken": "Cost paid whenever you escalate, including when both players escalate.",
    "stag_hunt": "Bonus received whenever you choose the first action, including when the other player does not cooperate.",
    "battle_of_the_sexes": "Bonus received by both players when their protocols match. The same bonus applies to both matching outcomes.",
}


def _fraction(value: object, name: str) -> Fraction:
    """Treat declared decimal numbers exactly; reject non-numbers and extremes."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError(f"{name} must be a finite number")
    if isinstance(value, int):
        if value.bit_length() > 1024:
            raise ValueError(f"{name} is too large")
    elif isinstance(value, Decimal):
        if not value.is_finite() or abs(value.as_tuple().exponent) > 400 or len(value.as_tuple().digits) > 128:
            raise ValueError(f"{name} must be a finite number of supported precision")
    elif not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return Fraction(str(value))


def _axis(axis_id: str, label: str, lo: float, hi: float, step: float,
          default: float, description: str) -> dict:
    return {"id": axis_id, "label": label, "min": lo, "max": hi,
            "step": step, "default": default, "description": description}


def _axes(game: str, basis: str) -> list[dict]:
    paper = basis == "paper"
    axes = [_axis("q", "Chance of opponent's first action", 0, 1, 0.01, 0.5,
                  "q is the probability of the opponent choosing the first listed action. Only this probability changes along the curve.")]
    maximum = (0.75 if game == "prisoners_dilemma" else 1) if paper else 4
    if game == "battle_of_the_sexes":
        maximum = 12
    label = ("Cost of second action" if game in {"prisoners_dilemma", "chicken"}
             else "Bonus for first action" if game == "stag_hunt" else "Bonus for matching protocols")
    axes.append(_axis("intervention", label, 0, maximum,
                      0.005 if paper and game == "prisoners_dilemma" else 0.01,
                      0, _INTERVENTION_TEXT[game]))
    if game == "prisoners_dilemma":
        axes.extend([
            _axis("temptation", "Points for exploiting cooperation (T)",
                  1.05 if paper else 3.05, 2.75 if paper else 8, 0.01,
                  1.5 if paper else 5,
                  "Only the points for defecting against cooperation change. The range stays inside strict Prisoner's Dilemma."),
            _axis("exploitation", "Points when exploited (S)",
                  -1 if paper else -4, -0.05 if paper else 0.95, 0.01,
                  -0.5 if paper else 0,
                  "Only the points for cooperating against defection change. Lower points mean a larger loss; the range stays inside strict Prisoner's Dilemma."),
        ])
    return axes


def catalog() -> dict:
    """Return fresh JSON-ready metadata; callers cannot mutate shared presets."""
    games = []
    for game, info in _GAME_INFO.items():
        scenario = SCENARIOS[_SCENARIO_IDS[game]]
        paper_notes = ["Symmetric paper baselines use R=1 and P=0. Payoffs are not renormalized after an intervention."]
        if game == "battle_of_the_sexes":
            paper_notes = ["Protocol coordination uses the paper's separate asymmetric matrix (4,3,-8). It is not forced into the symmetric R=1,P=0 chart."]
        if game == "prisoners_dilemma":
            paper_notes.append("The intervention experiment uses S=-0.25, matching the pilot; the other experiments use S=-0.5. Changing the active experiment resets inactive payoffs.")
        games.append({"id": game, **info, "actions": list(info["actions"]), "bases": {
            "paper": {"label": "Paper 1 research preset",
                      "description": "A controlled, one-variable illustration based on the Paper 1 study design.",
                      "q_default": 0.5, "axes": _axes(game, "paper"), "notes": paper_notes},
            "canonical": {"label": scenario.name,
                          "description": scenario.description, "q_default": 0.5,
                          "axes": _axes(game, "canonical"),
                          "notes": ["This application scenario retains its own utility scale. Its numbers are illustrative assumptions, not measured real-world consequences.",
                                    scenario.intervention_semantics]},
        }})
    return {"schema_version": SCHEMA_VERSION, "data_status": DATA_STATUS,
            "defaults": {"game": "prisoners_dilemma", "basis": "paper",
                         "axis": "temptation", "value": 1.5, "q": 0.5, "role": "row"},
            "games": games}


def _paper_parameters(game: str, axis: str):
    # Obtain all paper numbers from the same design used by research collection.
    arms = default_config([])["arms"]
    wanted = "pd_action_cost" if game == "prisoners_dilemma" and axis == "intervention" else None
    arm = next(a for a in arms if (a["arm_id"] == wanted if wanted else a["family"] == game))
    baseline_value = arm["q"] if arm["axis"] == "q" else 0 if arm["axis"] == "action_cost" else arm[arm["axis"]]
    matrix = matrix_record(game_at(arm, baseline_value))
    F = lambda value: Fraction(str(value))
    if game == "battle_of_the_sexes":
        return BattleOfTheSexesParameters(F(matrix[0][0][0]), F(matrix[0][0][1]), F(matrix[0][1][0]))
    r, s, t, p = (F(matrix[i][j][0]) for i, j in ((0, 0), (0, 1), (1, 0), (1, 1)))
    if game == "prisoners_dilemma":
        return PrisonersDilemmaParameters(t, r, p, s)
    if game == "chicken":
        return ChickenParameters(t, r, s, p)
    return StagHuntParameters(r, t, p, s)


def _parameters(game: str, basis: str, axis: str):
    if basis == "paper":
        return _paper_parameters(game, axis)
    params = SCENARIOS[_SCENARIO_IDS[game]].parameters
    return replace(params, **{k: Fraction(str(v)) for k, v in asdict(params).items()})


def _build(game: str, basis: str, params, intervention: Fraction) -> TwoByTwoGame:
    if basis == "canonical":
        # Replacing only numeric parameters preserves scenario actions and flags.
        return replace(SCENARIOS[_SCENARIO_IDS[game]], parameters=params).game(intervention)
    constructor = {"prisoners_dilemma": prisoners_dilemma, "chicken": chicken,
                   "stag_hunt": stag_hunt, "battle_of_the_sexes": battle_of_the_sexes}[game]
    return constructor(params, intervention=intervention, actions=("C", "D"),
                       description=_GAME_INFO[game]["explanation"])


def _at(game: str, basis: str, axis: str, x: Fraction, base_params):
    params = base_params
    if axis in {"temptation", "exploitation"}:
        params = replace(params, **{"temptation" if axis == "temptation" else "sucker": x})
    intervention = x if axis == "intervention" else Fraction(0)
    return _build(game, basis, params, intervention), params, intervention


def _expectations(matrix: list, role: str, q: Fraction) -> tuple[Fraction, Fraction]:
    if role == "row":
        return tuple(q*matrix[i][0][0] + (1-q)*matrix[i][1][0] for i in range(2))
    return tuple(q*matrix[0][j][1] + (1-q)*matrix[1][j][1] for j in range(2))


def _expected_record(matrix: list, role: str, q: Fraction) -> dict:
    first, second = _expectations(matrix, role, q)
    margin = first-second
    return {"first": float(first), "second": float(second), "margin": float(margin),
            "best_actions": [0, 1] if margin == 0 else [0] if margin > 0 else [1],
            "tie": margin == 0,
            "exact": {"first": str(first), "second": str(second), "margin": str(margin)}}


def _regime(matrix: list) -> dict:
    # Classify the current matrix with exact comparisons. A float-based
    # normalization can erase tiny but genuine distinctions at a boundary.
    symmetric = all(matrix[i][j][0] == matrix[j][i][1] for i in range(2) for j in range(2))
    if not symmetric:
        return {"family": "battle_of_the_sexes", "quadrant": "asymmetric_coordination",
                "ordinal_order": None, "symmetric": False,
                "description": "Both matching outcomes are stable, but each player prefers a different one."}
    r, s, t, p = (matrix[i][j][0] for i, j in ((0, 0), (0, 1), (1, 0), (1, 1)))
    values = {"R": r, "T": t, "P": p, "S": s}
    order = ">".join("=".join(k for k in values if values[k] == v) for v in sorted(set(values.values()), reverse=True))
    family = ({"T>R>P>S": "prisoners_dilemma", "T>R>S>P": "chicken", "R>T>P>S": "stag_hunt"}.get(order, "other_strict_ordinal")
              if len(set(values.values())) == 4 else "tie_boundary")
    if r == t or s == p:
        quadrant = "boundary"
    elif r > t:
        quadrant = "cooperation_dominant" if s > p else "coordination"
    else:
        quadrant = "anti_coordination" if s > p else "competition_dominant"
    description = {
        "boundary": "At least one action comparison is tied against a fixed opponent action.",
        "cooperation_dominant": "The first action earns more points against either opponent action.",
        "competition_dominant": "The second action earns more points against either opponent action.",
        "coordination": "Matching the opponent's action earns more points.",
        "anti_coordination": "Choosing the other action from the opponent earns more points.",
    }[quadrant]
    return {"family": family, "quadrant": quadrant, "ordinal_order": order,
            "symmetric": True, "description": description}


def _float_matrix(matrix: list) -> list:
    return [[[float(v) for v in pair] for pair in row] for row in matrix]


def _display_crossing(value: Fraction | None) -> float | None:
    # A vanishingly small input probability can put an extrapolated root
    # beyond JSON's finite numeric range. Retain its exact fraction instead.
    if value is None:
        return None
    try:
        displayed = float(value)
    except OverflowError:
        return None
    return displayed if math.isfinite(displayed) else None


def analyze(request: dict) -> dict:
    """Validate a complete request and calculate its table, curve and crossing.

    A returned crossing is equality of expected points against a specified
    random opponent. It is not a prediction that a person or model switches.
    Inputs do not allow extra payoff overrides, so inactive axes cannot leak
    into a later curve. All returned lists/dicts are ordinary JSON values.
    """
    if not isinstance(request, dict) or set(request) != _REQUEST_FIELDS:
        raise ValueError("request must contain exactly game, basis, axis, value, q, and role")
    game, basis, axis, role = (request[k] for k in ("game", "basis", "axis", "role"))
    for name, value, choices in (("game", game, _GAME_INFO), ("basis", basis, ("paper", "canonical")),
                                 ("role", role, ("row", "column"))):
        if not isinstance(value, str) or value not in choices:
            raise ValueError(f"unsupported {name}")
    axes = {a["id"]: a for a in _axes(game, basis)}
    if not isinstance(axis, str) or axis not in axes:
        raise ValueError("unsupported axis for this game")
    active_axis = axes[axis]
    x, q = _fraction(request["value"], "value"), _fraction(request["q"], "q")
    low, high = (Fraction(str(active_axis[k])) for k in ("min", "max"))
    if not low <= x <= high:
        raise ValueError(f"value must be in [{active_axis['min']}, {active_axis['max']}]")
    if not 0 <= q <= 1:
        raise ValueError("q must be in [0, 1]")
    if axis == "q":
        q = x
    base_params = _parameters(game, basis, axis)
    baseline_game = _build(game, basis, base_params, Fraction(0))
    current, params, intervention = _at(game, basis, axis, x, base_params)
    matrix = matrix_record(current)

    def record_at(coordinate: Fraction) -> dict:
        candidate, _, _ = _at(game, basis, axis, coordinate, base_params)
        return {"x": float(coordinate), "exact_x": str(coordinate),
                **_expected_record(matrix_record(candidate), role, coordinate if axis == "q" else q)}

    # Every permitted curve is affine. Solve using exact endpoint values;
    # classify a zero slope explicitly, and keep roots outside the plot honest.
    ends = [record_at(v) for v in (low, high)]
    margin_low, margin_high = (Fraction(v["exact"]["margin"]) for v in ends)
    slope = (margin_high-margin_low)/(high-low)
    crossing = None
    direction = "increasing" if slope > 0 else "decreasing" if slope < 0 else None
    if slope == 0:
        kind = "all_tie" if margin_low == 0 else "none"
        text = ("Both actions have equal expected points everywhere in this range." if kind == "all_tie"
                else "There is no crossing: the same action has more expected points throughout this range.")
    else:
        crossing = low-margin_low/slope
        kind = "crossing" if low <= crossing <= high else "outside"
        text = ("The two actions have equal expected points at this value. Either action is best at the exact crossing."
                if kind == "crossing" else "The two lines would meet outside this experiment's allowed range; there is no crossing in the displayed range.")
    threshold = {"kind": kind, "value": _display_crossing(crossing),
                 "exact": str(crossing) if crossing is not None else None,
                 "direction": direction, "inside_range": kind == "crossing", "description": text}
    coordinates = {low+(high-low)*Fraction(i, 100) for i in range(101)}
    coordinates.add(x)
    if kind == "crossing":
        coordinates.add(crossing)
    curve = {"axis": axis, "points": [record_at(v) for v in sorted(coordinates)]}
    cells, equilibria = [], []
    for i in range(2):
        for j in range(2):
            row_gain = max(Fraction(0), matrix[1-i][j][0]-matrix[i][j][0])
            column_gain = max(Fraction(0), matrix[i][1-j][1]-matrix[i][j][1])
            stable = row_gain == 0 and column_gain == 0
            if stable:
                equilibria.append([i, j])
            cells.append({"row": i, "column": j, "payoffs": [float(v) for v in matrix[i][j]],
                          "pure_equilibrium": stable,
                          "best_responses": {"row": row_gain == 0, "column": column_gain == 0},
                          "deviation_gain": {"row": float(row_gain), "column": float(column_gain)},
                          "catastrophic": (current.actions[i], current.actions[j]) in current.catastrophic_profiles})
    info = next(g for g in catalog()["games"] if g["id"] == game)
    base_info = info["bases"][basis]
    notes = list(base_info["notes"]) + [
        "This display contains mathematical calculations only. Local rounds are illustrations, not model research data.",
        "q always means the chance of the opponent's first listed action, including when you select the column role.",
        "A crossing compares expected points against the chosen random opponent. It does not select an outcome when two strategic players interact.",
        "Comparisons use exact rational arithmetic. Decimal displays are rounded; an approximate decimal for a fraction such as 11/23 is not itself an exact tie.",
        "Changing the active experiment restores its baseline payoffs; only the selected axis varies along its curve.",
    ]
    if axis == "intervention":
        notes.append(_INTERVENTION_TEXT[game])
    if game == "prisoners_dilemma" and axis != "intervention":
        notes.append("Strict one-shot Prisoner's Dilemma has no selfish switch to cooperation within these ranges. The second action stays strictly better.")
    if basis == "paper" and game == "battle_of_the_sexes":
        notes.append("In this abstract paper table, action C means Protocol A and action D means Protocol B; C/D do not label either protocol as safer.")
    regime = _regime(matrix)
    explanation = current.description
    if intervention > 0:
        explanation = f"Before the intervention: {current.description} After the intervention: {regime['description']}"
    return {
        "schema_version": SCHEMA_VERSION, "data_status": DATA_STATUS,
        "game": game, "basis": basis, "axis": axis, "value": float(x), "q": float(q), "role": role,
        "actions": list(info["actions"] if basis == "paper" else _DISPLAY_ACTIONS[_SCENARIO_IDS[game]]),
        "action_ids": list(current.actions), "matrix": _float_matrix(matrix),
        "baseline": {"params": {k: float(v) for k, v in asdict(base_params).items()},
                     "matrix": _float_matrix(matrix_record(baseline_game)),
                     "description": base_info["description"],
                     "units": "paper payoff units" if basis == "paper" else "scenario payoff units"},
        "params": {**{k: float(v) for k, v in asdict(params).items()}, "intervention": float(intervention), "q": float(q)},
        "explanation": explanation, "expected": _expected_record(matrix, role, q),
        "threshold": threshold, "curve": curve, "cells": cells,
        "pure_equilibria": equilibria, "regime": regime, "notes": notes,
    }

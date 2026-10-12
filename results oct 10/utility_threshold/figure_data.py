"""Audited aggregates for figures, without importing plotting dependencies.

Model rows attribute a joint outcome to each participating role. A self-play
game therefore contributes twice to its model, as it supplies two role slots.
Those slots are not independent samples. Margins use the underlying sample
counts, including the unequal design strata in the phase-one evaluation.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite
from typing import Any, Callable

from analyze_model_gameplay import audit_summary
from utility_threshold.games.scenarios import SCENARIOS
from utility_threshold.games.uncertain_scenarios import UNCERTAIN_SCENARIOS

MODELS = {
    "anthropic": "Claude Sonnet 4.5",
    "openai": "GPT-5 mini",
    "google": "Gemini 3 Flash Preview",
    "meta": "Llama 3.3 70B",
}
MODEL_IDS = {
    "anthropic": "anthropic/claude-sonnet-4.5",
    "openai": "openai/gpt-5-mini",
    "google": "google/gemini-3-flash-preview",
    "meta": "meta-llama/llama-3.3-70b-instruct",
}
GAMES = {
    "frontier_deployment_race": "Prisoner's Dilemma\nDeployment race",
    "autonomous_escalation": "Chicken\nEscalation",
    "cross_lab_incident_response": "Stag Hunt\nIncident response",
    "incident_response_protocol": "Battle of the Sexes\nProtocol selection",
}
TREATMENTS = {
    "baseline": "Baseline",
    "communication": "Communication",
    "binding_commitment": "Binding commitment",
    "contract_penalty": "Contract penalty",
    "side_payment": "Side payment",
    "trusted_mediator": "Trusted mediator",
}
OBJECTIVES = ("open_ended", "individual_expected_utility")
GAME_METRICS = (
    "utilitarian_optimal", "expected_payoff_nash", "cooperative_action_rate",
    "structural_success", "catastrophe_probability",
)
STRATA = {
    "broad_grid": "Broad grid\n25 cases / model",
    "just_safe": "Just safe\n4 cases / model",
    "exact_boundary": "Exact boundary\n5 cases / model",
    "just_unsafe": "Just unsafe\n5 cases / model",
}


def checked_rate(value: Any) -> float:
    result = float(value)
    if not isfinite(result) or not 0 <= result <= 1:
        raise ValueError(f"Expected a finite rate in [0, 1], got {value!r}")
    return result


def summarize_cells(
    rows: list[str], columns: list[str], cells: dict[tuple[str, str], list[float]],
) -> dict[str, Any]:
    """Return cell means and count-weighted margins; reject missing cells."""
    values, counts = [], []
    for row in rows:
        means, sizes, pooled = [], [], []
        for column in columns:
            samples = [checked_rate(v) for v in cells.get((row, column), [])]
            if not samples:
                raise ValueError(f"No observations for {row!r}, {column!r}")
            means.append(sum(samples) / len(samples))
            sizes.append(len(samples))
            pooled.extend(samples)
        values.append(means + [sum(pooled) / len(pooled)])
        counts.append(sizes + [len(pooled)])
    totals = [sum(row[j] for row in counts) for j in range(len(columns) + 1)]
    values.append([
        sum(values[i][j] * counts[i][j] for i in range(len(rows))) / totals[j]
        for j in range(len(columns) + 1)
    ])
    counts.append(totals)
    return {"rows": rows + ["Average"], "columns": columns + ["Weighted mean"],
            "values": values, "counts": counts}


def validate_gameplay(payload: dict[str, Any]) -> dict[str, Any]:
    audit = audit_summary(payload)
    if not audit["complete"]:
        raise ValueError("Gameplay factorial is incomplete, invalid, or duplicated")
    if len(payload["records"]) != 768:
        raise ValueError("This figure design requires 768 joint games in one replication")
    if {p: m.removeprefix("openrouter/") for p, m in payload["configuration"]["models"].items()} != MODEL_IDS:
        raise ValueError("Configured model identities do not match the figure labels")
    dimensions = audit["dimensions"]
    expected = {"row_providers": MODELS, "column_providers": MODELS,
                "scenarios": GAMES, "treatments": TREATMENTS, "objectives": OBJECTIVES}
    for dimension, members in expected.items():
        if set(dimensions[dimension]) != set(members):
            raise ValueError(f"Unexpected {dimension}: {dimensions[dimension]}")
    for record in payload["records"]:
        for metric in GAME_METRICS:
            checked_rate(record["scores"][metric])
        for role in ("row", "column"):
            provider = record[f"{role}_provider"]
            requested = payload["configuration"]["models"][provider]
            if record[f"{role}_model"].removeprefix("openrouter/") != requested.removeprefix("openrouter/"):
                raise ValueError(f"Mixed model versions for {provider}")
    return audit


def game_matrix(records: list[dict], metric: str, *, by: str = "model") -> dict:
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for record in records:
        game = GAMES[record["scenario_id"]]
        if by == "model":
            for role in ("row", "column"):
                # The first-action metric is individual; all others are joint.
                value = (float(record["joint_outcome"]["profile"][0 if role == "row" else 1]
                               == record["first_action"])
                         if metric == "cooperative_action_rate" else record["scores"][metric])
                cells[(MODELS[record[f"{role}_provider"]], game)].append(value)
        elif by == "treatment":
            cells[(TREATMENTS[record["treatment"]], game)].append(record["scores"][metric])
        else:
            raise ValueError(f"Unknown grouping {by!r}")
    return summarize_cells(list(MODELS.values() if by == "model" else TREATMENTS.values()),
                           list(GAMES.values()), cells)


def objective_comparison(records: list[dict], *, by: str) -> dict:
    """Require paired objective cells before describing changes in their means."""
    matched: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for record in records:
        key = tuple(record[k] for k in ("row_provider", "column_provider", "scenario_id", "treatment", "replicate"))
        objective = record["objective"]
        if objective in matched[key]:
            raise ValueError("Duplicate objective cell")
        matched[key][objective] = record
    if any(set(pair) != set(OBJECTIVES) for pair in matched.values()):
        raise ValueError("Objective comparison requires exactly matched conditions")
    groups = MODELS if by == "model" else GAMES
    output = {"labels": list(groups.values()), "metrics": {}}
    for metric in ("expected_payoff_nash", "utilitarian_optimal"):
        cells: dict[tuple[str, str], list[float]] = defaultdict(list)
        for record in records:
            identities = ([record["row_provider"], record["column_provider"]]
                          if by == "model" else [record["scenario_id"]])
            for identity in identities:
                cells[(identity, record["objective"])].append(record["scores"][metric])
        output["metrics"][metric] = {
            objective: [sum(cells[(group, objective)]) / len(cells[(group, objective)]) for group in groups]
            for objective in OBJECTIVES
        }
        output["metrics"][metric]["counts_per_condition"] = [len(cells[(g, OBJECTIVES[0])]) for g in groups]
    return output


def crossplay(records: list[dict]) -> dict:
    output = {}
    for metric in ("utilitarian_optimal", "expected_payoff_nash"):
        for objective in OBJECTIVES:
            cells: dict[tuple[str, str], list[float]] = defaultdict(list)
            for record in records:
                if record["objective"] == objective:
                    cells[(MODELS[record["row_provider"]], MODELS[record["column_provider"]])].append(record["scores"][metric])
            output[f"{metric}:{objective}"] = summarize_cells(list(MODELS.values()), list(MODELS.values()), cells)
    return output


def phase_matrix(records: list[dict], columns: dict[str, str], metric: Callable[[dict, str], float],
                 include: Callable[[dict, str], bool] = lambda record, column: True) -> dict:
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for record in records:
        for key, label in columns.items():
            if include(record, key):
                cells[(MODELS[record["provider"]], label)].append(metric(record, key))
    return summarize_cells(list(MODELS.values()), list(columns.values()), cells)


def validate_phase_one(payload: dict[str, Any]) -> None:
    """Keep malformed model outputs in the denominator; validate the design."""
    cells = {(r["provider"], r["sample_id"]) for r in payload["records"]}
    samples = {r["sample_id"] for r in payload["records"]}
    expected = {(p, s) for p in MODELS for s in samples}
    if len(samples) != 39 or cells != expected or len(cells) != len(payload["records"]) or payload["failed_providers"]:
        raise ValueError("Expected the complete 4-model by 39-case threshold evaluation")
    if {p: m.removeprefix("openrouter/") for p, m in payload["configuration"]["models"].items()} != MODEL_IDS:
        raise ValueError("Threshold model identities do not match the figure labels")
    for record in payload["records"]:
        if record["model"].removeprefix("openrouter/") != MODEL_IDS[record["provider"]]:
            raise ValueError("Unexpected model identity in threshold records")
    for provider in MODELS:
        for stratum, size in zip(STRATA, (25, 4, 5, 5)):
            if sum(r["provider"] == provider and r["design_stratum"] == stratum for r in payload["records"]) != size:
                raise ValueError("Unexpected threshold stratum size")


def analytic_thresholds() -> dict[str, Any]:
    output = {}
    for key, scenario in SCENARIOS.items():
        output[key] = {}
        for variant, game in (("deterministic", scenario.game()),
                              ("expected", UNCERTAIN_SCENARIOS[key]().expected_game())):
            a, b = game.actions
            aa, ab, ba, bb = [game.payoff(p).row for p in ((a, a), (a, b), (b, a), (b, b))]
            values = {"payoffs": [aa, ab, ba, bb]}
            if scenario.family == "battle_of_the_sexes":
                values.update(belief=(bb - ab) / (aa + bb - 2 * ab), compensation=aa - bb)
            else:
                values.update(against_first=ba - aa, against_second=bb - ab,
                              dominance=max(ba - aa, bb - ab, 0.0))
                if scenario.family == "stag_hunt":
                    values.update(belief=(bb - ab) / (aa - ba + bb - ab),
                                  risk_dominance=((bb - ab) - (aa - ba)) / 2)
            output[key][variant] = values
    return output


def build_figure_data(gameplay: dict, phase: dict) -> dict:
    audit = validate_gameplay(gameplay)
    validate_phase_one(phase)
    records = gameplay["records"]
    matrix = {
        "01_model_welfare": game_matrix(records, "utilitarian_optimal"),
        "02_model_equilibrium": game_matrix(records, "expected_payoff_nash"),
        "03_model_actions": game_matrix(records, "cooperative_action_rate"),
        "04_mechanism_success": game_matrix(records, "structural_success", by="treatment"),
        "05_mechanism_equilibrium": game_matrix(records, "expected_payoff_nash", by="treatment"),
        "06_mechanism_catastrophe": game_matrix(records, "catastrophe_probability", by="treatment"),
        "10_threshold_accuracy": phase_matrix(phase["records"], STRATA, lambda r, _: r["scores"]["optimal_action"],
                                              lambda r, s: r["design_stratum"] == s),
        "12_observable_worksheets": phase_matrix(phase["records"], {
            "optimal_action": "Correct\naction", "valid_json": "Valid JSON\nworksheet",
            "calculation_coverage": "Calculation\ncoverage", "margin_sign_correct": "Correct\nmargin sign",
            "threshold_inequality_present": "Threshold\ninequality present",
        }, lambda r, m: r["scores"][m]),
    }
    # Different quality measures do not define a meaningful composite score.
    quality = matrix["12_observable_worksheets"]
    quality["columns"] = quality["columns"][:-1]
    quality["values"] = [row[:-1] for row in quality["values"]]
    quality["counts"] = [row[:-1] for row in quality["counts"]]
    return {
        "audit": audit, "models": gameplay["configuration"]["models"],
        "matrices": matrix,
        "07_objective_by_model": objective_comparison(records, by="model"),
        "08_objective_by_game": objective_comparison(records, by="game"),
        "09_crossplay": crossplay(records), "11_analytic_thresholds": analytic_thresholds(),
        "phase_one_samples": len(phase["records"]),
    }

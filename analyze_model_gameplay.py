"""Audit and compare completed true-model gameplay summary files."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


METRICS = (
    "valid_joint_action",
    "cooperative_action_rate",
    "first_action_rate",
    "second_action_rate",
    "mutual_cooperation",
    "mutual_competition",
    "catastrophic_realization",
    "catastrophe_probability",
    "expected_welfare",
    "expected_payoff_nash",
    "pareto_efficient",
    "coordination_success",
    "miscoordination",
    "structural_success",
    "utilitarian_optimal",
    "egalitarian_optimal",
    "expected_utilitarian_welfare_regret",
    "expected_egalitarian_welfare_regret",
)


def load_summary(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload.get("records"), list):
        raise ValueError(f"{path}: records must be a list")
    return payload


def _objective(record: Mapping[str, Any]) -> str:
    # Summaries produced before the explicit objective condition was added are
    # the original open-ended/naturalistic condition.
    return str(record.get("objective", "open_ended"))


def audit_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    records = payload["records"]
    dimensions = {
        "row_providers": sorted({record["row_provider"] for record in records}),
        "column_providers": sorted({record["column_provider"] for record in records}),
        "scenarios": sorted({record["scenario_id"] for record in records}),
        "treatments": sorted({record["treatment"] for record in records}),
        "objectives": sorted({_objective(record) for record in records}),
        "replicates": sorted({int(record.get("replicate", 0)) for record in records}),
    }
    expected = 1
    for values in dimensions.values():
        expected *= len(values)
    keys = [
        (
            record["row_provider"],
            record["column_provider"],
            record["scenario_id"],
            record["treatment"],
            _objective(record),
            int(record.get("replicate", 0)),
        )
        for record in records
    ]
    counts = Counter(keys)
    duplicates = [list(key) for key, count in counts.items() if count > 1]
    invalid = [
        record.get("sample_id", "unknown")
        for record in records
        if not bool(record.get("scores", {}).get("valid_joint_action"))
    ]
    failures = list(payload.get("failed_pairs", []))
    complete = len(records) == expected and not duplicates and not invalid and not failures
    return {
        "complete": complete,
        "record_count": len(records),
        "expected_record_count": expected,
        "dimensions": dimensions,
        "duplicate_cells": duplicates,
        "invalid_samples": invalid,
        "failed_pairs": failures,
    }


def _means(records: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    groups = list(records)
    return {
        metric: sum(
            float(record["scores"][metric])
            for record in groups
            if metric in record["scores"]
        )
        / sum(metric in record["scores"] for record in groups)
        for metric in METRICS
        if any(metric in record["scores"] for record in groups)
    }


def summarize(payload: Mapping[str, Any]) -> dict[str, Any]:
    records = payload["records"]
    by_treatment: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_scenario: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        by_treatment[record["treatment"]].append(record)
        by_scenario[record["scenario_id"]].append(record)

    model_choices: dict[str, list[bool]] = defaultdict(list)
    for record in records:
        first_action = record.get("first_action", record["cooperative_action"])
        row_action, column_action = record["joint_outcome"]["profile"]
        model_choices[record["row_provider"]].append(row_action == first_action)
        model_choices[record["column_provider"]].append(column_action == first_action)

    return {
        "overall": _means(records),
        "by_treatment": {
            key: {"games": len(group), **_means(group)}
            for key, group in sorted(by_treatment.items())
        },
        "by_scenario": {
            key: {"games": len(group), **_means(group)}
            for key, group in sorted(by_scenario.items())
        },
        "by_model_across_roles": {
            model: {
                "decisions": len(choices),
                "first_action_rate": sum(choices) / len(choices),
            }
            for model, choices in sorted(model_choices.items())
        },
    }


def compare(
    baseline: Mapping[str, Any], comparison: Mapping[str, Any]
) -> dict[str, Any]:
    left = summarize(baseline)
    right = summarize(comparison)
    output: dict[str, Any] = {}
    for grouping in ("overall", "by_treatment", "by_scenario"):
        if grouping == "overall":
            output[grouping] = {
                metric: right[grouping][metric] - left[grouping][metric]
                for metric in sorted(set(left[grouping]) & set(right[grouping]))
            }
            continue
        shared = sorted(set(left[grouping]) & set(right[grouping]))
        output[grouping] = {
            key: {
                metric: right[grouping][key][metric] - left[grouping][key][metric]
                for metric in sorted(
                    set(left[grouping][key]) & set(right[grouping][key]) - {"games"}
                )
            }
            for key in shared
        }
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit one gameplay summary and optionally compare it with another"
    )
    parser.add_argument("baseline", help="baseline JSON summary")
    parser.add_argument("comparison", nargs="?", help="comparison JSON summary")
    parser.add_argument("--output", help="optional path for the JSON analysis")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    baseline = load_summary(args.baseline)
    baseline_audit = audit_summary(baseline)
    result: dict[str, Any] = {
        "baseline": {
            "path": args.baseline,
            "audit": baseline_audit,
            "summary": summarize(baseline),
        }
    }
    if args.comparison:
        comparison = load_summary(args.comparison)
        comparison_audit = audit_summary(comparison)
        result["comparison"] = {
            "path": args.comparison,
            "audit": comparison_audit,
            "summary": summarize(comparison),
        }
        result["delta_comparison_minus_baseline"] = compare(baseline, comparison)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    audits = [baseline_audit]
    if args.comparison:
        audits.append(result["comparison"]["audit"])
    return 0 if all(audit["complete"] for audit in audits) else 1


if __name__ == "__main__":
    raise SystemExit(main())

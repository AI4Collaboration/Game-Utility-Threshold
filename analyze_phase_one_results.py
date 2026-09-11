"""Audit and analyze a completed Phase 1 threshold-evaluation artifact."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from run_phase_one_eval import aggregate_phase_one_records


def load_summary(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload.get("records"), list):
        raise ValueError(f"{path}: records must be a list")
    return payload


def audit_phase_one_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    records = list(payload["records"])
    configuration = dict(payload.get("configuration", {}))
    providers = tuple(configuration.get("providers", ()))
    expected_samples = int(configuration.get("samples_per_provider", 0))
    expected_total = expected_samples * len(providers)
    keys = [(record.get("provider"), record.get("sample_id")) for record in records]
    counts = Counter(keys)
    duplicates = [list(key) for key, count in counts.items() if count > 1]

    sample_sets = {
        provider: {
            record["sample_id"]
            for record in records
            if record.get("provider") == provider
        }
        for provider in providers
    }
    reference_samples = next(iter(sample_sets.values()), set())
    missing_by_provider = {
        provider: sorted(reference_samples - samples)
        for provider, samples in sample_sets.items()
        if samples != reference_samples
    }
    wrong_sample_counts = {
        provider: len(samples)
        for provider, samples in sample_sets.items()
        if len(samples) != expected_samples
    }
    invalid_json = [
        record["sample_id"] + "@" + record["provider"]
        for record in records
        if not bool(record.get("scores", {}).get("valid_json"))
    ]
    invalid_actions = [
        record["sample_id"] + "@" + record["provider"]
        for record in records
        if not bool(record.get("scores", {}).get("valid_action"))
    ]
    missing_prompts = [
        record["sample_id"] + "@" + record["provider"]
        for record in records
        if not record.get("prompt_and_messages")
    ]
    missing_outputs = [
        record["sample_id"] + "@" + record["provider"]
        for record in records
        if not record.get("model_output")
    ]
    failures = list(payload.get("failed_providers", []))
    completed = tuple(payload.get("completed_providers", ()))
    factorial_complete = (
        len(records) == expected_total
        and set(completed) == set(providers)
        and not duplicates
        and not missing_by_provider
        and not wrong_sample_counts
        and not missing_prompts
        and not missing_outputs
        and not failures
    )
    return {
        "complete": factorial_complete,
        "factorial_complete": factorial_complete,
        "all_actions_parseable": not invalid_actions,
        "all_worksheets_valid_json": not invalid_json,
        "record_count": len(records),
        "expected_record_count": expected_total,
        "providers": list(providers),
        "samples_per_provider": expected_samples,
        "completed_providers": list(completed),
        "duplicate_cells": duplicates,
        "missing_by_provider": missing_by_provider,
        "wrong_sample_counts": wrong_sample_counts,
        "invalid_json": invalid_json,
        "invalid_actions": invalid_actions,
        "missing_prompts": missing_prompts,
        "missing_outputs": missing_outputs,
        "failed_providers": failures,
    }


def threshold_transition_analysis(payload: Mapping[str, Any]) -> dict[str, Any]:
    records = list(payload["records"])
    grouped: dict[tuple[str, float], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for record in records:
        stratum = str(record["design_stratum"])
        if stratum in {"just_safe", "exact_boundary", "just_unsafe"}:
            grouped[(str(record["provider"]), float(record["d"]))][stratum] = record

    transition_records: list[dict[str, Any]] = []
    for (provider, defense), strata in sorted(grouped.items()):
        required = {"exact_boundary", "just_unsafe"}
        if defense > 0:
            required.add("just_safe")
        if not required.issubset(strata):
            continue
        actions = {
            stratum: strata[stratum]["observed_action"]
            for stratum in sorted(strata)
        }
        expected_pattern = (
            actions.get("just_safe", "COOPERATE") == "COOPERATE"
            and actions["exact_boundary"] == "COOPERATE"
            and actions["just_unsafe"] == "ATTACK"
        )
        transition_records.append({
            "provider": provider,
            "defense": defense,
            "actions": actions,
            "expected_threshold_transition": expected_pattern,
        })
    return {
        "transition_count": len(transition_records),
        "expected_transition_rate": (
            sum(record["expected_threshold_transition"] for record in transition_records)
            / len(transition_records)
            if transition_records
            else 0.0
        ),
        "records": transition_records,
    }


def audit_policy_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    records = list(payload["records"])
    configuration = dict(payload.get("configuration", {}))
    policies = tuple(configuration.get("policies", ()))
    samples_per_policy = int(configuration.get("samples_per_policy", 0))
    expected = len(policies) * samples_per_policy
    counts = Counter((record.get("policy"), record.get("sample_id")) for record in records)
    duplicates = [list(key) for key, count in counts.items() if count > 1]
    wrong_counts = {
        policy: sum(record.get("policy") == policy for record in records)
        for policy in policies
        if sum(record.get("policy") == policy for record in records) != samples_per_policy
    }
    statuses = dict(payload.get("statuses", {}))
    invalid_probabilistic_certificates = [
        record["sample_id"] + "@" + record["policy"]
        for record in records
        if record.get("probabilistic_certificate") is not None
        and not bool(record["probabilistic_certificate"].get("valid"))
    ]
    exact_policies = {"threshold", "proof", "dupoc", "cupod"}
    invalid_exact_policy_decisions = [
        record["sample_id"] + "@" + record["policy"]
        for record in records
        if record.get("policy") in exact_policies
        and not bool(record.get("scores", {}).get("optimal_action"))
    ]
    complete = (
        len(records) == expected
        and set(statuses) == set(policies)
        and all(status == "success" for status in statuses.values())
        and not duplicates
        and not wrong_counts
        and not invalid_probabilistic_certificates
        and not invalid_exact_policy_decisions
    )
    return {
        "complete": complete,
        "record_count": len(records),
        "expected_record_count": expected,
        "policies": list(policies),
        "samples_per_policy": samples_per_policy,
        "statuses": statuses,
        "duplicate_cells": duplicates,
        "wrong_sample_counts": wrong_counts,
        "invalid_probabilistic_certificates": invalid_probabilistic_certificates,
        "invalid_exact_policy_decisions": invalid_exact_policy_decisions,
    }


def analyze(
    payload: Mapping[str, Any],
    policy_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    records = list(payload["records"])
    incorrect = [
        {
            "sample_id": record["sample_id"],
            "provider": record["provider"],
            "v": record["v"],
            "d": record["d"],
            "design_stratum": record["design_stratum"],
            "expected_action": record["expected_action"],
            "observed_action": record["observed_action"],
            "utility_regret": record["scores"].get("utility_regret"),
        }
        for record in records
        if not bool(record.get("scores", {}).get("optimal_action"))
    ]
    result = {
        "audit": audit_phase_one_summary(payload),
        "summary": aggregate_phase_one_records(records),
        "threshold_transitions": threshold_transition_analysis(payload),
        "incorrect_decisions": incorrect,
    }
    if policy_payload is not None:
        result["policy_baselines"] = {
            "audit": audit_policy_summary(policy_payload),
            "aggregates": policy_payload.get("aggregates", {}),
        }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit and analyze a Phase 1 model-evaluation summary"
    )
    parser.add_argument("summary", help="Phase 1 JSON summary")
    parser.add_argument("--policies", help="optional Phase 1 policy-baseline JSON")
    parser.add_argument("--output", help="optional JSON analysis output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = analyze(
        load_summary(args.summary),
        load_summary(args.policies) if args.policies else None,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    audits = [result["audit"]]
    if "policy_baselines" in result:
        audits.append(result["policy_baselines"]["audit"])
    return 0 if all(audit["complete"] for audit in audits) else 1


if __name__ == "__main__":
    raise SystemExit(main())

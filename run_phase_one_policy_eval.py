"""Execute every Phase 1 deterministic and proof-carrying policy in Inspect."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from inspect_ai import eval

from utility_threshold_inspect import build_phase_one_samples, utility_threshold_policy_eval


POLICIES = (
    "cooperate",
    "defect",
    "threshold",
    "probabilistic",
    "proof",
    "dupoc",
    "cupod",
    "pdupoc",
)


def aggregate_policy_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[record["policy"]].append(record)
    return {
        policy: {
            "samples": len(group),
            "optimal_action_rate": sum(
                float(record["scores"]["optimal_action"]) for record in group
            ) / len(group),
            "mean_utility_regret": sum(
                float(record["scores"]["utility_regret"]) for record in group
            ) / len(group),
            "valid_certificate_rate": sum(
                float(bool(record.get("certificate", {}).get("valid")))
                for record in group
            ) / len(group),
            "valid_probabilistic_certificate_rate": (
                sum(
                    float(bool(record["probabilistic_certificate"]["valid"]))
                    for record in group
                    if record.get("probabilistic_certificate") is not None
                )
                / sum(
                    record.get("probabilistic_certificate") is not None
                    for record in group
                )
                if any(record.get("probabilistic_certificate") is not None for record in group)
                else None
            ),
        }
        for policy, group in sorted(groups.items())
    }


def _record(sample: Any, policy: str, log_path: str) -> dict[str, Any]:
    metadata = dict(sample.metadata or {})
    score = next(iter(sample.scores.values()))
    return {
        "sample_id": sample.id,
        "policy": policy,
        "v": metadata["v"],
        "d": metadata["d"],
        "design_stratum": metadata["design_stratum"],
        "threshold_region": metadata["threshold_region"],
        "expected_action": metadata["expected_action"],
        "observed_action": score.answer,
        "scores": score.value,
        "certificate": metadata.get("certificate"),
        "probabilistic_certificate": metadata.get("probabilistic_certificate"),
        "inspect_log": Path(log_path).name,
    }


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    fields = [
        "sample_id",
        "policy",
        "v",
        "d",
        "design_stratum",
        "threshold_region",
        "expected_action",
        "observed_action",
        "optimal_action",
        "utility_regret",
        "certificate_valid",
        "probabilistic_certificate_valid",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({
                **{field: record.get(field) for field in fields[:8]},
                "optimal_action": record["scores"]["optimal_action"],
                "utility_regret": record["scores"]["utility_regret"],
                "certificate_valid": record.get("certificate", {}).get("valid"),
                "probabilistic_certificate_valid": (
                    record["probabilistic_certificate"]["valid"]
                    if record.get("probabilistic_certificate") is not None
                    else None
                ),
            })


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", choices=POLICIES, action="append")
    parser.add_argument("--log-dir", default="./logs/phase_one_policies")
    parser.add_argument("--output", default="./results/phase_one_policy_baselines.json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    policies = tuple(dict.fromkeys(args.policy or POLICIES))
    records: list[dict[str, Any]] = []
    statuses: dict[str, str] = {}
    for policy in policies:
        logs = eval(
            utility_threshold_policy_eval(policy),
            model="none",
            display="plain",
            log_dir=args.log_dir,
            max_samples=16,
            fail_on_error=False,
            ctl_server=False,
        )
        statuses[policy] = ",".join(str(log.status) for log in logs)
        records.extend(
            _record(sample, policy, str(log.location))
            for log in logs
            for sample in (log.samples or [])
        )

    expected = len(policies) * len(build_phase_one_samples())
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "policies": list(policies),
            "samples_per_policy": len(build_phase_one_samples()),
            "expected_total_samples": expected,
            "private_chain_of_thought_claimed": False,
        },
        "statuses": statuses,
        "complete": len(records) == expected and all(status == "success" for status in statuses.values()),
        "aggregates": aggregate_policy_records(records),
        "records": records,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(output.with_suffix(".csv"), records)
    print(json.dumps({"output": str(output), "samples": len(records), "complete": payload["complete"]}))
    return 0 if payload["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

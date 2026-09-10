"""Run and summarize the full cross-provider self-play/cross-play matrix."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from dotenv import load_dotenv
from inspect_ai import eval
from inspect_ai.model import get_model

from model_gameplay_inspect import (
    GAMEPLAY_OBJECTIVES,
    GAMEPLAY_SCENARIOS,
    GAMEPLAY_TREATMENTS,
    model_gameplay_eval,
)
from multi_model_eval import MODEL_MATRIX


def ordered_pairings(providers: Iterable[str]) -> tuple[tuple[str, str], ...]:
    """All self-play and both role orders of every cross-provider pairing."""
    names = tuple(dict.fromkeys(providers))
    if not names:
        raise ValueError("at least one provider is required")
    return tuple((row, column) for row in names for column in names)


def _numeric_means(records: Iterable[Mapping[str, Any]]) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for record in records:
        for key, value in record.get("scores", {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values[key].append(float(value))
    return {
        key: sum(numbers) / len(numbers)
        for key, numbers in sorted(values.items())
        if numbers
    }


def aggregate_gameplay_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_treatment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_objective: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_treatment[record["treatment"]].append(record)
        by_scenario[record["scenario_id"]].append(record)
        by_objective[record["objective"]].append(record)
        by_pair[f"{record['row_provider']}->{record['column_provider']}"].append(record)

    model_roles: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        joint = record.get("joint_outcome", {})
        if not joint.get("valid_joint_action"):
            continue
        first_action = record.get("first_action", record["cooperative_action"])
        row_action, column_action = joint["profile"]
        model_roles[record["row_provider"]]["games"].append(1.0)
        model_roles[record["row_provider"]]["first_action_rate"].append(
            float(row_action == first_action)
        )
        model_roles[record["row_provider"]]["expected_regret"].append(
            float(joint["row_expected_regret"])
        )
        model_roles[record["column_provider"]]["games"].append(1.0)
        model_roles[record["column_provider"]]["first_action_rate"].append(
            float(column_action == first_action)
        )
        model_roles[record["column_provider"]]["expected_regret"].append(
            float(joint["column_expected_regret"])
        )
    model_summary = {
        model: {
            "decision_count": int(sum(metrics["games"])),
            "first_action_rate": sum(metrics["first_action_rate"]) / len(metrics["first_action_rate"]),
            "mean_expected_regret": sum(metrics["expected_regret"]) / len(metrics["expected_regret"]),
        }
        for model, metrics in sorted(model_roles.items())
        if metrics["games"]
    }
    return {
        "completed_joint_games": len(records),
        "overall": _numeric_means(records),
        "by_treatment": {
            key: {"games": len(group), **_numeric_means(group)}
            for key, group in sorted(by_treatment.items())
        },
        "by_scenario": {
            key: {"games": len(group), **_numeric_means(group)}
            for key, group in sorted(by_scenario.items())
        },
        "by_objective": {
            key: {"games": len(group), **_numeric_means(group)}
            for key, group in sorted(by_objective.items())
        },
        "by_ordered_pair": {
            key: {"games": len(group), **_numeric_means(group)}
            for key, group in sorted(by_pair.items())
        },
        "by_model_across_roles": model_summary,
    }


def _record_from_sample(
    sample: Any,
    *,
    row_provider: str,
    column_provider: str,
    log_path: str,
) -> dict[str, Any]:
    metadata = dict(sample.metadata or {})
    scores = next(iter(sample.scores.values())).value if sample.scores else {}
    if not isinstance(scores, dict):
        scores = {"score": scores}
    actions = tuple(metadata["actions"])
    return {
        "sample_id": sample.id,
        "row_provider": row_provider,
        "column_provider": column_provider,
        "row_model": metadata.get("row_model", MODEL_MATRIX[row_provider]),
        "column_model": metadata.get("column_model", MODEL_MATRIX[column_provider]),
        "scenario_id": metadata["scenario_id"],
        "treatment": metadata["treatment"],
        "objective": metadata.get("objective", "open_ended"),
        "replicate": metadata["replicate"],
        "resolution_seed": metadata["resolution_seed"],
        "cooperative_action": actions[0],
        "competitive_action": actions[1],
        "first_action": actions[0],
        "second_action": actions[1],
        "scores": scores,
        "joint_outcome": metadata.get("joint_outcome"),
        "inspect_log": log_path,
    }


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    score_keys = sorted({key for record in records for key in record["scores"]})
    fields = [
        "sample_id",
        "row_provider",
        "column_provider",
        "scenario_id",
        "treatment",
        "objective",
        "replicate",
        "row_action",
        "column_action",
        *score_keys,
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            joint = record.get("joint_outcome") or {}
            profile = joint.get("profile", ["UNKNOWN", "UNKNOWN"])
            row = {
                key: record[key]
                for key in (
                    "sample_id",
                    "row_provider",
                    "column_provider",
                    "scenario_id",
                    "treatment",
                    "objective",
                    "replicate",
                )
            }
            row["row_action"] = profile[0]
            row["column_action"] = profile[1]
            row.update(record["scores"])
            writer.writerow(row)


def _save_checkpoint(
    output_path: Path,
    *,
    configuration: Mapping[str, Any],
    completed_pairs: list[str],
    failed_pairs: list[dict[str, str]],
    records: list[dict[str, Any]],
) -> None:
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "configuration": dict(configuration),
        "completed_pairs": completed_pairs,
        "failed_pairs": failed_pairs,
        "aggregates": aggregate_gameplay_records(records),
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_csv(output_path.with_suffix(".csv"), records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run true model self-play and ordered cross-provider play"
    )
    parser.add_argument("--provider", choices=tuple(MODEL_MATRIX), action="append")
    parser.add_argument("--scenario", choices=GAMEPLAY_SCENARIOS, action="append")
    parser.add_argument("--treatment", choices=GAMEPLAY_TREATMENTS, action="append")
    parser.add_argument("--objective", choices=GAMEPLAY_OBJECTIVES, action="append")
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=700)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-samples", type=int, default=2)
    parser.add_argument("--log-dir", default="./logs/model_gameplay")
    parser.add_argument("--output", default="./results/model_gameplay_summary.json")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="run one OpenAI-to-Anthropic baseline deployment match",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required in the local environment")
    if args.replicates <= 0 or args.max_tokens <= 0 or args.max_samples <= 0:
        raise SystemExit("replicates, max-tokens, and max-samples must be positive")

    if args.smoke:
        providers = ("openai", "anthropic")
        pairings = (("openai", "anthropic"),)
        scenarios = ("frontier_deployment_race",)
        treatments = ("baseline",)
        objectives = ("individual_expected_utility",)
    else:
        providers = tuple(args.provider or MODEL_MATRIX)
        pairings = ordered_pairings(providers)
        scenarios = tuple(args.scenario or GAMEPLAY_SCENARIOS)
        treatments = tuple(args.treatment or GAMEPLAY_TREATMENTS)
        objectives = tuple(args.objective or ("individual_expected_utility",))

    output_path = Path(args.output)
    records: list[dict[str, Any]] = []
    completed_pairs: list[str] = []
    failed_pairs: list[dict[str, str]] = []
    if output_path.exists():
        if not args.resume:
            raise SystemExit(f"{output_path} already exists; pass --resume or choose another output")
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        records = list(existing.get("records", []))
        completed_pairs = list(existing.get("completed_pairs", []))
        failed_pairs = list(existing.get("failed_pairs", []))

    configuration = {
        "providers": list(providers),
        "models": {provider: MODEL_MATRIX[provider] for provider in providers},
        "ordered_pair_count": len(pairings),
        "scenarios": list(scenarios),
        "treatments": list(treatments),
        "objectives": list(objectives),
        "replicates": args.replicates,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "role_isolation": True,
        "provider_data_collection": "deny",
        "private_chain_of_thought_claimed": False,
    }
    provider_options = {"data_collection": "deny", "allow_fallbacks": True}
    for row_provider, column_provider in pairings:
        pair_id = f"{row_provider}->{column_provider}"
        if pair_id in completed_pairs:
            continue
        game_count = len(scenarios) * len(treatments) * len(objectives) * args.replicates
        print(f"Running {pair_id} ({game_count} games)", flush=True)
        try:
            row_model = get_model(
                MODEL_MATRIX[row_provider],
                memoize=False,
                provider=provider_options,
            )
            column_model = get_model(
                MODEL_MATRIX[column_provider],
                memoize=False,
                provider=provider_options,
            )
            logs = eval(
                model_gameplay_eval(
                    scenario_ids=scenarios,
                    treatments=treatments,
                    objectives=objectives,
                    replicates=args.replicates,
                    max_tokens=args.max_tokens,
                    temperature=args.temperature,
                ),
                model="none",
                model_roles={"row_agent": row_model, "column_agent": column_model},
                display="plain",
                log_dir=args.log_dir,
                max_samples=args.max_samples,
                retry_on_error=2,
                fail_on_error=False,
                ctl_server=False,
            )
            for log in logs:
                log_path = str(log.location)
                for sample in log.samples or []:
                    records.append(
                        _record_from_sample(
                            sample,
                            row_provider=row_provider,
                            column_provider=column_provider,
                            log_path=log_path,
                        )
                    )
            if all(str(log.status) == "success" for log in logs):
                completed_pairs.append(pair_id)
            else:
                failed_pairs.append({
                    "pair": pair_id,
                    "error": "; ".join(str(log.error) for log in logs if log.error),
                })
        except Exception as exc:
            failed_pairs.append({"pair": pair_id, "error": f"{type(exc).__name__}: {exc}"})
        _save_checkpoint(
            output_path,
            configuration=configuration,
            completed_pairs=completed_pairs,
            failed_pairs=failed_pairs,
            records=records,
        )

    print(
        json.dumps(
            {
                "output": str(output_path),
                "csv": str(output_path.with_suffix('.csv')),
                "completed_pairs": len(completed_pairs),
                "failed_pairs": len(failed_pairs),
                "joint_games": len(records),
            },
            sort_keys=True,
        )
    )
    return 0 if not failed_pairs else 1


if __name__ == "__main__":
    raise SystemExit(main())

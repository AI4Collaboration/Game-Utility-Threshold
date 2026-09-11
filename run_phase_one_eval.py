"""Run and summarize the research-grade Phase 1 model evaluation matrix."""

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

from multi_model_eval import MODEL_MATRIX
from utility_threshold_inspect import build_phase_one_samples, utility_threshold_model_eval


def selected_providers(providers: Iterable[str] | None = None) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(providers or MODEL_MATRIX))
    if not names:
        raise ValueError("at least one provider is required")
    unknown = set(names) - set(MODEL_MATRIX)
    if unknown:
        raise ValueError(f"unknown providers: {sorted(unknown)}")
    return names


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


def aggregate_phase_one_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_stratum: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_region: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_provider[record["provider"]].append(record)
        by_stratum[record["design_stratum"]].append(record)
        by_region[record["threshold_region"]].append(record)

    def grouped(groups: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
        return {
            name: {"samples": len(group), **_numeric_means(group)}
            for name, group in sorted(groups.items())
        }

    return {
        "completed_samples": len(records),
        "overall": _numeric_means(records),
        "by_provider": grouped(by_provider),
        "by_design_stratum": grouped(by_stratum),
        "by_threshold_region": grouped(by_region),
    }


def _model_record(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def _record_from_sample(sample: Any, *, provider: str, log_path: str) -> dict[str, Any]:
    metadata = dict(sample.metadata or {})
    score = next(iter(sample.scores.values())) if sample.scores else None
    scores = score.value if score is not None else {}
    if not isinstance(scores, dict):
        scores = {"score": scores}
    score_metadata = dict(score.metadata or {}) if score is not None else {}
    return {
        "sample_id": sample.id,
        "provider": provider,
        "model": MODEL_MATRIX[provider],
        "v": metadata["v"],
        "d": metadata["d"],
        "critical_v": metadata["critical_v"],
        "distance_to_threshold": metadata["distance_to_threshold"],
        "design_stratum": metadata["design_stratum"],
        "threshold_region": metadata["threshold_region"],
        "near_boundary": metadata["near_boundary"],
        "expected_action": metadata["expected_action"],
        "observed_action": score.answer if score is not None else "UNKNOWN",
        "scores": scores,
        "ground_truth_certificate": metadata["ground_truth_certificate"],
        "parsed_worksheet": score_metadata.get(
            "parsed_worksheet", metadata.get("parsed_worksheet")
        ),
        "prompt_and_messages": [_model_record(message) for message in (sample.messages or [])],
        "model_output": _model_record(sample.output),
        "inspect_log": Path(log_path).name,
        "sample_error": _model_record(sample.error),
    }


def _write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    score_keys = sorted({key for record in records for key in record["scores"]})
    fields = [
        "sample_id",
        "provider",
        "model",
        "v",
        "d",
        "critical_v",
        "distance_to_threshold",
        "design_stratum",
        "threshold_region",
        "expected_action",
        "observed_action",
        *score_keys,
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {key: record[key] for key in fields if key in record}
            row.update(record["scores"])
            writer.writerow(row)


def _save_checkpoint(
    output_path: Path,
    *,
    configuration: Mapping[str, Any],
    completed_providers: list[str],
    failed_providers: list[dict[str, str]],
    records: list[dict[str, Any]],
) -> None:
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "configuration": dict(configuration),
        "completed_providers": completed_providers,
        "failed_providers": failed_providers,
        "aggregates": aggregate_phase_one_records(records),
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(output_path.with_suffix(".csv"), records)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the cross-provider Phase 1 sequential threshold evaluation"
    )
    parser.add_argument("--provider", choices=tuple(MODEL_MATRIX), action="append")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-samples", type=int, default=8)
    parser.add_argument("--log-dir", default="./logs/phase_one")
    parser.add_argument("--output", default="./results/phase_one_model_eval.json")
    parser.add_argument("--resume", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required in the local environment")
    if args.max_tokens <= 0 or args.max_samples <= 0:
        raise SystemExit("max-tokens and max-samples must be positive")

    providers = selected_providers(args.provider)
    sample_count = len(build_phase_one_samples())
    output_path = Path(args.output)
    records: list[dict[str, Any]] = []
    completed_providers: list[str] = []
    failed_providers: list[dict[str, str]] = []
    if output_path.exists():
        if not args.resume:
            raise SystemExit(f"{output_path} already exists; pass --resume or choose another output")
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        records = list(existing.get("records", []))
        completed_providers = list(existing.get("completed_providers", []))
        failed_providers = list(existing.get("failed_providers", []))

    configuration = {
        "providers": list(providers),
        "models": {provider: MODEL_MATRIX[provider] for provider in providers},
        "samples_per_provider": sample_count,
        "expected_total_samples": sample_count * len(providers),
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "dataset_design": "25 broad + 14 exact/adjacent threshold cases",
        "provider_data_collection": "deny",
        "provider_fallbacks_allowed": True,
        "private_chain_of_thought_claimed": False,
    }
    provider_options = {"data_collection": "deny", "allow_fallbacks": True}
    for provider in providers:
        if provider in completed_providers:
            continue
        print(f"Running {provider} ({sample_count} samples)", flush=True)
        try:
            logs = eval(
                utility_threshold_model_eval(),
                model=MODEL_MATRIX[provider],
                model_args={"provider": provider_options},
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                reasoning_effort="minimal",
                display="plain",
                log_dir=args.log_dir,
                max_samples=args.max_samples,
                retry_on_error=2,
                fail_on_error=False,
                ctl_server=False,
            )
            provider_records = [
                _record_from_sample(
                    sample,
                    provider=provider,
                    log_path=str(log.location),
                )
                for log in logs
                for sample in (log.samples or [])
            ]
            records.extend(provider_records)
            if (
                len(provider_records) == sample_count
                and all(str(log.status) == "success" for log in logs)
            ):
                completed_providers.append(provider)
            else:
                failed_providers.append({
                    "provider": provider,
                    "error": (
                        f"received {len(provider_records)}/{sample_count} samples; "
                        + "; ".join(str(log.error) for log in logs if log.error)
                    ),
                })
        except Exception as exc:
            failed_providers.append({
                "provider": provider,
                "error": f"{type(exc).__name__}: {exc}",
            })
        _save_checkpoint(
            output_path,
            configuration=configuration,
            completed_providers=completed_providers,
            failed_providers=failed_providers,
            records=records,
        )

    print(json.dumps({
        "output": str(output_path),
        "csv": str(output_path.with_suffix('.csv')),
        "completed_providers": len(completed_providers),
        "failed_providers": len(failed_providers),
        "samples": len(records),
    }, sort_keys=True))
    return 0 if len(completed_providers) == len(providers) and not failed_providers else 1


if __name__ == "__main__":
    raise SystemExit(main())

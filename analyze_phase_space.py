"""Summarize observed symmetric 2x2 decisions without inventing missing cells.

Uncertainty resamples independent sample_id episodes, preserving both participant
records in self-play. These intervals describe sampling variability in the logged
experiment, not uncertainty about an unobserved model population.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CELL_DIMENSIONS = ("model", "opponent_model", "mode", "s", "t", "opponent_cooperation_probability")
MODES = {"self_play", "cross_play", "fixed_belief"}
DEFAULT_BOOTSTRAP_SAMPLES = 2000
DEFAULT_SEED = 1729


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) else None


def _valid(record: Mapping[str, Any]) -> bool:
    return record.get("valid") is True and record.get("action") in {"C", "D"}


def _episode(record: Mapping[str, Any]) -> tuple[str, str]:
    return (str(record.get("_source_run", "")), str(record["sample_id"]))


def _cell_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    # In joint play this field can describe the realized opponent action. It is
    # an experimental condition only in fixed-belief mode.
    belief = record.get("opponent_cooperation_probability") if record["mode"] == "fixed_belief" else None
    return (str(record["model"]), str(record.get("opponent_model") or ""),
            record["mode"], float(record["s"]), float(record["t"]), _number(belief))


def _sorted_keys(keys: Iterable[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    return sorted(keys, key=lambda key: tuple("" if value is None else str(value) for value in key))


def _safe_configuration(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): ("[redacted]" if any(word in str(key).lower() for word in
                       ("api_key", "apikey", "secret", "password", "credential", "authorization"))
                       else _safe_configuration(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_safe_configuration(item) for item in value]
    return value


def validate_payload(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version", 1) != 1:
        raise ValueError("unsupported phase-space schema_version")
    if not isinstance(payload.get("records"), list):
        raise ValueError("records must be a list")
    for index, record in enumerate(payload["records"]):
        if not isinstance(record, Mapping):
            raise ValueError(f"record {index} must be an object")
        for field in ("sample_id", "model", "mode", "role", "s", "t"):
            if field not in record:
                raise ValueError(f"record {index} missing {field}")
        if not str(record["sample_id"]):
            raise ValueError(f"record {index} has an empty sample_id")
        if record["mode"] not in MODES or record["role"] not in {"row", "column"}:
            raise ValueError(f"record {index} has an unsupported mode or role")
        if _number(record["s"]) is None or _number(record["t"]) is None:
            raise ValueError(f"record {index} requires finite s and t")
        if record.get("R", 1) != 1 or record.get("P", 0) != 0:
            raise ValueError("phase-space analysis requires normalized R=1 and P=0")
        if record["mode"] == "fixed_belief":
            belief = _number(record.get("opponent_cooperation_probability"))
            if belief is None or not 0 <= belief <= 1:
                raise ValueError(f"record {index} requires a fixed belief in [0, 1]")


def load_runs(paths: Sequence[str | Path]) -> dict[str, Any]:
    """Merge files; namespace episodes by input run to preserve independent runs."""
    resolved = [Path(path).resolve() for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("the same input file was supplied more than once")
    result: dict[str, Any] = {"schema_version": 1, "records": [], "points": [], "errors": [], "runs": []}
    seen_contents: set[str] = set()
    points: dict[tuple[float, float], dict[str, Any]] = {}
    for path in resolved:
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest in seen_contents:
            raise ValueError("identical input files cannot count as independent runs")
        seen_contents.add(digest)
        payload = json.loads(raw)
        validate_payload(payload)
        # Content identity is stable under moving a file and avoids path leakage.
        result["records"].extend({**record, "_source_run": digest} for record in payload["records"])
        for point in payload.get("points", []):
            s, t = _number(point.get("s")), _number(point.get("t"))
            if s is not None and t is not None:
                points[(s, t)] = dict(point)
        result["errors"].extend(payload.get("errors", []))
        result["runs"].append({"path": str(path), "sha256": digest,
                               "configuration": _safe_configuration(payload.get("configuration", {})),
                               "budget": _safe_configuration(payload.get("budget", {}))})
    result["points"] = [points[key] for key in sorted(points)]
    return result


def audit_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    validate_payload(payload)
    records = payload["records"]
    decisions = Counter((_episode(record), record["role"]) for record in records)
    episodes: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        episodes[_episode(record)].append(record)
    inconsistent: list[str] = []
    incomplete: list[str] = []
    for (_, sample_id), group in episodes.items():
        joint = [record for record in group if record["mode"] != "fixed_belief"]
        if not joint:
            continue
        if {record["role"] for record in joint} != {"row", "column"}:
            incomplete.append(sample_id)
        if len({(record["mode"], float(record["s"]), float(record["t"])) for record in joint}) != 1:
            inconsistent.append(sample_id)
        if len(joint) == 2 and all(_valid(record) for record in joint):
            if any(record.get("opponent_action") != joint[1 - index]["action"]
                   for index, record in enumerate(joint)):
                inconsistent.append(sample_id)
    duplicates = [{"sample_id": key[0][1], "role": key[1], "count": count}
                  for key, count in decisions.items() if count > 1]
    return {"record_count": len(records), "episode_count": len(episodes),
            "valid_decisions": sum(_valid(record) for record in records),
            "invalid_decisions": sum(not _valid(record) for record in records),
            "duplicate_decisions": duplicates,
            "incomplete_joint_episodes": sorted(set(incomplete)),
            "inconsistent_joint_episodes": sorted(set(inconsistent)),
            "error_count": len(payload.get("errors", [])),
            "models": sorted({str(record["model"]) for record in records}),
            "modes": sorted({str(record["mode"]) for record in records}),
            "observed_point_count": len({(float(record["s"]), float(record["t"])) for record in records}),
            "planned_point_count": len(payload.get("points", [])),
            "valid_flag_conflicts": sum(record.get("valid") is True and not _valid(record) for record in records)}


def _quantile(values: Sequence[float], fraction: float) -> float:
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def clustered_interval(
    clusters: Sequence[tuple[float, int]], *, samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = DEFAULT_SEED,
) -> tuple[float | None, float | None]:
    """Percentile 95% CI for a decision-weighted ratio, resampling episodes.

    A cluster is (sum of valid decision values, number of valid decisions).
    Zero-denominator episodes remain in the resampling frame. No interval is
    claimed from a single informative episode, even when it has two roles.
    """
    if samples <= 0 or sum(count > 0 for _, count in clusters) < 2:
        return None, None
    randomizer = random.Random(seed)
    estimates: list[float] = []
    for _ in range(samples):
        draw = randomizer.choices(clusters, k=len(clusters))
        denominator = sum(count for _, count in draw)
        if denominator:
            estimates.append(sum(total for total, _ in draw) / denominator)
    if not estimates:
        return None, None
    estimates.sort()
    return _quantile(estimates, 0.025), _quantile(estimates, 0.975)


def _metric(records: Sequence[Mapping[str, Any]], name: str, samples: int, seed: int) -> dict[str, Any]:
    clusters: dict[tuple[str, str], list[float]] = defaultdict(list)
    for record in records:
        values = clusters[_episode(record)]
        if _valid(record):
            value = (float(record["action"] == "C") if name == "cooperation"
                     else _number(record.get(name)))
            if value is not None:
                values.append(value)
    observations = [value for values in clusters.values() for value in values]
    low, high = clustered_interval([(sum(values), len(values)) for values in clusters.values()], samples=samples, seed=seed)
    return {"mean": sum(observations) / len(observations) if observations else None,
            "n": len(observations), "episodes": sum(bool(values) for values in clusters.values()),
            "ci_low": low, "ci_high": high}


def _joint_metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    # Each realized profile contributes once, including in a two-role model cell.
    episodes: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        if record["mode"] != "fixed_belief":
            episodes[_episode(record)].append(record)
    metrics: dict[str, list[float]] = {name: [] for name in ("pure_nash", "joint_welfare", "welfare_optimal")}
    valid_profiles = 0
    for group in episodes.values():
        eligible = [record for record in group if _valid(record) and record.get("opponent_action") in {"C", "D"}]
        if not eligible:
            continue
        valid_profiles += 1
        for name in metrics:
            values = [float(record[name]) for record in eligible
                      if isinstance(record.get(name), (int, float)) and math.isfinite(float(record[name]))]
            if values:
                if any(abs(value - values[0]) > 1e-9 for value in values):
                    raise ValueError(f"conflicting {name} values within sample_id {group[0]['sample_id']}")
                metrics[name].append(values[0])
    return {"joint_episodes": len(episodes), "valid_joint_episodes": valid_profiles,
            **{f"{name}_rate" if name != "joint_welfare" else "mean_joint_welfare":
               sum(values) / len(values) if values else None for name, values in metrics.items()},
            **{f"{name}_episodes": len(values) for name, values in metrics.items()}}


def _summarize_group(records: Sequence[Mapping[str, Any]], samples: int, seed: int) -> dict[str, Any]:
    n = len(records)
    valid = sum(_valid(record) for record in records)
    cooperative = sum(_valid(record) and record["action"] == "C" for record in records)
    cooperation = _metric(records, "cooperation", samples, seed)
    result = {"n_decisions": n, "n_episodes": len({_episode(record) for record in records}),
              "n_valid": valid, "n_invalid": n - valid,
              "n_transport_errors": sum(not _valid(record) and "usage" not in record for record in records),
              "n_invalid_model_outputs": sum(not _valid(record) and "usage" in record for record in records),
              "n_valid_episodes": cooperation["episodes"],
              "n_cooperate": cooperative, "n_defect": valid - cooperative,
              "cooperation_rate_valid": cooperation["mean"],
              "defection_rate_valid": (valid - cooperative) / valid if valid else None,
              "cooperation_rate_all": cooperative / n if n else None,
              "defection_rate_all": (valid - cooperative) / n if n else None,
              "invalid_rate": (n - valid) / n if n else None,
              "cooperation_ci_low": cooperation["ci_low"], "cooperation_ci_high": cooperation["ci_high"]}
    for name in ("expected_utility", "regret"):
        estimate = _metric(records, name, samples, seed)
        result.update({f"mean_{name}": estimate["mean"], f"{name}_n": estimate["n"],
                       f"{name}_ci_low": estimate["ci_low"], f"{name}_ci_high": estimate["ci_high"]})
    result.update(_joint_metrics(records))
    return result


def _convergence(records: Sequence[Mapping[str, Any]], dimensions: Mapping[str, Any]) -> list[dict[str, Any]]:
    episodes: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        episodes[_episode(record)].append(record)
    ordered = sorted(episodes.values(), key=lambda group: (str(group[0].get("_source_run", "")),
                     _number(group[0].get("replicate")) or 0, str(group[0]["sample_id"])))
    cumulative_valid = cumulative_cooperative = 0
    points = []
    for index, group in enumerate(ordered, 1):
        cumulative_valid += sum(_valid(record) for record in group)
        cumulative_cooperative += sum(_valid(record) and record["action"] == "C" for record in group)
        points.append({**dimensions, "episodes": index, "valid_decisions": cumulative_valid,
                       "cumulative_cooperation_rate": cumulative_cooperative / cumulative_valid if cumulative_valid else None})
    return points


def summarize(payload: Mapping[str, Any], *, bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
              seed: int = DEFAULT_SEED) -> dict[str, Any]:
    if bootstrap_samples < 0:
        raise ValueError("bootstrap_samples must be nonnegative")
    audit = audit_summary(payload)
    if audit["duplicate_decisions"]:
        raise ValueError("duplicate sample_id/role records would double-count decisions")
    if audit["inconsistent_joint_episodes"]:
        raise ValueError("inconsistent joint episode records")
    records = payload["records"]
    cell_groups: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    model_groups: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        cell_groups[_cell_key(record)].append(record)
        model_groups[(str(record["model"]), str(record.get("opponent_model") or ""), record["mode"])].append(record)
    cells, convergence = [], []
    for key in _sorted_keys(cell_groups):
        dimensions = dict(zip(CELL_DIMENSIONS, key))
        cells.append({**dimensions, **_summarize_group(cell_groups[key], bootstrap_samples, seed)})
        convergence.extend(_convergence(cell_groups[key], dimensions))
    return {"schema_version": 1, "data_kind": "observed_model_decisions" if records else "no_observed_decisions",
            "uncertainty": {"method": "95% percentile episode-cluster bootstrap",
                            "cluster": "source_run + sample_id; roles stay together",
                            "bootstrap_samples": bootstrap_samples, "seed": seed,
                            "minimum_informative_episodes": 2,
                            "interpretation": "Decision-weighted, conditional on valid actions; no interval for a single informative episode. Small or unanimous samples can produce degenerate intervals; this does not establish certainty.",
                            "convergence": "Descriptive within-cell cumulative rates, ordered by source run and replicate; not a proof of convergence."},
            "audit": audit, "runs": _safe_configuration(payload.get("runs", [])),
            "configuration": _safe_configuration(payload.get("configuration", {})),
            "budget": _safe_configuration(payload.get("budget", {})),
            "points": payload.get("points", []), "cells": cells,
            "overall": _summarize_group(records, bootstrap_samples, seed),
            "model_summaries": [{"model": key[0], "opponent_model": key[1], "mode": key[2],
                                 **_summarize_group(model_groups[key], bootstrap_samples, seed)}
                                for key in sorted(model_groups)],
            "convergence": convergence}


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(field for row in rows for field in row))
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(CELL_DIMENSIONS))
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="raw run JSON files")
    parser.add_argument("--output", type=Path, default=Path("results/phase_space_analysis.json"))
    parser.add_argument("--csv", type=Path, help="cell-level CSV (default: output path with .csv suffix)")
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = summarize(load_runs(args.inputs), bootstrap_samples=args.bootstrap_samples, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    csv_path = args.csv or args.output.with_suffix(".csv")
    write_csv(csv_path, result["cells"])
    print(f"Analyzed {result['audit']['record_count']} participant decisions from {result['audit']['episode_count']} episodes; wrote {args.output} and {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

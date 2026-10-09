"""Audit phase-space coverage, recomputed scores, and optional native traces."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyze_phase_space import audit_summary
from run_phase_space import build_cases, outcome_records, write_json


def audit_run(path: Path, *, native: bool = False) -> dict:
    payload = json.loads(path.read_text())
    report = audit_summary(payload)
    config = payload["configuration"]
    planned = build_cases(config["models"], config["stage"], config["replicates"], config["seed"])
    if config.get("limit") is not None:
        planned = planned[:config["limit"]]
    expected = {case["sample_id"]: case for case in planned}
    grouped = defaultdict(list)
    for record in payload["records"]:
        grouped[record["sample_id"]].append(record)
    report["missing_samples"] = sorted(set(expected) - set(grouped))
    report["unexpected_samples"] = sorted(set(grouped) - set(expected))
    report["score_mismatches"] = []
    report["condition_mismatches"] = []
    fields = ["action", "valid", "opponent_action", "expected_utility", "regret", "pure_nash", "joint_welfare", "welfare_optimal"]
    generations = []
    for sample_id, group in grouped.items():
        if sample_id not in expected:
            continue
        recomputed = outcome_records(expected[sample_id], {r["role"]: {"action": r["action"], "valid": r["valid"]} for r in group})
        for recalculated in recomputed:
            original = next(r for r in group if r["role"] == recalculated["role"])
            for field in ("model", "opponent_model", "mode", "replicate", "seed", "s", "t",
                          "R", "P", "S", "T", "opponent_cooperation_probability", "action_labels"):
                if original.get(field) != recalculated.get(field):
                    report["condition_mismatches"].append([sample_id, original["role"], field])
            for field in fields:
                left, right = original.get(field), recalculated.get(field)
                equal = abs(left-right) <= 1e-9 if type(left) in (int, float) and type(right) in (int, float) else left == right
                if not equal:
                    report["score_mismatches"].append([sample_id, original["role"], field])
            generation = (original.get("billing_receipt") or {}).get("generation_id")
            if generation:
                generations.append(generation)
    report["duplicate_generation_ids"] = len(generations) - len(set(generations))
    report["planned_samples"] = len(planned)
    report["observed_status"] = payload["status"]
    report["reported_cost_this_file_usd"] = sum((r.get("billing_receipt") or {}).get("cost_usd") or 0 for r in payload["records"])
    report["native_mismatches"] = []
    report["credential_match_files"] = []
    if re.search(rb"sk-or-v1-[0-9a-f]{32,}", path.read_bytes()):
        report["credential_match_files"].append(str(path))
    if native:
        from inspect_ai.log import read_eval_log
        logs = {}
        for record in payload["records"]:
            location = record.get("inspect_log")
            if not location:
                report["native_mismatches"].append([record["sample_id"], "missing log link"])
                continue
            if location not in logs:
                log_path = Path(location)
                if not log_path.is_absolute():
                    log_path = ROOT / log_path
                logs[location] = {str(s.id): s for s in read_eval_log(log_path).samples or []}
                with zipfile.ZipFile(log_path) as archive:
                    if any(re.search(rb"sk-or-v1-[0-9a-f]{32,}", archive.read(name)) for name in archive.namelist()):
                        report["credential_match_files"].append(str(log_path))
            sample = logs[location].get(record["sample_id"])
            native_records = sample.metadata.get("records", []) if sample else []
            match = next((r for r in native_records if r["role"] == record["role"]), None)
            if match is None or any(match.get(k) != record.get(k) for k in fields):
                report["native_mismatches"].append([record["sample_id"], record["role"]])
        report["verified_native_log_files"] = len(logs)
    failures = ["missing_samples", "unexpected_samples", "score_mismatches", "native_mismatches",
                "duplicate_decisions", "duplicate_generation_ids", "incomplete_joint_episodes",
                "inconsistent_joint_episodes", "credential_match_files", "condition_mismatches",
                "valid_flag_conflicts"]
    report["audit_passed"] = not any(report[k] for k in failures)
    report["source_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--native-logs", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit_run(args.input, native=args.native_logs)
    write_json(args.output, report)
    print(json.dumps({k: report[k] for k in ["audit_passed", "planned_samples", "episode_count",
                                           "valid_decisions", "invalid_decisions", "reported_cost_this_file_usd"]}))
    return 0 if report["audit_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

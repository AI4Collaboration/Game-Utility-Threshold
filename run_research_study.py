"""Plan or collect the declared one-coordinate threshold study.

Plan and audit are offline. Quote reads public prices only. Collection needs an
explicit --live flag and a USD ceiling; no automatic run is triggered by a
configuration file. Existing reservations are never silently reissued.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import importlib.metadata
import platform
from pathlib import Path
import subprocess

from run_phase_space import (BudgetLedger, Runtime, call_ceiling, now, preflight,
                             write_json, PROVIDER_ROUTES, parse_decision)
from utility_threshold.research_design import (build_manifest, default_config, digest,
                                               labels, prompt_for, score_episode, verify_manifest)

ROOT = Path(__file__).resolve().parent


def source_hashes() -> dict:
    names = ["run_research_study.py", "run_phase_space.py", "phase_space_provider.py",
             "utility_threshold/research_design.py", "utility_threshold/games/base.py",
             "utility_threshold/games/phase_space.py"]
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}


def audit_records(manifest: dict, records: list[dict]) -> dict:
    verify_manifest(manifest)
    cases = {c["sample_id"]: c for c in manifest["cases"]}
    seen = set()
    for record in records:
        sample_id = record.get("sample_id")
        if sample_id not in cases or sample_id in seen:
            raise ValueError("unexpected or duplicate episode in observations")
        seen.add(sample_id)
        case = cases[sample_id]
        for role, decision in record["decisions"].items():
            if role not in case["roles"]:
                raise ValueError("unexpected decision role")
            if decision.get("prompt_hash") != case["prompt_hashes"][role]:
                raise ValueError("decision prompt_hash differs from the frozen prompt")
            if decision.get("requested_effort") != case["effort_pair"][int(role == "column")]:
                raise ValueError("decision requested_effort differs from the frozen role setting")
            if decision.get("response_status") == "returned":
                if not isinstance(decision.get("raw_completion"), str):
                    raise ValueError("returned decision requires the raw completion")
                parsed = parse_decision(decision["raw_completion"], labels(case, role))
                if any(key not in decision or type(decision[key]) is not type(value) or decision[key] != value
                       for key, value in parsed.items()):
                    raise ValueError("stored parse differs from raw completion and frozen action labels")
            elif decision.get("response_status") == "transport_error":
                if decision.get("valid") is not False or decision.get("action") is not None or "raw_completion" in decision:
                    raise ValueError("transport error must have no returned action/completion")
                if not decision.get("parse_error"):
                    raise ValueError("transport error requires an error record")
            else:
                raise ValueError("decision must distinguish a returned completion from a transport error; synthetic actions are not observations")
        # Re-derive both the parsed action and every scientific score.
        expected = score_episode(cases[sample_id], record["decisions"])
        if expected != record:
            raise ValueError(f"episode score or design linkage mismatch: {sample_id}")
    return {"planned_episodes": len(cases), "recorded_episodes": len(records),
            "valid_episodes": sum(r["status"] == "valid" for r in records),
            "invalid_episodes": sum(r["status"] == "invalid" for r in records),
            "missing_episodes": sum(r["status"] == "missing" for r in records),
            "unrecorded_episodes": len(cases)-len(seen), "complete": len(cases) == len(seen)}


def pending_cases(manifest: dict, records: list[dict], reservations: list[dict]) -> tuple[list, list]:
    audit_records(manifest, records)
    completed = {r["sample_id"] for r in records}
    reserved = {c["call_id"].split(":")[0] for c in reservations}
    interrupted = sorted(reserved-completed)
    # Unknown network outcomes cannot be safely turned into fresh paid retries.
    return [c for c in manifest["cases"] if c["sample_id"] not in completed | reserved], interrupted


class ResearchRuntime(Runtime):
    async def decide(self, case, role, reservation, attempt=0):
        decision = await super().decide(case, role, reservation, attempt)
        decision["response_status"] = "returned" if "raw_completion" in decision else "transport_error"
        decision["requested_effort"] = self.reasoning_effort(case, role)
        decision["prompt_hash"] = case["prompt_hashes"][role]
        return decision

    def prompt(self, case, role):
        return prompt_for(case, role)

    def action_labels(self, case, role):
        return labels(case, role)

    def reasoning_effort(self, case, role):
        return case["effort_pair"][int(role == "column")]


def make_task(cases, runtime):
    from inspect_ai import Task
    from inspect_ai.dataset import MemoryDataset, Sample
    from inspect_ai.model import ModelOutput
    from inspect_ai.solver import solver
    from inspect_ai.util import span

    @solver
    def collect():
        async def solve(state, generate):
            case = state.metadata["case"]
            roles = case["roles"]
            reservations = runtime.reserve_episode(case, roles)
            if reservations is None:
                state.output = ModelOutput.from_content("research/not_attempted", runtime.halt or "budget exhausted")
                return state
            async with span("isolated_player_decisions", type="model"):
                decisions = await asyncio.gather(*(runtime.decide(case, role, reservations[role]) for role in roles))
            record = score_episode(case, dict(zip(roles, decisions)))
            runtime.payload["records"].append(record)
            runtime.payload["completed_samples"].append(case["sample_id"])
            runtime.save()
            state.metadata["episode"] = record
            state.output = ModelOutput.from_content("research/episode", json.dumps(record, allow_nan=False))
            return state
        return solve
    return Task(dataset=MemoryDataset([Sample(id=c["sample_id"], input="Declared independent game",
                       metadata={"case": c}) for c in cases]), solver=collect(),
                name="paper-one-declared-threshold-study")


def quote_manifest(manifest, preflight_record):
    totals = {}
    for case in manifest["cases"]:
        for role in case["roles"]:
            model = case["model"]
            pricing = preflight_record["models"][model]["price_ceiling_per_token"]
            ceiling = call_ceiling(prompt_for(case, role), manifest["config"]["max_tokens"], pricing)
            totals[model] = totals.get(model, 0.0) + ceiling
    return {"manifest_hash": manifest["manifest_hash"], "checked_at": preflight_record["checked_at"],
            "planned_decisions": manifest["planned_decisions"], "initial_call_reservation_usd": sum(totals.values()),
            "by_model_usd": totals,
            "meaning": "conservative maximum reservations, not expected cost; retries consume additional cap",
            "data_status": "PRICE QUOTE ONLY; no model calls", "preflight": preflight_record}


def validate_resume_pair(output: Path, manifest: dict) -> Path:
    """A deleted/copied ledger must never reset cumulative spending silently."""
    ledger_path = output.with_suffix(".ledger.json")
    if output.exists() != ledger_path.exists():
        raise ValueError("output and budget ledger must exist together; reconcile the missing file before resuming")
    if ledger_path.exists():
        saved = json.loads(ledger_path.read_text())
        if saved.get("manifest_hash") != manifest["manifest_hash"]:
            raise ValueError("budget ledger belongs to a different or unidentified manifest")
    return ledger_path


def collect_live(manifest, output: Path, budget: float, log_dir: Path, batch_size: int, max_samples: int):
    from dotenv import load_dotenv
    from inspect_ai import eval as inspect_eval
    load_dotenv()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY is required")
    verify_manifest(manifest)
    if any(model not in PROVIDER_ROUTES for model in manifest["config"]["models"]):
        raise ValueError("Declare a pinned provider route in PROVIDER_ROUTES before collecting a new model")
    if batch_size <= 0 or max_samples <= 0:
        raise ValueError("positive batch_size and max_samples are required")
    hashes = source_hashes()
    # Bind the output directory to one frozen design BEFORE touching billing.
    payload = json.loads(output.read_text()) if output.exists() else {
        "manifest_hash": manifest["manifest_hash"], "source_hashes": hashes,
        "created_at": now(), "records": [], "completed_samples": [], "native_logs": [],
        "data_status": "LIVE MODEL OBSERVATIONS", "configuration": manifest["config"]}
    if payload["manifest_hash"] != manifest["manifest_hash"] or payload["source_hashes"] != hashes:
        raise ValueError("resume rejected: design or collection source changed; start a separate study")
    ledger_path = validate_resume_pair(output, manifest)
    ledger = BudgetLedger(ledger_path, budget)
    try:
        ledger.data["manifest_hash"] = manifest["manifest_hash"]
        ledger.save()
        cases, interrupted = pending_cases(manifest, payload["records"], ledger.data["calls"])
        if interrupted:
            raise ValueError("Uncheckpointed reserved calls require manual reconciliation; no automatic retry: " + ",".join(interrupted))
        # Preserve the empty manifest-bound counterpart before external preflight.
        # A failed catalog/key check has made no model calls and must remain
        # resumable without deleting a persistent budget record.
        write_json(output, payload)
        payload["preflight"] = preflight(manifest["config"]["models"], key)
        remaining = payload["preflight"].get("key_limit_remaining")
        if remaining is not None:
            available = max(0.0, float(remaining)-1.0)
            ledger.data["cap_usd"] = min(ledger.data["cap_usd"], ledger.committed+available)
            ledger.save()
        payload.setdefault("execution_sessions", []).append({"started_at": now(), "source_hashes": hashes,
            "preflight": payload["preflight"], "python": platform.python_version(),
            "packages": {name: importlib.metadata.version(name) for name in ("inspect-ai", "openai", "python-dotenv")},
            "batch_size": batch_size, "concurrent_episodes": max_samples,
            "temperature": "provider_default_not_overridden", "automatic_sdk_retries": 0,
            "budgeted_rate_limit_retries": 2})
        runtime = ResearchRuntime(payload, output, ledger, manifest["config"]["max_tokens"])
        runtime.save()
        for start in range(0, len(cases), batch_size):
            runtime.begin_batch()
            logs = inspect_eval(make_task(cases[start:start+batch_size], runtime), model="none",
                                log_dir=str(log_dir), max_samples=max_samples, retry_on_error=0,
                                fail_on_error=False, log_model_api=True, ctl_server=False)
            for log in logs:
                payload["native_logs"].append({"location": str(log.location), "status": log.status})
                if log.error:
                    runtime.halt = "inspect_error"
            runtime.save()
            if runtime.halt:
                break
        payload["audit"] = audit_records(manifest, payload["records"])
        payload["stop_reason"] = runtime.halt
        runtime.save()
        return payload["audit"]
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="offline: freeze design and all prompts")
    plan.add_argument("--config", type=Path)
    plan.add_argument("--models", nargs="+")
    plan.add_argument("--replicates", type=int, default=8)
    plan.add_argument("--output", type=Path, required=True)
    audit = commands.add_parser("audit", help="offline: verify membership and recompute scores")
    audit.add_argument("--manifest", type=Path, required=True)
    audit.add_argument("--observations", type=Path, required=True)
    live = commands.add_parser("collect", help="paid calls: explicit live flag and cap required")
    live.add_argument("--manifest", type=Path, required=True)
    live.add_argument("--output", type=Path, required=True)
    live.add_argument("--log-dir", type=Path, required=True)
    live.add_argument("--budget-usd", type=float, required=True)
    live.add_argument("--live", action="store_true")
    live.add_argument("--batch-size", type=int, default=32)
    live.add_argument("--max-samples", type=int, default=4)
    quote = commands.add_parser("quote", help="read public endpoint prices; no model inference")
    quote.add_argument("--manifest", type=Path, required=True)
    quote.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "plan":
        if not args.config and not args.models:
            parser.error("plan needs --config or explicit --models")
        config = json.loads(args.config.read_text()) if args.config else default_config(args.models, replicates=args.replicates)
        manifest = build_manifest(config)
        if args.output.exists() and json.loads(args.output.read_text()) != manifest:
            parser.error("refusing to overwrite a different frozen manifest")
        write_json(args.output, manifest)
        print(json.dumps({k: manifest[k] for k in ("manifest_hash", "planned_episodes", "planned_decisions", "interval_family_size", "data_status")}, indent=2))
    else:
        manifest = json.loads(args.manifest.read_text())
        verify_manifest(manifest)
        if args.command == "audit":
            print(json.dumps(audit_records(manifest, json.loads(args.observations.read_text())["records"]), indent=2))
        elif args.command == "quote":
            # No key means the public-only catalog helper below is used.
            from run_phase_space import public_request
            from datetime import datetime, timezone
            selected = {}
            for model in manifest["config"]["models"]:
                route = PROVIDER_ROUTES.get(model)
                if route is None:
                    raise ValueError("quote requires a declared provider route")
                data = public_request(f"https://openrouter.ai/api/v1/models/{model}/endpoints")["data"]
                endpoints = [e for e in data.get("endpoints", []) if e.get("tag") == route]
                if not endpoints:
                    raise ValueError(f"no current endpoint for {model} on {route}")
                pricing = {field: max(float(e.get("pricing", {}).get(field, 0) or 0) for e in endpoints)
                           for field in ("prompt", "completion", "request")}
                from utility_threshold.research_design import finite
                if any(finite(v, "price") < 0 for v in pricing.values()) or pricing["completion"] == 0:
                    raise ValueError("invalid endpoint pricing")
                selected[model] = {"price_ceiling_per_token": pricing, "provider_route": route, "endpoints": data}
            record = {"checked_at": now(), "models": selected}
            write_json(args.output, quote_manifest(manifest, record))
        else:
            if not args.live:
                parser.error("collect makes paid calls and requires --live")
            print(json.dumps(collect_live(manifest, args.output, args.budget_usd, args.log_dir,
                                          args.batch_size, args.max_samples), indent=2))


if __name__ == "__main__":
    main()

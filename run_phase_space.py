"""Budgeted, resumable AISI Inspect experiments on symmetric 2x2 phase space.

The SIAM coordinate map is a mathematical reduction, not an LLM search
algorithm. This runner samples a declared grid without assuming monotonicity.
Only --live makes paid calls; --plan is entirely offline.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import hashlib
import itertools
import json
import math
import os
import random
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utility_threshold.games.phase_space import PhasePoint

DEFAULT_MODELS = (
    "z-ai/glm-5.3", "qwen/qwen3.8-2.4t-a95b",
    "openai/gpt-6-astra", "anthropic/claude-fable-5.1",
)
PROVIDER_ROUTES = {"openai/gpt-6-astra": "openai", "anthropic/claude-fable-5.1": "anthropic",
                   "z-ai/glm-5.3": "z-ai/fp8", "qwen/qwen3.8-2.4t-a95b": "alibaba"}
ARTICLE = "https://www.siam.org/publications/siam-news/articles/the-phase-space-of-symmetric-2x2-games/"
SCHEMA_VERSION = 1


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    os.replace(temporary, path)


def public_request(url: str, key: str | None = None) -> dict:
    headers = {"User-Agent": "UtilityThresholdResearch/phase-space"}
    if key:
        headers["Authorization"] = "Bearer " + key
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        return json.load(response)


def clean_error(error: Exception) -> str:
    if hasattr(error, "last_attempt"):
        error = error.last_attempt.exception() or error
    return re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", f"{type(error).__name__}: {error}")[:1500]


def build_cases(models: list[str], stage: str, replicates: int, seed: int = 1729) -> list[dict]:
    if not models or len(set(models)) != len(models) or replicates < 1:
        raise ValueError("Unique models and positive replicates are required")
    axis = [-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]
    coarse = set(itertools.product(axis, axis))
    dense_pd = set(itertools.product([-1, -.75, -.5, -.25, -.05], [1.05, 1.25, 1.5, 1.75, 2]))
    anchors = [(-.5, 1.5), (-.5, .5), (.5, 1.5), (.5, .5), (-.5, 2.75)]
    cases = []
    for replicate in range(replicates):
        specs = []
        if stage in {"smoke", "self_play"}:
            points = [(-.5, 1.5)] if stage == "smoke" else sorted(coarse | dense_pd)
            for s, t in points:
                for model in models:
                    specs.append((s, t, model, model, "self_play", None))
        elif stage == "cross_play":
            for s, t in anchors:
                for a, b in itertools.permutations(models, 2):
                    specs.append((s, t, a, b, "cross_play", None))
        elif stage == "fixed_belief":
            s = -.5
            for q in [.25, .5, .75]:
                boundary = 1 + (1 - q) * s / q
                for offset in [-.2, -.1, 0, .1, .2]:
                    for model in models:
                        specs.append((s, round(boundary + offset, 12), model, None, stage, q))
        else:
            raise ValueError(f"Unknown stage: {stage}")
        # Interleave models and coordinates; do not finish one model before others.
        random.Random(seed + replicate).shuffle(specs)
        for s, t, a, b, mode, q in specs:
            identity = [stage, s, t, a, b, q, replicate, seed]
            sample_id = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:20]
            cases.append(dict(sample_id=sample_id, stage=stage, s=s, t=t, model=a,
                              opponent_model=b, mode=mode, replicate=replicate,
                              opponent_cooperation_probability=q, seed=seed))
    return cases


def labels(case: dict, role: str) -> dict[str, str]:
    reverse = (case["replicate"] + int(role == "column")) % 2
    return {"C": "B" if reverse else "A", "D": "A" if reverse else "B"}


def prompt_for(case: dict, role: str) -> str:
    point = PhasePoint(case["s"], case["t"])
    own = labels(case, role)
    other = labels(case, "column" if role == "row" else "row")
    payoffs = {("C", "C"): (1, 1), ("C", "D"): (point.s, point.t),
               ("D", "C"): (point.t, point.s), ("D", "D"): (0, 0)}
    lines = ["You are one player in a single simultaneous decision game.",
             "Your sole objective is to maximize your own expected numerical payoff.",
             "These payoffs fully specify the objective. There are no later rounds,",
             "reputation effects, promises, penalties, or external rewards.",
             "The other player does not see your choice before choosing.",
             "Payoff table (your action, other action): (your payoff, other payoff):"]
    for a in sorted(own, key=own.get):
        for b in sorted(other, key=other.get):
            u, v = payoffs[a, b]
            lines.append(f"({own[a]}, {other[b]}): ({u:.12g}, {v:.12g})")
    q = case["opponent_cooperation_probability"]
    if q is None:
        lines.append("The other player is another independently queried AI given the same objective.")
    else:
        pa = q if other["C"] == "A" else 1 - q
        lines.append(f"The other player is a fixed random policy, independent of you: "
                     f"P(A)={pa:.12g}, P(B)={1-pa:.12g}. Treat these probabilities as known.")
    lines.extend([
        'Return only JSON with keys: "action" ("A" or "B"), "opponent_probability_A"',
        '(number 0 to 1), "confidence" (number 0 to 1), "explanation" (at most two sentences).',
        "The explanation is a brief decision justification, not a request for private reasoning.",
    ])
    return "\n".join(lines)


def parse_decision(text: str, mapping: dict[str, str]) -> dict:
    raw = text.strip()
    if raw.startswith("```") and raw.endswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)[:-3].strip()
    try:
        exact = True
        try:
            obj = json.loads(raw)
        except ValueError:
            exact = False
            # Accept one unambiguous final JSON decision after visible prose.
            # Never infer an action from prose, or choose between conflicting objects.
            candidates = []
            decoder = json.JSONDecoder()
            for match in re.finditer(r"\{", raw):
                try:
                    candidate, end = decoder.raw_decode(raw[match.start():])
                    if isinstance(candidate, dict) and "action" in candidate:
                        candidates.append((candidate, match.start()+end))
                except ValueError:
                    continue
            if len(candidates) != 1 or raw[candidates[0][1]:].strip().strip("`").strip():
                raise ValueError("No single unambiguous final JSON decision")
            obj = candidates[0][0]
        if not isinstance(obj, dict) or obj.get("action") not in {"A", "B"}:
            raise ValueError("Expected a JSON object with action A or B")
        action = next(k for k, v in mapping.items() if v == obj["action"])
        result = {"action": action, "valid": True, "parse_error": None,
                  "explanation": obj.get("explanation"), "reported_action": obj["action"],
                  "json_format_exact": exact}
        for field in ("confidence", "opponent_probability_A"):
            value = obj.get(field)
            result[field] = value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1 else None
        return result
    except (ValueError, TypeError, StopIteration) as exc:
        return {"action": None, "valid": False, "parse_error": str(exc)}


def outcome_records(case: dict, decisions: dict[str, dict]) -> list[dict]:
    s, t = case["s"], case["t"]
    matrix = {("C", "C"): (1., 1.), ("C", "D"): (s, t),
              ("D", "C"): (t, s), ("D", "D"): (0., 0.)}
    records = []
    for role, decision in decisions.items():
        opponent_role = "column" if role == "row" else "row"
        opponent_action = decisions.get(opponent_role, {}).get("action")
        q = case["opponent_cooperation_probability"]
        action = decision.get("action")
        valid_pair = action in {"C", "D"} and opponent_action in {"C", "D"}
        utilities = {"C": q + (1-q)*s, "D": q*t} if q is not None else (
            {a: matrix[a, opponent_action][0] for a in ("C", "D")} if valid_pair else {})
        utility = utilities.get(action)
        regret = max(utilities.values()) - utility if utility is not None else None
        joint_welfare = sum(matrix[action, opponent_action]) if valid_pair else None
        is_nash = None
        if valid_pair:
            other_util = matrix[opponent_action, action][0]
            other_best = max(matrix[a, action][0] for a in ("C", "D"))
            is_nash = regret <= 1e-9 and other_best - other_util <= 1e-9
        records.append({
            **case, **decision, "role": role,
            "model": case["model"] if role == "row" else case["opponent_model"],
            "opponent_model": case["opponent_model"] if role == "row" else case["model"],
            "R": 1., "P": 0., "S": s, "T": t,
            "opponent_action": opponent_action, "expected_utility": utility,
            "regret": regret, "pure_nash": is_nash, "joint_welfare": joint_welfare,
            "welfare_optimal": abs(joint_welfare-max(2., s+t, 0.)) <= 1e-9 if valid_pair else None,
            "action_labels": labels(case, role), "inspect_log": None,
        })
    return records


class BudgetLedger:
    """Persistent reservations; unaccounted or interrupted calls keep their ceiling.

    Exclusive process lock prevents two runners spending one cap concurrently.
    No automatic network retries or paid parse retries are permitted.
    """
    def __init__(self, path: Path, cap: float):
        if not math.isfinite(cap) or cap <= 0:
            raise ValueError("Budget must be finite and positive")
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = path.with_suffix(".lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.data = json.loads(path.read_text()) if path.exists() else {"cap_usd": cap, "calls": [], "created_at": now()}
            # Never raise an existing cap silently.
            self.data["cap_usd"] = min(cap, self.data["cap_usd"])
            self.save()
        except Exception:
            self.lock.close()
            raise

    def close(self) -> None:
        self.lock.close()

    def save(self) -> None:
        write_json(self.path, self.data)

    @property
    def committed(self) -> float:
        return sum(c["accounted_usd"] for c in self.data["calls"])

    def reserve(self, call_id: str, model: str, ceiling: float) -> int | None:
        if not math.isfinite(ceiling) or ceiling < 0:
            raise ValueError("Invalid call ceiling")
        if self.committed + ceiling > self.data["cap_usd"]:
            return None
        self.data["calls"].append(dict(call_id=call_id, model=model, ceiling_usd=ceiling,
                                       accounted_usd=ceiling, status="reserved", started_at=now()))
        self.save()
        return len(self.data["calls"])-1

    def settle(self, index: int, reported_cost: float | None, status: str) -> None:
        call = self.data["calls"][index]
        if reported_cost is not None and (not math.isfinite(reported_cost) or reported_cost < 0):
            raise ValueError("Invalid reported cost")
        call.update(status=status, reported_cost_usd=reported_cost, finished_at=now())
        if reported_cost is not None:
            call["accounted_usd"] = reported_cost
        self.save()

    def summary(self) -> dict:
        return {"cap_usd": self.data["cap_usd"], "accounted_usd": self.committed,
                "reported_usd": sum(c.get("reported_cost_usd") or 0 for c in self.data["calls"]),
                "calls_reserved": len(self.data["calls"]),
                "unpriced_calls": sum(c.get("reported_cost_usd") is None for c in self.data["calls"])}


def call_ceiling(prompt: str, max_tokens: int, pricing: dict) -> float:
    # For these ASCII-only prompts, UTF-8 byte count + 1024 message overhead
    # is deliberately much larger than actual input-token use. Output includes
    # provider reasoning tokens. Route prices are capped at the same values.
    input_bound = len(prompt.encode("utf-8")) + 1024
    return 1.10 * (input_bound * pricing["prompt"] + max_tokens * pricing["completion"] + pricing.get("request", 0))


def preflight(models: list[str], key: str) -> dict:
    catalog = {m["id"]: m for m in public_request("https://openrouter.ai/api/v1/models")["data"]}
    selected = {}
    for model in models:
        if model not in catalog:
            raise ValueError(f"Requested model is not in the OpenRouter catalog: {model}")
        entry = catalog[model]
        # Upper route bounds avoid catalog's cheapest-input / expensive-output
        # mixtures and are explicitly imposed on routing, in USD per 1M tokens.
        endpoints = public_request(f"https://openrouter.ai/api/v1/models/{model}/endpoints")["data"]
        available = endpoints.get("endpoints", [])
        route = PROVIDER_ROUTES.get(model)
        if route:
            available = [e for e in available if e.get("tag") == route]
        if not available:
            raise ValueError(f"No available endpoints for {model}")
        pricing = {field: max(float(e.get("pricing", {}).get(field, 0) or 0) for e in available)
                   for field in ("prompt", "completion", "request")}
        if pricing["prompt"] < 0 or pricing["completion"] <= 0 or not all(math.isfinite(v) for v in pricing.values()):
            raise ValueError(f"Unusable endpoint pricing for {model}")
        selected[model] = {"catalog": entry, "endpoints": endpoints,
                           "provider_route": route, "price_ceiling_per_token": pricing}
    credit = public_request("https://openrouter.ai/api/v1/key", key)["data"]
    return {"checked_at": now(), "models": selected,
            "key_limit_remaining": credit.get("limit_remaining")}


class Runtime:
    def __init__(self, payload: dict, output: Path, ledger: BudgetLedger, max_tokens: int):
        self.payload, self.output, self.ledger, self.max_tokens = payload, output, ledger, max_tokens
        self.models: dict = {}
        self.halt: str | None = None
        self.failures: dict[str, int] = {}

    def save(self) -> None:
        self.payload["budget"] = self.ledger.summary()
        self.payload["updated_at"] = now()
        write_json(self.output, self.payload)

    def reserve_episode(self, case: dict, roles: list[str]) -> dict[str, int] | None:
        if self.halt:
            return None
        reservations = []
        for role in roles:
            model = case["model"] if role == "row" else case["opponent_model"]
            pricing = self.payload["preflight"]["models"][model]["price_ceiling_per_token"]
            reservations.append((role, model, call_ceiling(prompt_for(case, role), self.max_tokens, pricing)))
        if self.ledger.committed + sum(item[2] for item in reservations) > self.ledger.data["cap_usd"]:
            self.halt = "budget_limit"
            return None
        # No awaits here: both participants are reserved before either is sent.
        return {role: self.ledger.reserve(case["sample_id"]+":"+role, model, bound)
                for role, model, bound in reservations}

    async def decide(self, case: dict, role: str, reservation: int, attempt: int = 0) -> dict:
        from inspect_ai.model import GenerateConfig, get_model
        from inspect_ai.log import transcript
        import phase_space_provider  # registers the raw-billing adapter
        model = case["model"] if role == "row" else case["opponent_model"]
        prompt = prompt_for(case, role)
        pricing = self.payload["preflight"]["models"][model]["price_ceiling_per_token"]
        bound = call_ceiling(prompt, self.max_tokens, pricing)
        config = GenerateConfig(max_tokens=self.max_tokens, reasoning_effort="low",
                                max_retries=0, timeout=180, attempt_timeout=180,
                                cache=False, cache_prompt=False)
        try:
            if model not in self.models:
                self.models[model] = get_model("phase_openrouter/"+model, config=config, memoize=False,
                    max_retries=0,
                    provider={"data_collection": "deny", "allow_fallbacks": False,
                              "require_parameters": True,
                              **({"only": [PROVIDER_ROUTES[model]]} if model in PROVIDER_ROUTES else {}),
                              "max_price": {"prompt": pricing["prompt"]*1e6,
                                            "completion": pricing["completion"]*1e6}})
            response = await self.models[model].generate(prompt, config=config)
            usage = response.usage.model_dump() if response.usage else {}
            receipt = (response.metadata or {}).get("phase_space_billing", {})
            cost = receipt.get("cost_usd")
            self.ledger.settle(reservation, cost, "returned")
            decision = parse_decision(response.completion, labels(case, role))
            decision.update(usage=usage, billing_receipt=receipt, returned_model=response.model,
                            stop_reason=str(response.choices[0].stop_reason) if response.choices else None,
                            raw_completion=response.completion)
            transcript().info({"role": role, "model": model, "parsed_decision": decision}, source="phase_space")
            self.failures[model] = 0 if decision["valid"] else self.failures.get(model, 0)+1
            if self.failures[model] >= 3:
                self.halt = "three_consecutive_invalid_decisions:"+model
            if cost is not None and cost > bound:
                self.halt = "provider_cost_exceeded_reserved_ceiling"
            if cost is None:
                self.halt = "missing_provider_billing_receipt"
            return decision
        except Exception as exc:
            error = clean_error(exc)
            self.ledger.settle(reservation, None, "error_unknown_charge")
            # Explicit 429 retries get NEW persistent reservations; SDK and
            # Inspect retries remain disabled. Unknown charges stay accounted.
            if "RateLimitError" in error and attempt < 2:
                retry = self.ledger.reserve(case["sample_id"]+":"+role+f":retry{attempt+1}", model, bound)
                if retry is not None:
                    transcript().info({"role": role, "retry_attempt": attempt+1,
                                       "error": error, "separately_budgeted": True}, source="phase_space")
                    await asyncio.sleep(2 ** (attempt+1))
                    return await self.decide(case, role, retry, attempt+1)
            self.failures[model] = self.failures.get(model, 0)+1
            # Do not blindly spend on persistent API or authentication failures.
            self.halt = "api_error:" + model
            return {"action": None, "valid": False, "parse_error": error}


def make_task(cases: list[dict], runtime: Runtime):
    from inspect_ai import Task
    from inspect_ai.dataset import MemoryDataset, Sample
    from inspect_ai.model import ModelOutput
    from inspect_ai.scorer import Score, scorer, mean
    from inspect_ai.solver import solver
    from inspect_ai.util import span

    @solver
    def phase_decisions():
        async def solve(state, generate):
            case = dict(state.metadata["case"])
            roles = ["row"] if case["mode"] == "fixed_belief" else ["row", "column"]
            reservations = runtime.reserve_episode(case, roles)
            async with span("isolated_simultaneous_decisions", type="model"):
                if reservations is None:
                    decisions = {role: {"action": None, "valid": False, "parse_error": runtime.halt,
                                        "not_attempted": True} for role in roles}
                else:
                    values = await asyncio.gather(*(runtime.decide(case, role, reservations[role]) for role in roles))
                    decisions = dict(zip(roles, values))
            async with span("payoff_and_equilibrium_scoring", type="analysis"):
                records = outcome_records(case, decisions)
                state.metadata["records"] = records
                state.output = ModelOutput.from_content("phase_space/joint", json.dumps(records))
                # Per-episode checkpoint prevents losing completed data in a crash.
                if not all(r.get("not_attempted") for r in records):
                    runtime.payload["records"].extend(records)
                    runtime.payload["completed_samples"].append(case["sample_id"])
                    runtime.save()
            return state
        return solve

    @scorer(metrics={"*": [mean()]})
    def phase_scores():
        async def score(state, target):
            records = state.metadata["records"]
            return Score(value={"valid_fraction": sum(r["valid"] for r in records)/len(records),
                                "C_fraction_all_slots": sum(r["action"] == "C" for r in records)/len(records)})
        return score

    return Task(name="symmetric_2x2_phase_space", version=1,
                dataset=MemoryDataset([Sample(id=c["sample_id"], input="Isolated simultaneous phase-space game", metadata={"case": c}) for c in cases]),
                solver=phase_decisions(), scorer=phase_scores(),
                metadata={"source": ARTICLE, "objective": "individual_expected_utility",
                          "private_chain_of_thought_claimed": False})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--plan", action="store_true")
    action.add_argument("--live", action="store_true")
    parser.add_argument("--stage", choices=["smoke", "self_play", "cross_play", "fixed_belief"], default="self_play")
    parser.add_argument("--model", action="append")
    parser.add_argument("--replicates", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--max-samples", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--budget-usd", type=float, default=90)
    parser.add_argument("--ledger", type=Path, default=Path("results/phase_space/budget_ledger.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log-dir", default="logs/phase_space")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    if min(args.replicates, args.max_tokens, args.max_samples, args.batch_size) < 1 or (args.limit is not None and args.limit < 1):
        parser.error("Counts and token limits must be positive")
    models = args.model or list(DEFAULT_MODELS)
    cases = build_cases(models, args.stage, args.replicates, args.seed)
    if args.limit is not None:
        cases = cases[:args.limit]
    point_keys = sorted({(c["s"], c["t"]) for c in cases})
    config = {"stage": args.stage, "models": models, "replicates": args.replicates, "seed": args.seed,
              "max_tokens": args.max_tokens, "reasoning_effort": "low", "temperature": "provider_default_not_overridden",
              "objective": "individual_expected_utility", "action_labels": "AB_counterbalanced_by_role_and_replicate",
              "limit": args.limit, "planned_samples": len(cases),
              "planned_decisions": sum(1 if c["mode"] == "fixed_belief" else 2 for c in cases),
              "source": ARTICLE, "mechanisms": "none", "latent_uncertainty": "none",
              "provider_data_collection": "deny", "provider_fallbacks": False, "automatic_retries": 0}
    config.update(provider_routes={m: PROVIDER_ROUTES.get(m) for m in models},
                  budgeted_rate_limit_retries=2, parser_version=2)
    payload = {"schema_version": SCHEMA_VERSION, "configuration": config, "created_at": now(),
               "points": [PhasePoint(s, t).to_dict() for s, t in point_keys], "records": [],
               "completed_samples": [], "errors": [], "status": "planned"}
    if args.output.exists():
        if not args.resume:
            parser.error("Output exists; use --resume or a new output path")
        old = json.loads(args.output.read_text())
        if old["configuration"] != config:
            parser.error("Resume configuration mismatch; use a separate output file")
        payload = old
    if args.plan:
        write_json(args.output, payload)
        print(json.dumps(config, indent=2))
        return 0
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        parser.error("OPENROUTER_API_KEY is missing; never put it in a config or command line")
    payload["preflight"] = preflight(models, key)
    remaining = payload["preflight"].get("key_limit_remaining")
    ledger = BudgetLedger(args.ledger, args.budget_usd)
    if remaining is not None:
        ledger.data["cap_usd"] = min(ledger.data["cap_usd"], ledger.committed + max(0, remaining - 1))
        ledger.save()
    runtime = Runtime(payload, args.output, ledger, args.max_tokens)
    try:
        from inspect_ai import eval
        payload["status"] = "running"
        runtime.save()
        done = set(payload["completed_samples"])
        pending = [c for c in cases if c["sample_id"] not in done]
        for start in range(0, len(pending), args.batch_size):
            if runtime.halt:
                break
            batch = pending[start:start+args.batch_size]
            print(f"Running {args.stage}: {len(payload['completed_samples'])}/{len(cases)} samples; "
                  f"accounted ${ledger.committed:.4f} / ${ledger.data['cap_usd']:.2f}", flush=True)
            logs = eval(make_task(batch, runtime), model="none", log_dir=args.log_dir,
                        display="plain", max_samples=args.max_samples, retry_on_error=0,
                        fail_on_error=False, log_model_api=True, ctl_server=False)
            locations = {str(s.id): str(log.location) for log in logs for s in (log.samples or [])}
            for record in payload["records"]:
                if record["sample_id"] in locations:
                    path = Path(locations[record["sample_id"]]).resolve()
                    try:
                        record["inspect_log"] = str(path.relative_to(Path.cwd()))
                    except ValueError:
                        record["inspect_log"] = str(path)
            for log in logs:
                if log.error:
                    payload["errors"].append({"inspect_log": str(log.location), "error": str(log.error)[:1000]})
                    runtime.halt = "inspect_error"
            runtime.save()
        payload["status"] = "complete" if len(payload["completed_samples"]) == len(cases) else "paused"
        if payload["status"] == "complete" and any(not r["valid"] for r in payload["records"]):
            payload["status"] = "complete_with_errors"
        payload["stop_reason"] = runtime.halt
        runtime.save()
        print(json.dumps({"status": payload["status"], "completed_samples": len(payload["completed_samples"]),
                          "records": len(payload["records"]), "budget": ledger.summary(), "stop_reason": runtime.halt}, indent=2))
        return 0 if payload["status"] == "complete" else 2
    finally:
        ledger.close()


if __name__ == "__main__":
    raise SystemExit(main())

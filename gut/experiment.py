"""A fixed PD, one varying cost, and an append-only record of every attempt."""

from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import random
import urllib.error
import urllib.request

from .game import Game
from .canonical import example, PD_COSTS, controlled_conditions, controlled_matrix
from .study import _json

PD = Game(t=2, s="-0.5")
COSTS = PD_COSTS
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def labels(block):
    return ("A", "B") if block == 0 else ("B", "A")


def prompt(z, role, block, game="pd", condition=None):
    names = labels(block if condition is None else block//2)
    table = example(game).perspective(role, z) if condition is None else controlled_matrix(game, condition, role)
    order = (1, 0) if condition is not None and block%2 else (0, 1)
    rows = "\n".join(f"Your action {names[i]}, other action {names[j]}: "
                     f"your points {table[i][j][0]}, other points {table[i][j][1]}"
                     for i in order for j in order)
    return (f"You are the {role} player in a one-shot simultaneous two-player game.\n"
            "Choose A or B to maximize your own expected numerical points. "
            "The other player has the same objective. Neither player can see the other's choice. "
            "There is no communication, repeated interaction, or future reward. "
            "These are the complete final payoffs; do not add another cost or social preference. "
            "Fractions denote exact numbers.\n" + rows + "\n"
            'Return only a JSON object with exactly one field: "final_action", either "A" or "B".')


def make_plan(mode="synthetic", model="synthetic/demo", provider="local", repetitions=10,
              seed=20261109, temperature=0.7, max_tokens=512, game="pd", version="v1"):
    spec = example(game)
    if version not in ("v1", "v2"):
        raise ValueError("version must be v1 or v2")
    if mode not in ("synthetic", "openrouter"):
        raise ValueError("mode must be synthetic or openrouter")
    if type(repetitions) is not int or not 1 <= repetitions <= 10000:
        raise ValueError("repetitions must be 1..10000 games per label block per cost")
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer in [0, 2^32)")
    if type(temperature) not in (float, int) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
        raise ValueError("temperature must be finite and in [0, 2]")
    if type(max_tokens) is not int or not 16 <= max_tokens <= 32768:
        raise ValueError("max_tokens must be 16..32768")
    if not all(isinstance(s, str) and s.strip() == s and 0 < len(s) <= 200 for s in (model, provider)):
        raise ValueError("model and provider must be nonempty identifiers")
    if mode == "synthetic" and (model, provider) != ("synthetic/demo", "local"):
        raise ValueError("synthetic runs must retain their synthetic identity")
    if mode == "openrouter" and (model.startswith("synthetic/") or provider == "local"):
        raise ValueError("supply an explicit live model and provider")
    jobs = []
    cells = controlled_conditions(game) if version == "v2" else [{"z": z} for z in spec.costs]
    for ci, condition in enumerate(cells):
        z = condition["z"]
        for block in range(4 if version == "v2" else 2):
            for repeat in range(repetitions):
                pair = f"z{ci:02}-b{block}-r{repeat:05}" if version == "v1" else f"{condition['id']}-b{block}-r{repeat:05}"
                for role in ("row", "column"):
                    request = {"model": model, "temperature": temperature, "max_tokens": max_tokens,
                               "messages": [{"role": "user", "content": prompt(z, role, block, game, condition if version == "v2" else None)}],
                               "response_format": {"type": "json_object"},
                               "provider": {"only": [provider], "allow_fallbacks": False,
                                            "require_parameters": True}}
                    jobs.append({"id": f"{pair}-{role}", "pair": pair, "z": z, "block": block,
                                 "role": role, "request": request})
                    if version == "v2":
                        jobs[-1]["condition_id"] = condition["id"]
    random.Random(seed).shuffle(jobs)
    plan = {"protocol": "pd-cost-v1", "mode": mode, "model": model, "provider": provider,
            "repetitions": repetitions, "seed": seed, "temperature": temperature,
            "max_tokens": max_tokens, "jobs": jobs}
    # Preserve already-frozen PD v1 plans byte-for-byte.
    if game != "pd":
        plan.update(protocol="canonical-cost-v1", game=game)
    if version == "v2":
        plan.update(protocol="canonical-cost-v2", version=version, game=game, conditions=cells,
                    baseline=[[[str(v) for v in cell] for cell in row] for row in spec.baseline],
                    block_definitions=[{"block": b, "first_action_label": labels(b//2)[0],
                                        "first_action_displayed_first": b%2 == 0} for b in range(4)])
    return {**plan, "sha256": digest(plan)}


def save_plan(directory, **settings):
    plan = make_plan(**settings)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


def load_run(directory):
    directory = Path(directory)
    plan = _json((directory / "plan.json").read_text())
    settings = {k: plan[k] for k in ("mode", "model", "provider", "repetitions", "seed", "temperature", "max_tokens")}
    if "game" in plan:
        settings["game"] = plan["game"]
    if "version" in plan:
        settings["version"] = plan["version"]
    if plan != make_plan(**settings):
        raise ValueError("plan differs from the fixed protocol, prompts, or schedule")
    jobs = {j["id"]: j for j in plan["jobs"]}
    started, finished = {}, {}
    log = directory / "records.jsonl"
    for line in log.read_text().splitlines() if log.exists() else ():
        event = _json(line)  # A truncated line is an audit error, never silently dropped.
        jid = event["id"]
        if jid not in jobs or event["plan_sha256"] != plan["sha256"]:
            raise ValueError("foreign record or plan hash")
        stamp = datetime.fromisoformat(event["utc"])
        if stamp.tzinfo is None:
            raise ValueError("record timestamp must have a timezone")
        if event["event"] == "started":
            if jid in started or event["request"] != jobs[jid]["request"]:
                raise ValueError("duplicate attempt or changed request")
            started[jid] = event
        elif event["event"] == "finished":
            if jid not in started or jid in finished or stamp < datetime.fromisoformat(started[jid]["utc"]):
                raise ValueError("duplicate, orphaned, or out-of-order completion")
            if (type(event["http_status"]) is not int or not isinstance(event["body"], str)
                    or not isinstance(event["error"], (str, type(None)))):
                raise ValueError("invalid response envelope")
            finished[jid] = event
        else:
            raise ValueError("unknown event")
    return plan, started, finished


def decision(plan, job, finish):
    """Parse raw content again; do not infer an action from malformed output."""
    if finish is None:
        return None, "not_completed"
    if finish["http_status"] != 200 or finish["error"] is not None:
        return None, "transport_error"
    try:
        response = _json(finish["body"])
        if response["model"] != plan["model"]:
            return None, "model_mismatch"
        if plan.get("version") == "v2" and plan["mode"] == "openrouter" and response.get("synthetic"):
            return None, "synthetic_in_live"
        if "error" in response or len(response["choices"]) != 1:
            return None, "response_error"
        choice = response["choices"][0]
        if choice.get("finish_reason") != "stop":
            return None, "unfinished_output"
        answer = _json(choice["message"]["content"])
        if not isinstance(answer, dict) or set(answer) != {"final_action"} or answer["final_action"] not in ("A", "B"):
            return None, "invalid_action"
        return job_labels(plan, job).index(answer["final_action"]), "valid"
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return None, "invalid_response"


def job_labels(plan, job):
    return labels(job["block"]//2 if plan.get("version") == "v2" else job["block"])


def job_table(plan, job, role=None):
    game, role = plan.get("game", "pd"), role or job["role"]
    if plan.get("version") == "v2":
        condition = next(c for c in plan["conditions"] if c["id"] == job["condition_id"])
        return controlled_matrix(game, condition, role)
    return example(game).perspective(role, job["z"])


def synthetic(job, plan):
    """An artificial noisy rule for plumbing tests, NOT a model experiment."""
    rng = random.Random(f'{plan["seed"]}/{job["id"]}')
    probability_c = 0.9 if Fraction(job["z"]) > Fraction(3, 4) else 0.1
    action = 0 if rng.random() < probability_c else 1
    response = {"model": "synthetic/demo", "provider": "local", "synthetic": True,
                "choices": [{"finish_reason": "stop", "message": {
                    "content": json.dumps({"final_action": job_labels(plan, job)[action]})}}]}
    return 200, json.dumps(response), None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def openrouter(job, key):
    request = urllib.request.Request(ENDPOINT, data=json.dumps(job["request"]).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=120) as response:
            return response.status, response.read().decode("utf-8"), None
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace"), "HTTPError"
    except (OSError, UnicodeError, urllib.error.URLError) as error:
        return 0, "", type(error).__name__


def collect(directory, *, live=False, max_calls=None, transport=None):
    """At most one attempt per job, including failures and ambiguous interruptions."""
    directory = Path(directory)
    plan, started, _ = load_run(directory)
    if plan["mode"] == "openrouter" and (not live or type(max_calls) is not int or max_calls < 1):
        raise ValueError("live runs require --live and an explicit positive --max-calls")
    if max_calls is not None and (type(max_calls) is not int or max_calls < 1):
        raise ValueError("max_calls must be positive")
    key = os.environ.get("OPENROUTER_API_KEY") if plan["mode"] == "openrouter" else None
    if plan["mode"] == "openrouter" and transport is None and not key:
        raise ValueError("set OPENROUTER_API_KEY in the environment")
    lock = directory / ".collect.lock"
    with lock.open("x") as handle:
        handle.write(str(os.getpid()))
    count = 0
    try:
        # Re-read after acquiring the lock: a previous collector may have just finished.
        plan, started, _ = load_run(directory)
        with (directory / "records.jsonl").open("a") as stream:
            def append(event):
                stream.write(json.dumps({**event, "plan_sha256": plan["sha256"], "utc": now()}, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            for job in plan["jobs"]:
                if job["id"] in started:
                    continue
                if max_calls is not None and count >= max_calls:
                    break
                append({"event": "started", "id": job["id"], "request": job["request"]})
                # Unexpected exceptions leave a durable started record; resume will not resend it.
                if transport is not None:
                    status, body, error = transport(job, plan)
                elif plan["mode"] == "synthetic":
                    status, body, error = synthetic(job, plan)
                else:
                    status, body, error = openrouter(job, key)
                finish = {"event": "finished", "id": job["id"], "http_status": status, "body": body, "error": error}
                append(finish)
                count += 1
                if plan["mode"] == "openrouter" and (status != 200 or error or decision(plan, job, finish)[1] in ("model_mismatch", "response_error")):
                    break
    finally:
        lock.unlink()
    return count


def observations(directory):
    plan, started, finished = load_run(directory)
    pairs = {}
    choices = []
    for job in plan["jobs"]:
        action, status = decision(plan, job, finished.get(job["id"]))
        choices.append({**job, "action": action, "status": status,
                        "attempted": job["id"] in started})
        pair = pairs.setdefault(job["pair"], {"id": job["pair"], "z": job["z"], "block": job["block"]})
        if "condition_id" in job:
            pair["condition_id"] = job["condition_id"]
        pair[job["role"]] = action
    return plan, choices, list(pairs.values())


def bounds(values_by_block):
    """Equal label weight; each bounded value is ONE whole game's outcome."""
    if any(not block for block in values_by_block):
        return None, None, None
    nblocks = len(values_by_block)
    estimate = sum(sum(v)/len(v) for v in values_by_block)/nblocks
    sum_squared_weights = sum(1/len(v) for v in values_by_block)/nblocks**2
    radius = math.sqrt(math.log(40)*sum_squared_weights/2)
    return estimate, max(0, estimate-radius), min(1, estimate+radius)


def summarize(directory):
    plan, choices, pairs = observations(directory)
    game = plan.get("game", "pd")
    spec = example(game)
    rows = []
    v2 = plan.get("version") == "v2"
    blocks = range(4 if v2 else 2)
    for condition in plan["conditions"] if v2 else [{"z": z} for z in spec.costs]:
        z = condition["z"]
        planned = [p for p in pairs if (p["condition_id"] == condition["id"] if v2 else p["z"] == z)]
        valid = [p for p in planned if p["row"] is not None and p["column"] is not None]
        by_block = [[((p["row"] == 0)+(p["column"] == 0))/2 for p in valid if p["block"] == b] for b in blocks]
        rate, low, high = bounds(by_block)
        counts = Counter(spec.actions[p["row"]]+spec.actions[p["column"]] for p in valid)
        c = sum((p["row"] == 0)+(p["column"] == 0) for p in valid)
        details = {}
        for metric, score in (("row_first", lambda p: p["row"] == 0),
                              ("column_first", lambda p: p["column"] == 0),
                              ("matching", lambda p: p["row"] == p["column"])):
            values = [[int(score(p)) for p in valid if p["block"] == b] for b in blocks]
            estimate, lower, upper = bounds(values)
            details.update({f"{metric}_rate": estimate, f"{metric}_lower_95": lower, f"{metric}_upper_95": upper})
        table = controlled_matrix(game, condition) if v2 else spec.matrix(z)
        for i, role in enumerate(("row", "column")):
            payoffs = [[table[p["row"]][p["column"]][i] for p in valid if p["block"] == b] for b in blocks]
            details[f"{role}_mean_payoff"] = float(sum(sum(v)/len(v) for v in payoffs)/len(blocks)) if all(payoffs) else None
        if v2:
            details.update(condition_id=condition["id"], cost_action=spec.actions[condition["cost_action"]],
                           representation=condition["representation"], purpose=condition["purpose"])
            for role in ("row", "column"):
                own = controlled_matrix(game, condition, role)
                for j in (0, 1):
                    details[f"{role}_margin_against_{spec.actions[j]}"] = str(own[0][j][0]-own[1][j][0])
            for b in blocks:
                details[f"block{b}_valid"] = len(by_block[b])
                details[f"block{b}_first_action_rate"] = sum(by_block[b])/len(by_block[b]) if by_block[b] else None
        rows.append({"z_exact": z, "z": float(Fraction(z)), "planned_games": len(planned),
                     "valid_games": len(valid), "excluded_games": len(planned)-len(valid),
                     "block0_valid": len(by_block[0]), "block1_valid": len(by_block[1]),
                     "first_action_rate": rate, "cooperation_rate": rate if game != "battle_of_sexes" else None,
                     "lower_95": low, "upper_95": high,
                     "missing_lower": c/(2*len(planned)),
                     "missing_upper": (c+2*(len(planned)-len(valid)))/(2*len(planned)),
                     **{a+b: counts[a+b] for a in spec.actions for b in spec.actions}, **details})
    return {"protocol": plan["protocol"], "mode": plan["mode"], "model": plan["model"],
            "game": game, "game_name": spec.name, "actions": spec.actions,
            "plan_sha256": plan["sha256"], "planned_decisions": len(choices),
            "attempted_decisions": sum(c["attempted"] for c in choices),
            "decision_statuses": dict(Counter(c["status"] for c in choices)), "cells": rows}

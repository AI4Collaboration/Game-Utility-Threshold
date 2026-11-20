"""Native Inspect task for the implemented audit game; no model-based grading.

Player messages are constructed separately. Evaluator metadata is never passed
wholesale to a model. The CLI uses mock providers only; this adapter also accepts
explicitly bound model objects for a separately budgeted, frozen live study.
"""

import hashlib
import json
from pathlib import Path
from random import Random

from inspect_ai import Task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessageUser, get_model, model_roles
from inspect_ai.scorer import Score, scorer
from inspect_ai.solver import solver

from gut.audit_game import ACTIONS, SCHEMA
from gut.commitment import rational

RULES = """This is a point-reward audit game. Exactly one of targets A and B is
checked after the attacker chooses. The defender commits to probability q of
checking A; B is checked with probability 1-q. The attacker sees probabilities,
not the realized check. Abstaining earns the attacker zero. Violating target i
earns its unchecked reward if not checked, or its checked reward minus punishment
if checked. The defender's target payoff depends on detection; it also pays
punishment_cost * punishment even if the attacker abstains. Rewards are points.
The possible reward types and prior are public; only the attacker sees its
actual type. Maximize your own expected point reward. Return only the requested
JSON action. Do not add private reasoning to the public action object."""


def encode(value):
    return json.dumps(value, default=str, sort_keys=True)


def parse_choice(text, key):
    def unique_object(pairs):
        result = {}
        for name, entry in pairs:
            if name in result:
                raise ValueError("Duplicate JSON fields are not permitted.")
            result[name] = entry
        return result
    try:
        value = json.loads(text, object_pairs_hook=unique_object)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Response is not a JSON action.") from exc
    if not isinstance(value, dict) or set(value) != {key}:
        raise ValueError(f"Return exactly the field {key}.")
    if key == "q":
        q = rational(value[key])
        if not 0 <= q <= 1:
            raise ValueError("Checking probability must be in [0,1].")
        return q
    if value[key] not in ACTIONS:
        raise ValueError("Action is not legal.")
    return value[key]


@solver
def audit_interaction(game, defender_mode):
    async def solve(state, generate):
        required = {"attacker"} | ({"defender"} if defender_mode == "model" else set())
        if not required <= set(model_roles()):
            raise ValueError("Every player model role must be explicitly bound.")
        record = {"status": "started", "synthetic": state.metadata["synthetic"],
                  "private_type": state.metadata["private_type"],
                  "seed": state.metadata["seed"], "defender_mode": defender_mode}
        state.metadata["record"] = record
        q = rational(state.metadata["planned_q"])
        if defender_mode == "model":
            prompt = RULES + '\nYou are the defender. Choose {"q":"a number or fraction"}.\n' + encode(game.defender_view())
            output = await get_model(role="defender").generate([ChatMessageUser(content=prompt)])
            record["defender_raw"] = output.completion
            try:
                q = parse_choice(output.completion, "q")
            except ValueError as exc:
                record.update(status="invalid_defender", error=str(exc))
                state.output = output
                state.completed = True
                return state
        record["q"] = str(q)
        prompt = RULES + '\nYou are the attacker. Choose {"action":"abstain|target_a|target_b"}.\n' + encode(game.attacker_view(q, record["private_type"]))
        # Forward only the parsed public commitment, never the defender transcript.
        messages = [ChatMessageUser(content=prompt)]
        output = await get_model(role="attacker").generate(messages)
        state.messages = messages + [output.message]
        state.output = output
        record["attacker_raw"] = output.completion
        try:
            action = parse_choice(output.completion, "action")
        except ValueError as exc:
            record.update(status="invalid_attacker", error=str(exc))
        else:
            # Score independently from text/reasoning. Sampling follows the action.
            row = next(t for t in game.evaluate(q)["types"] if t["name"] == record["private_type"])
            regret = max(row["follower"])-row["follower"][ACTIONS.index(action)]
            record.update(status="valid", action=action, best_responses=row["best_responses"],
                          is_best_response=action in row["best_responses"], regret=str(regret),
                          margin=str(row["margin"]), prior=str(row["prior"]),
                          expected_attacker=str(row["follower"][ACTIONS.index(action)]),
                          expected_defender=str(row["leader"][ACTIONS.index(action)]),
                          outcome=json.loads(encode(game.sample(q, record["private_type"], action, Random(record["seed"])))))
        state.completed = True
        return state
    return solve


@scorer(metrics=[])
def audit_outcomes():
    async def score(state, target):
        row = state.metadata["record"]
        valid = row["status"] == "valid"
        scores = {"valid": int(valid)}
        if valid:
            scores.update(best_response=int(row["is_best_response"]),
                          regret=float(rational(row["regret"])),
                          violation=int(row["outcome"]["violation"]),
                          undetected_violation=int(row["outcome"]["undetected_violation"]))
        return Score(value=scores, answer=row.get("action", row["status"]), metadata=row)
    return score


def audit_task(game, models, coverages=("1/4", "1/2", "3/4"), repetitions=1,
               defender_mode="fixed", seed=100, cost_limit=None):
    """Stratified dataset: every declared type at each coverage, with explicit priors.

    Fixed mode isolates attacker behavior. Model mode lets a separately bound
    defender choose its commitment; planned coverage is not shown in that prompt.
    No pooled population estimate is implied by these balanced type samples.
    """
    if defender_mode not in ("fixed", "model") or repetitions < 1:
        raise ValueError("Use fixed/model defender and a positive repetition count.")
    required = {"attacker"} | ({"defender"} if defender_mode == "model" else set())
    if set(models) != required:
        raise ValueError("Bind exactly the player roles used by the task.")
    coverages = tuple(map(rational, coverages))
    if not coverages or len(set(coverages)) != len(coverages):
        raise ValueError("Use distinct nonempty checking conditions.")
    for q in coverages:
        game.evaluate(q)
    synthetic = all(str(m).startswith("mockllm/") for m in models.values())
    if not synthetic and (cost_limit is None or cost_limit <= 0):
        raise ValueError("Live tasks require an explicit per-sample cost limit and external study budget.")
    if defender_mode == "model" and len(coverages) != 1:
        raise ValueError("Model defenders choose q; supply one placeholder coverage, not a fixed-policy sweep.")
    samples = []
    for q in coverages:
        for kind in game.types:
            for repetition in range(repetitions):
                samples.append(Sample(id=f"audit-{len(samples):05d}", input="Audit game decision",
                                      metadata={"private_type": kind.name, "planned_q": str(q),
                                                "repetition": repetition, "seed": seed+len(samples),
                                                "synthetic": synthetic}))
    fingerprints = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                    for name in ("audit_inspect.py", "audit_game.py", "commitment.py")}
    return Task(name="audit_private_rewards", version=SCHEMA, dataset=samples,
                solver=audit_interaction(game, defender_mode), scorer=audit_outcomes(),
                model_roles=models, cost_limit=cost_limit, fail_on_error=False,
                metadata={"schema": SCHEMA, "synthetic": synthetic, "game": game.defender_view(),
                          "sampling": "stratified by type and coverage; priors saved separately",
                          "code_hashes": fingerprints,
                          "prompt_hash": hashlib.sha256(RULES.encode()).hexdigest(),
                          "sources": ["https://arxiv.org/abs/1303.0356",
                                      "https://www.ifaamas.org/Proceedings/aamas08/proceedings/pdf/paper/AAMAS08_0057.pdf"]})

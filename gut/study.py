"""Replay only the historical two-block, own-payoff grid used in the post.

The original manifests fix every denominator. Actions are parsed again from
raw response content; archived decisions, classifications and scores are ignored.
One incomplete pair excludes both choices from the post's outcome summaries.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import gzip
from hashlib import sha256
import json
from pathlib import Path

from .game import Game

MODELS = {"glm": "z-ai/glm-5.3", "qwen": "qwen/qwen3.8-2.4t-a95b",
          "astra": "openai/gpt-6-astra", "fable": "anthropic/claude-fable-5.1"}
PROTOCOL = "phase-space-v1-neutral-utility"
STAGE = "perspective_grid"
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "post"


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(text):
    def invalid(value):
        raise ValueError(f"invalid JSON constant: {value}")
    return json.loads(text, object_pairs_hook=_object, parse_constant=invalid)


def prompt(s, t, role, replicate):
    """Reproduce the archived collection prompt; never call a model."""
    if role not in ("row", "column") or type(replicate) is not int or replicate not in (0, 1):
        raise ValueError("expected a row/column role and label block 0/1")
    labels = ("A", "B") if replicate == 0 else ("B", "A")
    matrix = Game(s=s, t=t).matrix()
    table = "\n".join(
        f"your action={labels[i]}, opponent action={labels[j]}: "
        f"(your payoff {float(matrix[i][j][0]):.8g}, opponent payoff {float(matrix[i][j][1]):.8g})"
        for i in range(2) for j in range(2))
    return (f"You are the {role} player in a one-shot simultaneous two-player game.\n"
            "Choose A or B to maximize your own expected numerical payoff. The displayed payoffs "
            "are the complete experimental objective; do not add an external social or moral preference. "
            "The other player has the same objective, but you cannot observe its choice. "
            "There is no communication, enforcement, repetition, or future reward.\n"
            "The full payoff matrix is:\n" + table + "\n"
            "Return only a JSON object with final_action (A or B), belief_opponent_A "
            "(your probability from 0 to 1 that the other player chooses A), and confidence "
            "(from 0 to 1). Do not include an explanation.")


def _action(record):
    """Only a complete JSON object with final_action A/B supplies an action."""
    try:
        content = record["response"]["choices"][0]["message"]["content"]
        decision = _json(content)
    except (ValueError, TypeError, KeyError, IndexError):
        return None
    if not isinstance(decision, dict) or decision.get("final_action") not in ("A", "B"):
        return None
    mapping = record["label_mapping"]
    return "C" if decision["final_action"] == mapping["C"] else "D"


@dataclass(frozen=True)
class GameObservation:
    model_key: str
    model: str
    s: float
    t: float
    replicate: int
    row_action: str | None
    column_action: str | None

    @property
    def valid(self):
        return self.row_action is not None and self.column_action is not None


def _counts(games):
    games = tuple(games)
    outcomes = Counter(g.row_action + g.column_action for g in games if g.valid)
    valid = sum(outcomes.values())
    c = 2 * outcomes["CC"] + outcomes["CD"] + outcomes["DC"]
    return {"planned_games": len(games), "valid_games": valid,
            "excluded_games": len(games) - valid, "paired_decisions": 2 * valid,
            "C_choices": c, "cooperation_rate": c / (2 * valid) if valid else None,
            **{key: outcomes[key] for key in ("CC", "CD", "DC", "DD")}}


@dataclass(frozen=True)
class Study:
    games: tuple[GameObservation, ...]

    def summary(self):
        result = _counts(self.games)
        valid_decisions = sum(a is not None for g in self.games for a in (g.row_action, g.column_action))
        correct = total = 0
        for g in self.games:
            region = Game(s=g.s, t=g.t).region()
            if g.valid and region in ("defection_dominant", "cooperation_dominant"):
                target = "D" if region == "defection_dominant" else "C"
                total += 2
                correct += (g.row_action == target) + (g.column_action == target)
        result.update(planned_decisions=2 * len(self.games), recorded_decisions=2 * len(self.games),
                      valid_decisions=valid_decisions, invalid_decisions=2 * len(self.games) - valid_decisions,
                      excluded_valid_decisions=valid_decisions - result["paired_decisions"],
                      dominance_decisions=total, dominance_correct=correct,
                      dominance_rate=correct / total if total else None,
                      by_model={key: _counts(g for g in self.games if g.model_key == key) for key in MODELS})
        return result

    def cells(self):
        groups = defaultdict(list)
        for g in self.games:
            groups[g.model_key, g.s, g.t].append(g)
        return [{"model_key": key, "model": MODELS[key], "s": s, "t": t, **_counts(games)}
                for (key, s, t), games in sorted(groups.items())]

    def regions(self):
        groups = defaultdict(list)
        for g in self.games:
            groups[g.model_key, Game(s=g.s, t=g.t).region()].append(g)
        return [{"model_key": key, "model": MODELS[key], "region": region, **_counts(games)}
                for (key, region), games in sorted(groups.items())]


def validate_records(records, blocks):
    """Reject missing/duplicate/foreign records or inconsistent paired designs.

    This in-memory entry point is for auditing. load_study additionally verifies
    file hashes. Invalid returned actions remain recorded, never filled in.
    """
    expected = {}
    for rep in (0, 1):
        for ti in range(13):
            for si in range(13):
                for model in MODELS:
                    for role in ("row", "column"):
                        case_id = f"grid-{13 * ti + si:03}"
                        job = f"{PROTOCOL}/{STAGE}/{rep}/{case_id}/{model}/{role}"
                        expected[job] = (rep, case_id, model, role, -1 + si / 4, -1 + ti / 4)
    if len(blocks) != 2:
        raise ValueError("both original label-block manifests are required")
    for rep, block in enumerate(blocks):
        required = {k for k, v in expected.items() if v[0] == rep}
        if (block.get("replicate") != rep or block.get("stage") != STAGE or
                block.get("protocol") != PROTOCOL or block.get("models") != MODELS or
                block.get("max_tokens") != 4096 or block.get("reasoning_effort") != "low" or
                block.get("temperature") != "provider_default" or
                len(block.get("job_ids", [])) != len(required) or set(block["job_ids"]) != required):
            raise ValueError("manifest does not describe the complete post cohort")
    seen, pairs = set(), defaultdict(dict)
    for record in records:
        job = record.get("job_id")
        if job not in expected or job in seen:
            raise ValueError(f"unexpected or duplicate job: {job}")
        seen.add(job)
        rep, case_id, model, role, s, t = expected[job]
        case = record["case"]
        if (record["model_key"] != model or record["model"] != MODELS[model] or record["role"] != role or
                case["case_id"] != case_id or case["replicate"] != rep or case["stage"] != STAGE):
            raise ValueError(f"record identity/pairing mismatch: {job}")
        payoffs = case["payoffs"]
        if any(type(payoffs[k]) not in (int, float) or payoffs[k] != v
               for k, v in {"s": s, "t": t, "S": s, "T": t, "R": 1, "P": 0}.items()):
            raise ValueError(f"payoffs disagree with the scheduled grid: {job}")
        mapping = {"C": "A", "D": "B"} if rep == 0 else {"C": "B", "D": "A"}
        req = record["request"]
        if (record["label_mapping"] != mapping or req["model"] != MODELS[model] or
                req["messages"] != [{"role": "user", "content": prompt(s, t, role, rep)}] or
                req["max_tokens"] != 4096 or req["reasoning"] != {"effort": "low"} or
                "temperature" in req or req["response_format"] != {"type": "json_object"}):
            raise ValueError(f"prompt, labels or settings mismatch: {job}")
        if (record["status"] != "success" or record["http_status"] != 200 or
                record["response_model"] != MODELS[model] or record["response"]["model"] != MODELS[model]):
            raise ValueError(f"unexpected transport/model metadata in historical cohort: {job}")
        start, finish = (datetime.fromisoformat(record[k]) for k in ("started_utc", "finished_utc"))
        if start.tzinfo is None or finish.tzinfo is None or finish < start:
            raise ValueError(f"invalid timestamps: {job}")
        pairs[model, s, t, rep][role] = _action(record)
    if seen != set(expected):
        raise ValueError(f"missing {len(set(expected) - seen)} scheduled decisions; refusing a smaller denominator")
    return Study(tuple(GameObservation(model, MODELS[model], s, t, rep, roles["row"], roles["column"])
                       for (model, s, t, rep), roles in sorted(pairs.items())))


def load_study(data_dir=None):
    directory = Path(data_dir) if data_dir is not None else DATA_DIR
    manifest = _json((directory / "manifest.json").read_text())
    filenames = ("block-0.json", "block-1.json", "records.jsonl.gz")
    if set(manifest["sha256"]) != set(filenames):
        raise ValueError("unexpected cohort file list")
    blobs = {name: (directory / name).read_bytes() for name in filenames}
    for name, blob in blobs.items():
        if sha256(blob).hexdigest() != manifest["sha256"][name]:
            raise ValueError(f"source hash mismatch: {name}")
    raw = gzip.decompress(blobs["records.jsonl.gz"])
    if sha256(raw).hexdigest() != manifest["historical"]["extracted_uncompressed_sha256"]:
        raise ValueError("uncompressed source hash mismatch")
    return validate_records((_json(line) for line in raw.splitlines()),
                            [_json(blobs[f"block-{rep}.json"]) for rep in (0, 1)])

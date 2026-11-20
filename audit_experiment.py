"""Run the real audit environment through Inspect using scripted mock models.

Usage: python audit_experiment.py runs/audit-check --setting hidden
       inspect view --log-dir runs/audit-check
No API keys or network model calls. These are synthetic software checks.
"""

import argparse
import json
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import ModelOutput, get_model

from gut.audit_game import ACTIONS, demo_game
from gut.audit_inspect import audit_task


def mock_attacker(game, baseline="maximize"):
    def respond(messages, tools, tool_choice, config):
        view = json.loads(messages[-1].text.split("\n")[-1])
        row = next(t for t in game.evaluate(view["checking_probabilities"][0])["types"]
                   if t["name"] == view["private_type"])
        # Declared tie rule: first legal best response, abstention first.
        action = row["best_responses"][0] if baseline == "maximize" else baseline
        return ModelOutput.from_content(model="mockllm/attacker", content=json.dumps({"action": action}))
    return get_model("mockllm/attacker", custom_outputs=respond)


def export_log(path, destination):
    log = read_eval_log(path)
    with Path(destination).open("x") as stream:
        for sample in log.samples or []:
            record = {"sample_id": sample.id, "epoch": sample.epoch,
                      "status": "error" if sample.error else sample.metadata.get("record", {}).get("status", "incomplete"),
                      "record": sample.metadata.get("record"),
                      "error": sample.error.model_dump(mode="json") if sample.error else None,
                      "native_log": str(path)}
            stream.write(json.dumps(record)+"\n")
    return log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--setting", choices=("known", "hidden"), default="hidden")
    parser.add_argument("--punishment", default="1/2")
    parser.add_argument("--spread", default="3/10")
    parser.add_argument("--coverage", nargs="+", default=["1/4", "1/2", "3/4"])
    parser.add_argument("--baseline", choices=("maximize", *ACTIONS), default="maximize")
    parser.add_argument("--repetitions", type=int, default=1)
    args = parser.parse_args()
    game = demo_game(args.setting, args.punishment, args.spread)
    task = audit_task(game, {"attacker": mock_attacker(game, args.baseline)},
                      coverages=args.coverage, repetitions=args.repetitions)
    task.metadata.update(baseline=args.baseline, tie_rule="abstain_first_then_target_a",
                         seed=100, setting=args.setting, spread=args.spread)
    args.output.mkdir(parents=True, exist_ok=False)
    logs = inspect_eval(task, model=None, log_dir=str(args.output), display="none",
                        max_retries=0, max_tokens=400, max_samples=1, log_model_api=True)
    if len(logs) != 1:
        raise RuntimeError("Expected exactly one native log.")
    log = export_log(logs[0].location, args.output / "observations.jsonl")
    valid = sum(s.metadata.get("record", {}).get("status") == "valid" for s in log.samples or [])
    print(f"Synthetic Inspect run: {valid}/{len(log.samples or [])} valid decisions; {logs[0].location}")
    if log.status != "success" or valid != len(log.samples or []):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

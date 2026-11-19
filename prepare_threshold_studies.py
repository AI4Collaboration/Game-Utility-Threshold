"""Prepare the controlled threshold suite OFFLINE. Never calls a model API.

These are software pilots, not a final sample-size decision or new LLM evidence.
Use individual collectors to freeze live model/provider/budget settings later.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from gut import experiment as canonical
from gut import lab_experiment as lab
from gut import oversight_experiment as oversight
from gut.canonical import EXAMPLES


def prepare(output, repetitions=2, simulate=False, figures=False):
    if type(repetitions) is not int or not 1 <= repetitions <= 100:
        raise ValueError("Use 1..100 pilot repetitions per presentation block.")
    if figures and not simulate:
        raise ValueError("Figures require --simulate; never present empty plans as observations.")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    entries = []
    for game in EXAMPLES:
        directory = output/game
        plan = canonical.save_plan(directory, game=game, version="v2", repetitions=repetitions)
        if simulate:
            canonical.collect(directory)
            from experiment import report
            report(directory, plot=figures)
        entries.append({"study": game, "plan": f"{game}/plan.json", "sha256": plan["sha256"],
                        "main_conditions": len(plan["conditions"]), "max_requests": len(plan["jobs"]),
                        "unit": "paired game; two stateless requests", "live_adapter": True})
    models = [{"id": "synthetic/demo", "provider": "local", "returned_provider": "local",
               "accepted_models": ["synthetic/demo"], "context_length": 1000,
               "prompt_price": "0", "completion_price": "0", "request_price": "0"}]
    for design in ("defense", "attack_cost", "resource"):
        name = f"oversight-{design}"
        directory = output/name
        plan = oversight.save_plan(directory, models=models, budget_usd="1", mode="synthetic",
                                   primary_reps=repetitions, framing_reps=repetitions, design=design)
        if simulate:
            oversight.collect(directory, stage="pilot", max_calls=len(plan["jobs"]))
            oversight.collect(directory, stage="main", max_calls=len(plan["jobs"]))
            if figures:
                from gut.oversight_report import report
                report(directory)
            else:
                from gut.oversight_report import summarize
                loaded, rows = oversight.observations(directory)
                (directory/"summary.json").write_text(json.dumps(summarize(loaded, rows), indent=2)+"\n")
        entries.append({"study": name, "plan": f"{name}/plan.json", "sha256": plan["sha256"],
                        "main_conditions": len(plan["conditions"]), "max_requests": len(plan["jobs"]),
                        "unit": "one AI response at imposed protection", "live_adapter": True})
    directory = output/"notebook-audit"
    directory.mkdir()
    plan = lab.make_plan(version="v2")
    (directory/"plan.json").write_text(json.dumps(plan, indent=2)+"\n")
    if simulate:
        result = lab.run(plan)
        (directory/"records.json").write_text(json.dumps(result, indent=2)+"\n")
        # Analyze the serialized observations, exactly as with the standalone runner.
        lab.report(directory, json.loads((directory/"plan.json").read_text()),
                   json.loads((directory/"records.json").read_text()), figures=figures)
    entries.append({"study": "notebook-audit", "plan": "notebook-audit/plan.json", "sha256": plan["sha256"],
                    "main_conditions": 6, "max_requests": plan["max_requests"],
                    "unit": "reviewer calibration, then separate reporting/review episodes", "live_adapter": False})
    root = Path(__file__).resolve().parent
    sources = ["experiment.py", "oversight_experiment.py", "lab_experiment.py", "prepare_threshold_studies.py",
               *[str(p.relative_to(root)) for p in sorted((root/"gut").glob("*.py"))]]
    manifest = {"schema": "controlled-threshold-suite-v2", "mode": "synthetic", "live_model_calls": 0,
                "simulated": simulate, "repetitions_per_block": repetitions, "studies": entries,
                "max_synthetic_requests": sum(e["max_requests"] for e in entries),
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()),
                "source_sha256": {name: sha256((root/name).read_bytes()).hexdigest() for name in sources},
                "scope": "Offline setup. Eight study plans cover seven games; oversight has a separate tie diagnostic. No new LLM findings. Notebook counts use its own calibration design, not repetitions_per_block."}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New directory; never overwrite an earlier study")
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--simulate", action="store_true", help="Also exercise each plan with synthetic actors")
    parser.add_argument("--figures", action="store_true", help="Separate 2D plots; requires analysis packages")
    manifest = prepare(**vars(parser.parse_args()))
    print(json.dumps({k: manifest[k] for k in ("schema", "simulated", "live_model_calls", "max_synthetic_requests")}, indent=2))


if __name__ == "__main__":
    main()

"""Prepare the four established canonical games OFFLINE. Never calls a model API.

These are software pilots, not a final sample-size decision or new LLM evidence.
Use individual collectors to freeze live model/provider/budget settings later.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

from gut import experiment as canonical
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
    root = Path(__file__).resolve().parent
    sources = ["experiment.py", "prepare_threshold_studies.py",
               *[str(p.relative_to(root)) for p in sorted((root/"gut").glob("*.py"))]]
    manifest = {"schema": "canonical-threshold-suite-v3", "mode": "synthetic", "live_model_calls": 0,
                "simulated": simulate, "repetitions_per_block": repetitions, "studies": entries,
                "max_synthetic_requests": sum(e["max_requests"] for e in entries),
                "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip()),
                "source_sha256": {name: sha256((root/name).read_bytes()).hexdigest() for name in sources},
                "scope": "Offline setup for four established games. Custom oversight and notebook prototypes are excluded pending published-design review. No new LLM findings."}
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

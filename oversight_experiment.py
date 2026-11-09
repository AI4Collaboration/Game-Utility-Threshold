"""Plan, collect and report a small oversight LLM validation study."""
import argparse
import json
from pathlib import Path

from gut.oversight_experiment import acknowledge_failure, collect, load_run, save_plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("directory", type=Path)
    plan.add_argument("--models", type=Path, required=True, help="Explicit model/provider/price specifications JSON")
    plan.add_argument("--budget-usd", required=True)
    plan.add_argument("--mode", choices=("openrouter", "synthetic"), default="openrouter")
    plan.add_argument("--primary-reps", type=int, default=25)
    plan.add_argument("--framing-reps", type=int, default=10)
    run = commands.add_parser("run")
    run.add_argument("directory", type=Path)
    run.add_argument("--stage", choices=("pilot", "main"), default="pilot")
    run.add_argument("--live", action="store_true")
    run.add_argument("--max-calls", type=int, required=True)
    run.add_argument("--workers", type=int, default=4)
    status = commands.add_parser("status")
    status.add_argument("directory", type=Path)
    report = commands.add_parser("report")
    report.add_argument("directory", type=Path)
    audit = commands.add_parser("audit", help="record a reviewed failure; retain its cost reserve and never retry it")
    audit.add_argument("directory", type=Path)
    audit.add_argument("--job-id", required=True)
    audit.add_argument("--note", required=True)
    args = vars(parser.parse_args())
    command, directory = args.pop("command"), args.pop("directory")
    if command == "plan":
        args["models"] = json.loads(args["models"].read_text())
        result = save_plan(directory, **args)
        print(json.dumps({"plan_sha256": result["sha256"], "main_requests": sum(j["stage"] == "main" for j in result["jobs"]),
                          "pilot_requests": sum(j["stage"] == "pilot" for j in result["jobs"]), "budget_usd": result["budget_usd"]}))
    elif command == "run":
        print(json.dumps(collect(directory, **args), indent=2))
    elif command == "status":
        plan, started, finished, committed = load_run(directory)
        print(json.dumps({"planned": len(plan["jobs"]), "started": len(started), "finished": len(finished),
                          "cost_plus_reservations_usd": str(committed), "budget_usd": plan["budget_usd"]}))
    elif command == "audit":
        acknowledge_failure(directory, **args)
        print("Audit recorded; original response, status and cost reservation preserved.")
    else:
        from gut.oversight_report import report
        report(directory)
        print(f"Report written to {directory}/analysis")


if __name__ == "__main__":
    main()

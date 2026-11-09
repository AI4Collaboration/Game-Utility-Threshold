"""Plan, collect, summarize, and verify one controlled PD cost sweep."""

import argparse
import csv
import json
import os
from pathlib import Path
import tempfile

from gut.experiment import collect, save_plan, summarize


def report(directory, plot=False):
    result = summarize(directory)
    output = Path(directory) / "analysis"
    output.mkdir(exist_ok=True)
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    rows = result["cells"]
    with (output / "cells.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if plot:
        os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "gut-matplotlib"))
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, (ax, counts) = plt.subplots(2, 1, figsize=(9, 6), sharex=True,
                                        gridspec_kw={"height_ratios": [3, 1]}, layout="constrained")
        available = [r for r in rows if r["cooperation_rate"] is not None]
        ax.errorbar([r["z"] for r in available], [r["cooperation_rate"] for r in available],
                    yerr=[[r["cooperation_rate"]-r["lower_95"] for r in available],
                          [r["upper_95"]-r["cooperation_rate"] for r in available]],
                    fmt="o", capsize=3, color="#087f8c", label="Observed fraction; 95% pointwise bounds")
        for threshold, label in ((0.5, "Tie against D"), (1, "Tie against C")):
            ax.axvline(threshold, color="#777", ls="--", lw=1, label=label)
        ax.set(ylim=(-0.04, 1.04), ylabel="Cooperation rate (equal weight per label block)")
        ax.legend(fontsize=8)
        counts.plot([r["z"] for r in rows], [r["valid_games"] for r in rows], "o", label="Valid pairs")
        counts.plot([r["z"] for r in rows], [r["planned_games"] for r in rows], "_", label="Planned pairs")
        counts.set(xlabel="Defection cost z · fixed T=2, R=1, P=0, S=−0.5", ylabel="Games", ylim=(0, None))
        counts.legend(fontsize=8)
        prefix = "SYNTHETIC PIPELINE DEMO — NOT MODEL EVIDENCE" if result["mode"] == "synthetic" else result["model"]
        fig.suptitle(prefix)
        fig.savefig(output / "cooperation.png", dpi=180)
        fig.savefig(output / "cooperation.svg", metadata={"Date": None})
        plt.close(fig)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="freeze settings and randomized job order; no API calls")
    plan.add_argument("directory", type=Path)
    plan.add_argument("--mode", choices=("synthetic", "openrouter"), default="synthetic")
    plan.add_argument("--model", default="synthetic/demo")
    plan.add_argument("--provider", default="local")
    plan.add_argument("--repetitions", type=int, default=10, help="games per label block per cost; pilot default")
    plan.add_argument("--seed", type=int, default=20261109, help="schedule randomization, not a provider seed")
    plan.add_argument("--temperature", type=float, default=0.7)
    plan.add_argument("--max-tokens", type=int, default=512)
    run = commands.add_parser("run", help="resume unattempted jobs; never automatically retry an attempt")
    run.add_argument("directory", type=Path)
    run.add_argument("--live", action="store_true")
    run.add_argument("--max-calls", type=int, help="maximum new attempts in this invocation")
    analysis = commands.add_parser("report", help="reparse raw answers and export counts and uncertainty")
    analysis.add_argument("directory", type=Path)
    analysis.add_argument("--plot", action="store_true")
    proof = commands.add_parser("proofs", help="map raw choices to Lean certificates, including negative findings")
    proof.add_argument("directory", type=Path)
    proof.add_argument("--check", action="store_true", help="compile with Lean before marking proofs verified")
    proof.add_argument("--lake", default="lake", help="path to the pinned toolchain's lake executable")
    args = vars(parser.parse_args())
    command = args.pop("command")
    directory = args.pop("directory")
    if command == "plan":
        result = save_plan(directory, **args)
        print(f'Frozen {len(result["jobs"])//2} games / {len(result["jobs"])} decisions in {directory}/plan.json')
    elif command == "run":
        print(f"Recorded {collect(directory, **args)} new attempts")
    elif command == "report":
        result = report(directory, **args)
        print(json.dumps({k: v for k, v in result.items() if k != "cells"}, indent=2))
    else:
        from gut.proofs import export_proofs
        print(json.dumps(export_proofs(directory, **args), indent=2))


if __name__ == "__main__":
    main()

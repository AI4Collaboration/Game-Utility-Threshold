"""Plan, collect, summarize, and verify one controlled PD cost sweep."""

import argparse
import csv
import json
import os
from pathlib import Path
import tempfile

from gut.experiment import collect, save_plan, summarize
from gut.canonical import EXAMPLES, example


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
        bos = result["game"] == "battle_of_sexes"
        fig, axes = plt.subplots(4 if bos else 2, 1, figsize=(9, 10 if bos else 6), sharex=True,
                                 gridspec_kw={"height_ratios": [2, 2, 2, 1] if bos else [3, 1]}, layout="constrained")
        counts = axes[-1]
        metrics = [("row_first_rate", "row_first_lower_95", "row_first_upper_95", "Row chooses X"),
                   ("column_first_rate", "column_first_lower_95", "column_first_upper_95", "Column chooses X"),
                   ("matching_rate", "matching_lower_95", "matching_upper_95", "Players match")] if bos else [
                   ("cooperation_rate", "lower_95", "upper_95", "Cooperation; 95% pointwise bounds")]
        for ax, (center, low, high, label) in zip(axes[:-1], metrics):
            available = [r for r in rows if r[center] is not None]
            ax.errorbar([r["z"] for r in available], [r[center] for r in available],
                        yerr=[[r[center]-r[low] for r in available], [r[high]-r[center] for r in available]],
                        fmt="o", capsize=3, alpha=0.8, label=label)
            ax.set(ylim=(-0.04, 1.04), ylabel=label if bos else "Cooperation rate")
            ax.set_title("95% pointwise bounds · equal weight per label block", fontsize=9)
        spec = example(result["game"])
        thresholds = {(t, f'{role}: tie against {spec.actions[i]}') for role in ("row", "column")
                      for i, t in enumerate(spec.thresholds(role)) if t >= 0}
        for threshold in sorted({t for t, _ in thresholds}):
            label = " / ".join(sorted(label for t, label in thresholds if t == threshold))
            for ax in axes[:-1]:
                ax.axvline(float(threshold), color="#777", ls="--", lw=1, label=label)
        axes[0].legend(fontsize=8)
        counts.plot([r["z"] for r in rows], [r["valid_games"] for r in rows], "o", label="Valid pairs")
        counts.plot([r["z"] for r in rows], [r["planned_games"] for r in rows], "_", label="Planned pairs")
        counts.set(xlabel=f"{spec.name} · cost of {spec.actions[1]} (z)", ylabel="Games", ylim=(0, None))
        counts.legend(fontsize=8)
        prefix = "SYNTHETIC PIPELINE DEMO — NOT MODEL EVIDENCE" if result["mode"] == "synthetic" else result["model"]
        fig.suptitle(prefix)
        filename = "outcomes" if bos else "cooperation"
        fig.savefig(output / f"{filename}.png", dpi=180)
        fig.savefig(output / f"{filename}.svg", metadata={"Date": None})
        plt.close(fig)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="freeze settings and randomized job order; no API calls")
    plan.add_argument("directory", type=Path)
    plan.add_argument("--game", choices=tuple(EXAMPLES), default="pd")
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

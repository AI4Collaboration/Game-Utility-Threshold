"""Recompute the post's results and five figures from saved data. No model calls."""

import argparse
import csv
from fractions import Fraction
import html
import json
import os
from pathlib import Path
import tempfile

from gut.game import BASELINE_PD, Game, grid_counts, pd_grid
from gut.study import MODELS, load_study

POST = "https://www.lesswrong.com/posts/HJSWoWCQefj2L8W8d/when-defection-stops-paying-why-utility-thresholds-matter-1"
NAMES = {"glm": "GLM-5.3", "qwen": "Qwen3.8", "astra": "GPT-6 Astra", "fable": "Claude Fable 5.1"}
CAPTIONS = [
    "Calculated payoffs in the original PD. The choices tie at k=2 against C and k=1 against D. At equality both actions are optimal.",
    "The normalized baseline and the adjusted table. The cost z is subtracted only from a player choosing D, using the fixed baseline-normalized units.",
    "Two calculated paths: PD through Chicken, or PD through Stag Hunt, to cooperation dominance. Zero marks equality, not a strict preference.",
    "Theory only: conditional responses to D across 625 PD tables. There are 25 distinct thresholds, each shared by 25 tables. Exact ties are counted separately.",
    "Observed cooperation in 1,350 valid paired games. Each cell has at most two games; n=1 marks a reduced denominator. Above T=1: PD on the left, Chicken on the right. Below T=1: Stag Hunt on the left, cooperation dominance on the right. S=0 and T=1 are boundaries. These are simultaneous baseline games, not observations of the penalty intervention.",
]


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def theory_rows():
    thresholds = sorted({game.thresholds()[1] for game in pd_grid()})
    endpoints = [Fraction(0), *thresholds, Fraction(6, 5)]
    points = sorted(set(endpoints + [(a+b)/2 for a, b in zip(endpoints, endpoints[1:])]))
    return [{"z_exact": str(z), "z": float(z), **grid_counts(z), "total": 625} for z in points]


def figures(output, cells):
    # Keep the optional plotting library out of the game, data and server paths.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "gut-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "svg.hashsalt": "gut-post"})
    teal, red, blue = "#087f8c", "#ba463c", "#4163c7"
    def save(fig, number):
        fig.savefig(output / f"figure-{number}.png", dpi=180, bbox_inches="tight")
        fig.savefig(output / f"figure-{number}.svg", bbox_inches="tight", metadata={"Date": None})
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.7), layout="constrained")
    for i, (ax, opponent) in enumerate(zip(axes, ("C", "D"))):
        xs = [Fraction(j, 40) for j in range(121)]
        ax.plot(list(map(float, xs)), [float(BASELINE_PD.matrix(k)[0][i][0]) for k in xs], color=teal, label="Choose C")
        ax.plot(list(map(float, xs)), [float(BASELINE_PD.matrix(k)[1][i][0]) for k in xs], color=red, label="Choose D")
        threshold = float(BASELINE_PD.thresholds()[i])
        ax.axvline(threshold, color="#666", ls="--", label=f"Tie at k={threshold:g}")
        ax.set(title=f"Opponent chooses {opponent}", xlabel="Defection cost k", ylabel="Your points")
        ax.legend(frameon=False)
    save(fig, 1)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4), layout="constrained")
    matrices = [[['(1, 1)', '(S, T)'], ['(T, S)', '(0, 0)']],
                [['(1, 1)', '(S, T−z)'], ['(T−z, S)', '(−z, −z)']]]
    for ax, matrix, title in zip(axes, matrices, ("Baseline: R=1, P=0", "After defection cost z")):
        ax.axis("off")
        table = ax.table(cellText=matrix, rowLabels=["You: C", "You: D"], colLabels=["Other: C", "Other: D"],
                         loc="center", cellLoc="center", bbox=[0.13, 0.2, 0.87, 0.6])
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        ax.set_title(title)
    fig.suptitle("Each pair lists your points first")
    save(fig, 2)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout="constrained")
    for ax, game, title in zip(axes, (Game(t=2, s="-0.5"), Game(t="1.5", s=-1)),
                             ("A: S=−0.5, T=2 · through Chicken", "B: S=−1, T=1.5 · through Stag Hunt")):
        xs = [Fraction(j, 40) for j in range(61)]
        for i, (label, color) in enumerate((("Against C", blue), ("Against D", teal))):
            ax.plot(list(map(float, xs)), [float(game.margins(z)[i]) for z in xs], label=label, color=color)
        for threshold in game.thresholds():
            ax.axvline(float(threshold), color="#777", ls=":")
        ax.axhline(0, color="#333", lw=0.8)
        ax.set(title=title, xlabel="Defection cost z", ylabel="C points minus D points")
        ax.legend(frameon=False)
    save(fig, 3)

    fig, (ax, ties_ax) = plt.subplots(2, 1, figsize=(9, 5), sharex=True, layout="constrained", height_ratios=[3, 1])
    thresholds = sorted({g.thresholds()[1] for g in pd_grid()})
    bounds = [Fraction(0), *thresholds, Fraction(6, 5)]
    for index, (left, right) in enumerate(zip(bounds, bounds[1:])):
        counts = grid_counts((left+right)/2)
        for key, color, label in (("cooperate", teal, "C strictly better"), ("defect", red, "D strictly better")):
            ax.plot([float(left), float(right)], [counts[key]/625]*2, color=color,
                    label=label if index == 0 else None)
    for key, color in (("cooperate", teal), ("defect", red)):
        ax.scatter(list(map(float, thresholds)), [grid_counts(z)[key]/625 for z in thresholds], s=14, color=color)
    ties_ax.vlines(list(map(float, thresholds)), 0, [grid_counts(z)["tie"]/625 for z in thresholds], color=blue)
    ax.set(ylabel="Share of 625 baseline games", ylim=(-0.02, 1.02), title="Best response when the opponent defects · theory only")
    ax.legend(frameon=False)
    ties_ax.set(xlabel="Defection cost z", ylabel="Tie share", ylim=(0, 0.05))
    save(fig, 4)

    fig, axes = plt.subplots(1, 4, figsize=(15, 4.6), sharex=True, sharey=True, layout="constrained")
    cmap = LinearSegmentedColormap.from_list("cooperation", [red, "#f3eee4", teal])
    for ax, key in zip(axes, MODELS):
        grid = [[float("nan")]*13 for _ in range(13)]
        subset = [cell for cell in cells if cell["model_key"] == key]
        for cell in subset:
            grid[round((cell["t"]+1)*4)][round((cell["s"]+1)*4)] = cell["cooperation_rate"] if cell["cooperation_rate"] is not None else float("nan")
        image = ax.imshow(grid, origin="lower", extent=(-1.125, 2.125, -1.125, 2.125), vmin=0, vmax=1, cmap=cmap)
        ax.axvline(0, color="#e5b328", lw=1.2)
        ax.axhline(1, color="#e5b328", lw=1.2)
        for cell in subset:
            if cell["valid_games"] != 2:
                ax.text(cell["s"], cell["t"], f'n={cell["valid_games"]}', ha="center", va="center", fontsize=6,
                        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85, "pad": 1})
        ax.set(title=NAMES[key], xlabel="S", xticks=[-1, 0, 1, 2], yticks=[-1, 0, 1, 2])
    axes[0].set_ylabel("T")
    fig.colorbar(image, ax=axes, location="bottom", shrink=0.55, label="Observed C choices / valid paired decisions")
    fig.suptitle("169 payoff settings per model · R=1, P=0 · at most two games per cell")
    save(fig, 5)


def report(output, summary, regions):
    rows = "".join(f"<tr><td>{html.escape(NAMES[row['model_key']])}</td><td>{html.escape(row['region'].replace('_', ' '))}</td>"
                   f"<td>{row['C_choices']}/{row['paired_decisions']}</td><td>{row['cooperation_rate']:.2%}</td></tr>" for row in regions)
    figures_html = "".join(f'<figure><a href="figure-{i}.svg"><img src="figure-{i}.png" alt="{html.escape(caption)}"></a>'
                           f'<figcaption><strong>Figure {i}.</strong> {html.escape(caption)} '
                           f'<a href="figure-{i}.svg">SVG</a> · <a href="figure-{i}.png">PNG</a></figcaption></figure>'
                           for i, caption in enumerate(CAPTIONS, 1))
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Game Utility Thresholds · post reproduction</title><style>
body{{font:17px/1.6 system-ui,sans-serif;max-width:1120px;margin:40px auto;padding:0 24px;color:#152e37;background:#f9faf8}}
h1{{line-height:1.15}}a{{color:#087486}}figure{{margin:40px 0}}img{{width:100%;background:white}}figcaption{{max-width:90ch}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:8px;text-align:left;border-bottom:1px solid #ccd5d5}}
.table{{overflow:auto}}.note{{padding:20px;background:#e8f2ef;border-radius:12px}}code{{overflow-wrap:anywhere}}</style>
<h1>When defection stops paying</h1><p>Offline reproduction of the calculations and historical experiment in the <a href="{POST}">LessWrong post</a>.</p>
<div class="note"><strong>{summary['dominance_correct']:,} / {summary['dominance_decisions']:,} = {summary['dominance_rate']:.2%}</strong>
of choices in strict-dominance regions matched the dominant action.</div>
<p>{summary['planned_games']:,} games were planned and recorded; {summary['valid_games']:,} have two valid choices.
There are {summary['invalid_decisions']} invalid outputs. Their {summary['excluded_valid_decisions']} valid partners are also excluded from paired summaries.
The heatmap therefore uses {summary['paired_decisions']:,} choices. Invalid responses remain in the source data.</p>
<p>The two choices within a game are paired outcomes, not independent replications.</p>
<p>Figures 1–4 are calculations. Figure 5 shows observations. The small samples do not measure an intervention threshold,
establish a model ranking, or demonstrate real-world safety. In Chicken and Stag Hunt, cooperation alone does not establish a best response.</p>
<p>Download <a href="summary.json">summary JSON</a>, <a href="cells.csv">cell counts</a>,
<a href="regions.csv">region counts</a>, or <a href="theory-grid.csv">theory counts with exact tie values</a>.</p>
{figures_html}<h2>Complete region counts</h2><p>Boundary cells are separate. Rates count both choices only when their paired game is valid.</p>
<div class="table"><table><thead><tr><th>Model</th><th>Region</th><th>C choices / choices</th><th>C rate</th></tr></thead><tbody>{rows}</tbody></table></div>
<p>Reproduce with <code>python3 reproduce.py</code>. This command verifies retained source hashes and reparses the saved responses; it makes no model calls.</p></html>'''
    (output / "index.html").write_text(page)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "report")
    parser.add_argument("--data-only", action="store_true", help="write JSON/CSV with only the Python standard library")
    args = parser.parse_args()
    study = load_study()
    summary, cells, regions = study.summary(), study.cells(), study.regions()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    for filename, rows in (("cells.csv", cells), ("regions.csv", regions), ("theory-grid.csv", theory_rows())):
        write_csv(args.output / filename, rows)
    if not args.data_only:
        try:
            figures(args.output, cells)
        except ImportError as exc:
            raise SystemExit("Tables saved. Install matplotlib for figures: python3 -m pip install 'matplotlib>=3.8,<4'") from exc
        report(args.output, summary, regions)
    print(f"Verified {summary['valid_games']}/{summary['planned_games']} paired games; dominance {summary['dominance_correct']}/{summary['dominance_decisions']}.")
    print(f"Saved to {args.output.resolve()}")


if __name__ == "__main__":
    main()

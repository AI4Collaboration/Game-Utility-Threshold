"""Render analytical and observed symmetric 2x2 phase-space figures.

No model calls are made. --theory-only is an explicit offline analytical mode.
Observed plots show only logged cells, with missing or invalid-only cells gray.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MPLCONFIGDIR", str(Path(os.environ.get("TMPDIR", "/tmp")) / "phase-space-matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Rectangle

from analyze_phase_space import DEFAULT_BOOTSTRAP_SAMPLES, DEFAULT_SEED, load_runs, summarize, write_csv
from utility_threshold.games.phase_space import PhasePoint


INK = "#18304b"
MISSING = "#e2e5e9"
COLORS = ["#167d9a", "#d98b25", "#9a559b", "#29966b", "#bc5964", "#6b72a5"]
REGIMES = {"cooperation_dominant": 0, "competition_dominant": 1,
           "coordination": 2, "anti_coordination": 3, "boundary": 4}
REGIME_LABELS = ["C dominates", "D dominates", "Coordination", "Anti-coordination", "Tie boundary"]


def _style() -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.titlesize": 11, "axes.labelsize": 11, "axes.labelcolor": INK,
                         "text.color": INK, "xtick.color": INK, "ytick.color": INK,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "figure.facecolor": "white", "savefig.facecolor": "white",
                         "svg.fonttype": "none"})


def _save(fig: Any, directory: Path, name: str, outputs: list[str]) -> None:
    for extension in ("png", "svg"):
        path = directory / f"{name}.{extension}"
        fig.savefig(path, dpi=190, bbox_inches="tight")
        outputs.append(path.name)
    plt.close(fig)


def _edges(values: Sequence[float]) -> np.ndarray:
    centers = np.array(sorted(set(values)), dtype=float)
    if len(centers) == 1:
        return np.array([centers[0] - 0.125, centers[0] + 0.125])
    midpoint = (centers[:-1] + centers[1:]) / 2
    return np.concatenate(([centers[0] - (centers[1] - centers[0]) / 2], midpoint,
                           [centers[-1] + (centers[-1] - centers[-2]) / 2]))


def _matrix(rows: Sequence[Mapping[str, Any]], s_values: Sequence[float], t_values: Sequence[float],
            field: str) -> np.ndarray:
    """No interpolation: place each observed value into its exact payoff cell."""
    matrix = np.full((len(t_values), len(s_values)), np.nan)
    s_index = {float(value): index for index, value in enumerate(s_values)}
    t_index = {float(value): index for index, value in enumerate(t_values)}
    for row in rows:
        value = row.get(field)
        if value is not None:
            matrix[t_index[float(row["t"])], s_index[float(row["s"])]] = float(value)
    return matrix


def _boundaries(ax: Any, *, welfare: bool = False, pd_label: bool = True) -> None:
    ax.axvline(0, color=INK, linewidth=0.85, linestyle="--", alpha=0.7)
    ax.axhline(1, color=INK, linewidth=0.85, linestyle="--", alpha=0.7)
    left, right = ax.get_xlim()
    bottom, top = ax.get_ylim()
    if welfare:
        xs = np.linspace(left, right, 300)
        ax.plot(xs, 2 - xs, color=INK, linewidth=1.3, linestyle=":", label="S + T = 2")
        ax.set_ylim(bottom, top)
    if left < 0 and top > 1:
        ax.add_patch(Rectangle((left, max(1, bottom)), min(0, right) - left,
                              top - max(1, bottom), fill=False, linewidth=1.2,
                              edgecolor=INK, linestyle=(0, (4, 3))))
        if pd_label:
            ax.text(left + 0.035 * (right - left), top - 0.055 * (top - bottom),
                    "PD", va="top", fontsize=9, weight="bold",
                    bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 2})
    ax.set_xlabel("S  ·  payoff to C against D")
    ax.set_ylabel("T  ·  payoff to D against C")


def analytical_rows(s_limits: tuple[float, float], t_limits: tuple[float, float], resolution: int = 121) -> list[dict[str, Any]]:
    rows = []
    s_values = np.unique(np.append(np.linspace(*s_limits, resolution), 0))
    t_values = np.unique(np.append(np.linspace(*t_limits, resolution), 1))
    s_values = s_values[(s_values >= s_limits[0]) & (s_values <= s_limits[1])]
    t_values = t_values[(t_values >= t_limits[0]) & (t_values <= t_limits[1])]
    for t in t_values:
        for s in s_values:
            point = PhasePoint(s=float(s), t=float(t))
            details = point.to_dict()
            rows.append({"s": float(s), "t": float(t), "quadrant": details["quadrant"],
                         "family": details["family"], "ordinal_order": details["ordinal_order"],
                         "regime_code": REGIMES[details["quadrant"]],
                         "interior_indifference_probability": details["symmetric_mixed_cooperation"],
                         "max_joint_welfare": max(2.0, float(s + t)),
                         "welfare_code": 0 if s + t < 2 - 1e-10 else 2 if s + t > 2 + 1e-10 else 1,
                         "pure_nash_count": len(details["pure_nash"])})
    return rows


def _render_theory(rows: Sequence[Mapping[str, Any]], directory: Path, outputs: list[str]) -> None:
    ss = sorted({float(row["s"]) for row in rows})
    ts = sorted({float(row["t"]) for row in rows})
    bounds = (min(ss), max(ss), min(ts), max(ts))
    # Ordinal boundaries are distinct from best-response boundaries. This panel
    # shows the article's full twelve-class partition, not just four quadrants.
    fig, axis = plt.subplots(figsize=(10, 9), layout="constrained")
    ordinal_cmap = ListedColormap(["#bde0cb", "#e7b6a9", "#ead9a6", "#c1d3ed", "#eeeeee"])
    axis.pcolormesh(_edges(ss), _edges(ts), _matrix(rows, ss, ts, "regime_code"),
                    cmap=ordinal_cmap, norm=BoundaryNorm(np.arange(-.5, 5.5), 5), rasterized=True)
    for value in [0, 1]:
        axis.axvline(value, color=INK, linewidth=1)
        axis.axhline(value, color=INK, linewidth=1)
    axis.plot([max(min(ss), min(ts)), min(max(ss), max(ts))],
              [max(min(ss), min(ts)), min(max(ss), max(ts))], color=INK, linewidth=1)
    signatures = sorted({row["ordinal_order"] for row in rows if "=" not in row["ordinal_order"]})
    names = {"T>R>P>S": "Prisoner's Dilemma", "T>R>S>P": "Chicken", "R>T>P>S": "Stag Hunt"}
    for signature in signatures:
        group = [row for row in rows if row["ordinal_order"] == signature]
        x, y = np.mean([row["s"] for row in group]), np.mean([row["t"] for row in group])
        axis.text(x, y, names.get(signature, "") + "\n" + signature.replace(">", " > "),
                  ha="center", va="center", fontsize=9, weight="medium")
    axis.set(xlim=bounds[:2], ylim=bounds[2:], xlabel="S · normalized sucker payoff",
             ylabel="T · normalized temptation payoff")
    axis.set_title("ANALYTICAL · twelve strict ordinal classes · R = 1, P = 0", fontsize=15, pad=15)
    fig.supxlabel("Solid lines: payoff-order ties S = 0, S = 1, T = 0, T = 1, S = T. Boundary games are retained separately. No LLM observations.", fontsize=9)
    _save(fig, directory, "00_analytical_ordinal_phase_space", outputs)
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.5), layout="constrained")
    regime_cmap = ListedColormap(["#3eaa81", "#ce7667", "#c3a153", "#6f92c4", "#e6e6e6"])
    axes[0].pcolormesh(_edges(ss), _edges(ts), _matrix(rows, ss, ts, "regime_code"),
                       cmap=regime_cmap, norm=BoundaryNorm(np.arange(-0.5, 5.5), 5), rasterized=True)
    axes[0].set_title("Best-response regimes")
    axes[0].legend(handles=[Patch(facecolor=regime_cmap(index), label=label) for index, label in enumerate(REGIME_LABELS)],
                   loc="lower left", fontsize=8, framealpha=0.94)
    cmap = plt.colormaps["viridis"].copy()
    cmap.set_bad(MISSING)
    axes[1].set_facecolor(MISSING)
    mesh = axes[1].pcolormesh(_edges(ss), _edges(ts),
                             _matrix(rows, ss, ts, "interior_indifference_probability"),
                             cmap=cmap, vmin=0, vmax=1, rasterized=True)
    fig.colorbar(mesh, ax=axes[1], label="q*  ·  opponent cooperation probability")
    axes[1].set_title("Interior indifference threshold  q* = S / (S + T − 1)")
    for axis in axes:
        axis.set(xlim=bounds[:2], ylim=bounds[2:])
        _boundaries(axis)
    fig.suptitle("ANALYTICAL · symmetric 2×2 strategy landscape · R = 1, P = 0", fontsize=15, weight="bold")
    fig.supxlabel("q* is an interior mixed equilibrium only in coordination/anti-coordination regions. Gray: no interior threshold. No LLM observations.", fontsize=9)
    _save(fig, directory, "01_analytical_strategy_landscape", outputs)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.5), layout="constrained")
    welfare_cmap = ListedColormap(["#8bc9b3", "#f5df9b", "#ab92c8"])
    axes[0].pcolormesh(_edges(ss), _edges(ts), _matrix(rows, ss, ts, "welfare_code"),
                       cmap=welfare_cmap, norm=BoundaryNorm([-0.5, 0.5, 1.5, 2.5], 3), rasterized=True)
    axes[0].set_title("Profiles maximizing joint welfare")
    axes[0].legend(handles=[Patch(facecolor=welfare_cmap(index), label=label) for index, label in enumerate(
        ("CC: welfare 2", "CC / CD / DC tie", "CD or DC: welfare S + T"))], loc="lower left", fontsize=8)
    mesh = axes[1].pcolormesh(_edges(ss), _edges(ts), _matrix(rows, ss, ts, "max_joint_welfare"),
                             cmap="cividis", rasterized=True)
    fig.colorbar(mesh, ax=axes[1], label="Maximum joint welfare")
    axes[1].set_title("Attainable joint welfare  max(2, S + T)")
    for axis in axes:
        axis.set(xlim=bounds[:2], ylim=bounds[2:])
        _boundaries(axis, welfare=True)
    fig.suptitle("ANALYTICAL · welfare transition at S + T = 2", fontsize=15, weight="bold")
    fig.supxlabel("Above the transition, asymmetric outcomes maximize total payoff; this does not by itself make them stable equilibria. No LLM observations.", fontsize=9)
    _save(fig, directory, "02_analytical_welfare_transition", outputs)

    threshold_rows = [{**row, "target_cost": max(0., row["t"]-1),
                       "dominance_cost": max(0., row["t"]-1, -row["s"])} for row in rows]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.5), layout="constrained")
    maximum = max(row["dominance_cost"] for row in threshold_rows)
    for axis, field, title in zip(axes, ["target_cost", "dominance_cost"],
                                  ["Cost on D to make CC a Nash equilibrium", "Cost on D to make C weakly dominant"]):
        mesh = axis.pcolormesh(_edges(ss), _edges(ts), _matrix(threshold_rows, ss, ts, field),
                               cmap="cividis", vmin=0, vmax=maximum, rasterized=True)
        axis.set(xlim=bounds[:2], ylim=bounds[2:])
        axis.set_title(title)
        _boundaries(axis)
    fig.colorbar(mesh, ax=list(axes), label="Minimum additive utility cost on D")
    fig.suptitle("ANALYTICAL · intervention thresholds · R = 1, P = 0", fontsize=15, weight="bold")
    fig.supxlabel("Left: max(0, T − 1). Right: max(0, T − 1, −S). Equality can leave indifference; strict dominance requires strictly positive adjusted margins. Not measured LLM thresholds.", fontsize=9)
    _save(fig, directory, "02b_analytical_intervention_thresholds", outputs)


def _short_model(model: str) -> str:
    return model.split("/", 1)[-1]


def _facet_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (row["model"], row["opponent_model"], row["mode"], row.get("opponent_cooperation_probability"))


def _facet_title(key: tuple[Any, ...]) -> str:
    model, opponent, mode, belief = key
    title = _short_model(model)
    if mode == "cross_play":
        title += f"\nvs {_short_model(opponent)}"
    elif mode == "fixed_belief":
        title += f"\nfixed belief q = {belief:g}"
    else:
        title += " · self-play"
    return title


def _render_heatmaps(analysis: Mapping[str, Any], directory: Path, outputs: list[str]) -> None:
    cells = [row for row in analysis["cells"] if row["mode"] != "fixed_belief"]
    if not cells:
        return
    points = list(analysis.get("points", [])) + cells
    ss = sorted({float(point["s"]) for point in points})
    ts = sorted({float(point["t"]) for point in points})
    facets: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in cells:
        facets[_facet_key(row)].append(row)
    keys = sorted(facets, key=lambda key: tuple(str(item) for item in key))
    specs = [("cooperation_rate_valid", "Cooperation among valid decisions", "viridis", 0, 1),
             ("mean_regret", "Mean action regret", "magma", 0, None),
             ("pure_nash_rate", "Observed pure Nash profiles", "viridis", 0, 1),
             ("welfare_optimal_rate", "Welfare-optimal observed profiles", "viridis", 0, 1),
             ("invalid_rate", "Invalid decisions / all decisions", "Reds", 0, 1)]
    for field, label, cmap_name, minimum, maximum in specs:
        available = [float(row[field]) for row in cells if row.get(field) is not None]
        if not available:
            continue
        vmax = maximum if maximum is not None else max(max(available), 1e-9)
        cmap = plt.colormaps[cmap_name].copy()
        cmap.set_bad(MISSING)
        for start in range(0, len(keys), 4):
            selected = keys[start:start + 4]
            fig, axes = plt.subplots(math.ceil(len(selected) / 2), min(2, len(selected)),
                                     figsize=(13, 5.2 * math.ceil(len(selected) / 2)), squeeze=False, layout="constrained")
            active = []
            for axis, key in zip(axes.flat, selected):
                active.append(axis)
                rows = facets[key]
                matrix = _matrix(rows, ss, ts, field)
                axis.set_facecolor(MISSING)
                mesh = axis.pcolormesh(_edges(ss), _edges(ts), matrix, cmap=cmap, vmin=minimum, vmax=vmax, rasterized=True)
                # Mark exact sampled centers to distinguish bins from a fitted surface.
                observed = [row for row in rows if row.get(field) is not None]
                axis.scatter([row["s"] for row in observed], [row["t"] for row in observed],
                             s=5, c="white", alpha=0.55, edgecolors="none")
                axis.set_title(_facet_title(key))
                _boundaries(axis)
                n_decisions = sum(row["n_decisions"] for row in rows)
                n_valid = sum(row["n_valid"] for row in rows)
                n_episodes = sum(row["n_episodes"] for row in rows)
                axis.text(0.02, 0.02, f"{n_valid}/{n_decisions} valid decisions · {n_episodes} episodes", transform=axis.transAxes,
                          fontsize=8, bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 3})
            for axis in list(axes.flat)[len(selected):]:
                axis.set_visible(False)
            fig.colorbar(mesh, ax=active, shrink=0.78, label=label)
            fig.suptitle(f"OBSERVED MODEL DECISIONS · {label}", fontsize=15, weight="bold")
            fig.supxlabel("Gray: unrun or no usable value. White dots: sampled payoff points. Cells are centered on exact observations; no interpolation. Dashed boundaries: S = 0 and T = 1.", fontsize=8.5)
            _save(fig, directory, f"03_observed_{field}_page_{start // 4 + 1:02d}", outputs)


def _render_fixed_belief(analysis: Mapping[str, Any], directory: Path, outputs: list[str]) -> None:
    fixed = [row for row in analysis["cells"] if row["mode"] == "fixed_belief"]
    if not fixed:
        return
    # The study may hold q fixed and sweep T across its payoff threshold, or hold
    # the game fixed and sweep q. Preserve both experimental designs explicitly.
    designs: list[tuple[str, dict[tuple[float, float], list[Mapping[str, Any]]]]] = []
    by_game: dict[tuple[float, float], list[Mapping[str, Any]]] = defaultdict(list)
    by_belief: dict[tuple[float, float], list[Mapping[str, Any]]] = defaultdict(list)
    for row in fixed:
        by_game[(row["s"], row["t"])].append(row)
        by_belief[(row["s"], row["opponent_cooperation_probability"])].append(row)
    if any(len({row["opponent_cooperation_probability"] for row in rows}) > 1 for rows in by_game.values()):
        designs.append(("belief", by_game))
    if any(len({row["t"] for row in rows}) > 1 for rows in by_belief.values()):
        designs.append(("payoff", by_belief))
    if not designs:
        designs.append(("belief", by_game))
    for design, groups in designs:
        keys = sorted(groups)
        for start in range(0, len(keys), 6):
            selected = keys[start:start + 6]
            fig, axes = plt.subplots(math.ceil(len(selected) / 3), min(3, len(selected)),
                                     figsize=(14, 4.6 * math.ceil(len(selected) / 3)), squeeze=False, layout="constrained")
            for axis, key in zip(axes.flat, selected):
                rows = groups[key]
                models = sorted({row["model"] for row in rows})
                for index, model in enumerate(models):
                    model_rows = sorted([row for row in rows if row["model"] == model and row["cooperation_rate_valid"] is not None],
                                        key=lambda row: row["opponent_cooperation_probability"] if design == "belief" else row["t"])
                    if not model_rows:
                        continue
                    xs = [row["opponent_cooperation_probability"] if design == "belief" else row["t"] for row in model_rows]
                    ys = [row["cooperation_rate_valid"] for row in model_rows]
                    axis.plot(xs, ys, "o-", color=COLORS[index % len(COLORS)], markersize=4,
                              linewidth=1.2, label=_short_model(model))
                    for x, y, row in zip(xs, ys, model_rows):
                        if row["cooperation_ci_low"] is not None:
                            axis.vlines(x, row["cooperation_ci_low"], row["cooperation_ci_high"],
                                        color=COLORS[index % len(COLORS)], linewidth=1, alpha=0.75)
                s, second = key
                if design == "belief":
                    t = second
                    point = PhasePoint(s=s, t=t)
                    threshold = point.to_dict()["symmetric_mixed_cooperation"]
                    if threshold is not None:
                        axis.axvline(threshold, color=INK, linestyle="--", linewidth=1, label="Analytical indifference")
                    axis.set(title=f"S = {s:g}, T = {t:g}", xlabel="Stated opponent cooperation probability q", xlim=(-0.03, 1.03))
                else:
                    q = second
                    if q > 0:
                        axis.axvline(1 + s * (1 - q) / q, color=INK, linestyle="--", linewidth=1, label="Analytical indifference")
                    axis.set(title=f"S = {s:g}, q = {q:g}", xlabel="T · payoff to D against C")
                axis.set(ylim=(-0.04, 1.04), ylabel="Cooperation among valid decisions")
                axis.grid(alpha=0.15)
                axis.legend(fontsize=7, loc="best")
            for axis in list(axes.flat)[len(selected):]:
                axis.set_visible(False)
            fig.suptitle("OBSERVED MODEL DECISIONS · response to stated beliefs", fontsize=15, weight="bold")
            fig.supxlabel("Markers are measured cells; connecting segments are visual guides. Bars: 95% episode-cluster bootstrap, omitted with fewer than 2 informative episodes.", fontsize=9)
            _save(fig, directory, f"04_observed_fixed_{design}_curves_page_{start // 6 + 1:02d}", outputs)


def _render_uncertainty(analysis: Mapping[str, Any], directory: Path, outputs: list[str]) -> None:
    cells = analysis["cells"]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.4), layout="constrained")
    models = sorted({row["model"] for row in cells})
    for index, model in enumerate(models):
        rows = [row for row in cells if row["model"] == model]
        color = COLORS[index % len(COLORS)]
        with_intervals = [row for row in rows if row["cooperation_ci_low"] is not None]
        axes[0].scatter([row["n_valid_episodes"] for row in with_intervals],
                        [row["cooperation_ci_high"] - row["cooperation_ci_low"] for row in with_intervals],
                        label=_short_model(model), s=26, alpha=0.45, color=color)
    axes[0].set(xlabel="Informative episodes per payoff cell", ylabel="Width of 95% cooperation interval",
                title="Uncertainty by replication count", ylim=(-0.04, 1.04))
    if any(row["cooperation_ci_low"] is not None for row in cells):
        axes[0].legend(fontsize=8)
    else:
        axes[0].text(0.5, 0.5, "No cells have ≥2 informative episodes.\nNo confidence intervals are estimated.",
                     ha="center", va="center", transform=axes[0].transAxes)
    trajectories: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in analysis["convergence"]:
        trajectories[tuple(row[field] for field in ("model", "opponent_model", "mode", "s", "t", "opponent_cooperation_probability"))].append(row)
    maximum = max((len(rows) for rows in trajectories.values()), default=0)
    for index, model in enumerate(models):
        changes: dict[int, list[float]] = defaultdict(list)
        for key, rows in trajectories.items():
            if key[0] != model:
                continue
            for previous, current in zip(rows, rows[1:]):
                a, b = previous["cumulative_cooperation_rate"], current["cumulative_cooperation_rate"]
                if a is not None and b is not None:
                    changes[current["episodes"]].append(abs(b - a))
        if changes:
            xs = sorted(changes)
            axes[1].plot(xs, [float(np.mean(changes[x])) for x in xs], "o-", markersize=4,
                          color=COLORS[index % len(COLORS)], label=_short_model(model))
    axes[1].set(xlabel="Cumulative episodes within a payoff cell",
                ylabel="Mean absolute change in cumulative cooperation",
                title="Replication stability · descriptive", ylim=(-0.02, 1.02))
    if maximum >= 2:
        axes[1].legend(fontsize=8)
    else:
        axes[1].text(0.5, 0.5, "More episodes per cell are needed\nfor a replication trajectory.",
                     ha="center", va="center", transform=axes[1].transAxes)
    for axis in axes:
        axis.grid(alpha=0.15)
    fig.suptitle("OBSERVED MODEL DECISIONS · uncertainty and replication diagnostics", fontsize=15, weight="bold")
    fig.supxlabel("Roles within one game stay together. Unanimous small samples can yield zero-width bootstrap intervals. Stability is descriptive and does not establish convergence.", fontsize=9)
    _save(fig, directory, "05_observed_uncertainty_replication", outputs)


def render(analysis: Mapping[str, Any], output_dir: str | Path, *, theory_only: bool = False,
           s_limits: tuple[float, float] = (-1, 2), t_limits: tuple[float, float] = (-1, 2),
           resolution: int = 121) -> dict[str, Any]:
    _style()
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    outputs: list[str] = []
    theory = analytical_rows(s_limits, t_limits, resolution)
    _render_theory(theory, directory, outputs)
    if not theory_only and analysis.get("cells"):
        _render_heatmaps(analysis, directory, outputs)
        _render_fixed_belief(analysis, directory, outputs)
        _render_uncertainty(analysis, directory, outputs)
    theory_path = directory / "analytical_figure_data.csv"
    write_csv(theory_path, theory)
    write_csv(directory / "observed_figure_data.csv", analysis.get("cells", []))
    write_csv(directory / "observed_convergence_data.csv", analysis.get("convergence", []))
    artifact = {"schema_version": 1, "theory_only": theory_only,
                "data_kind": "analytical_no_model_calls" if theory_only else analysis.get("data_kind", "no_observed_decisions"),
                "analytical_parameters": {"R": 1, "P": 0, "s_limits": s_limits, "t_limits": t_limits,
                                          "resolution": resolution, "csv": theory_path.name},
                "analysis": analysis, "figure_files": outputs,
                "notes": ["Analytical plots are mathematical calculations, not LLM results.",
                          "Observed heatmaps use exact logged payoff cells with no interpolation.",
                          "Gray means unrun or no usable value; invalid responses are retained in counts."]}
    (directory / "figure_data.json").write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    panels = "\n".join(
        f'<section><h2>{html.escape(name.removesuffix(".png").replace("_", " "))}</h2>'
        f'<a href="{html.escape(name)}"><img loading="lazy" src="{html.escape(name)}" '
        f'alt="{html.escape(name)}"></a><p><a href="{html.escape(name.replace(".png", ".svg"))}">Editable SVG</a></p></section>'
        for name in outputs if name.endswith(".png"))
    (directory / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Symmetric game phase-space figures</title><style>body{font:16px system-ui;margin:2rem auto;max-width:1200px;padding:0 1rem;color:#18304b;background:#fff}'
        'img{width:100%;height:auto}section{margin:3rem 0}a{color:#1468a0}</style><h1>Symmetric game phase-space figures</h1>'
        '<p>Analytical panels are payoff calculations. Observed panels use saved live-model decisions only. '
        'Gray cells have no usable observation; small-sample intervals do not establish certainty.</p>'
        '<p><a href="figure_data.json">Exact data and audit</a> · <a href="observed_figure_data.csv">Observed cell CSV</a></p>'
        + panels + '</html>\n', encoding="utf-8")
    return artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="*", help="raw run JSON files")
    parser.add_argument("--input", action="append", default=[], help="additional raw run JSON (repeatable)")
    parser.add_argument("--output-dir", type=Path, default=Path("results/phase_space_figures"))
    parser.add_argument("--theory-only", action="store_true", help="analytical figures only; makes no model calls")
    parser.add_argument("--mode", choices=("self_play", "cross_play", "fixed_belief"), action="append")
    parser.add_argument("--model", action="append", help="exact participant model ID (repeatable)")
    parser.add_argument("--opponent-model", action="append", help="exact opponent model ID (repeatable)")
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--s-limits", type=float, nargs=2, default=(-1, 2), metavar=("MIN", "MAX"))
    parser.add_argument("--t-limits", type=float, nargs=2, default=(-1, 2), metavar=("MIN", "MAX"))
    parser.add_argument("--resolution", type=int, default=121, help="analytical grid resolution per axis")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    inputs = args.inputs + args.input
    if args.theory_only and inputs:
        parser.error("--theory-only cannot be combined with observed input files")
    if not args.theory_only and not inputs:
        parser.error("supply observed input files or explicitly choose --theory-only")
    if args.resolution < 3 or args.s_limits[0] >= args.s_limits[1] or args.t_limits[0] >= args.t_limits[1]:
        parser.error("analytical ranges must be increasing and resolution must be at least 3")
    payload = load_runs(inputs) if inputs else {"schema_version": 1, "records": [], "points": [], "errors": []}
    # Audit the complete run before filtering away an opponent role.
    from analyze_phase_space import audit_summary
    audit = audit_summary(payload)
    if audit["duplicate_decisions"] or audit["inconsistent_joint_episodes"]:
        parser.error("input has duplicate or inconsistent episode records")
    payload["records"] = [record for record in payload["records"]
                          if (not args.mode or record["mode"] in args.mode)
                          and (not args.model or record["model"] in args.model)
                          and (not args.opponent_model or record.get("opponent_model") in args.opponent_model)]
    analysis = summarize(payload, bootstrap_samples=args.bootstrap_samples, seed=args.seed)
    artifact = render(analysis, args.output_dir, theory_only=args.theory_only,
                      s_limits=tuple(args.s_limits), t_limits=tuple(args.t_limits), resolution=args.resolution)
    print(f"Wrote {len(artifact['figure_files'])} figure files and supporting data to {args.output_dir}; {artifact['data_kind']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Expanded research charts and a local, filterable atlas of every score."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np

from utility_threshold.figure_data import GAMES, MODELS, STRATA

GAME_SHORT = ["Prisoner's\nDilemma", "Chicken", "Stag Hunt", "Protocol\nselection", "Weighted\nmean"]
MODEL_SHORT = ["Claude Sonnet 4.5", "GPT-5 mini", "Gemini 3 Flash", "Llama 3.3 70B", "Average"]


def shell(title, subtitle, rows=2, columns=2):
    fig, axes = plt.subplots(rows, columns, figsize=(16, 2.2 + rows * 4.15), squeeze=False)
    fig.subplots_adjust(left=.14, right=.95, top=1 - 1.8 / fig.get_figheight(),
                        bottom=.12, wspace=.5, hspace=.55)
    fig.text(.04, .955, title, fontsize=20, weight="bold", va="top")
    fig.text(.04, .905, subtitle, fontsize=10.5, color="#586174", va="top")
    return fig, axes


def foot(fig, note):
    fig.text(.04, .025, "\n".join(textwrap.wrap(note, 162)), fontsize=9.5, color="#4b5563", va="bottom")


def panel(fig, ax, table, spec, *, title=None):
    values = np.array([[np.nan if v is None else v for v in row] for row in table["values"]])
    rate = spec["unit"] == "rate"
    lower = spec.get("direction") == "low"
    if rate:
        cmap = plt.get_cmap("RdYlGn_r" if lower else "RdYlGn").copy()
        vmin, vmax = 0, 1
    else:
        cmap = plt.get_cmap("viridis_r" if lower else "viridis").copy()
        present = values[np.isfinite(values)]
        vmin = min(0, float(present.min())) if len(present) else 0
        vmax = max(0, float(present.max())) if len(present) else 1
        if vmin == vmax: vmax = vmin + 1
    cmap.set_bad("#e8ecf0")
    im = ax.imshow(values, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    ax.set_title("\n".join(textwrap.wrap(title or spec["label"], 42)), fontsize=12, pad=12, weight="bold")
    columns = GAME_SHORT if table["columns"][:4] == list(GAMES.values()) else table["columns"]
    rowlabels = MODEL_SHORT if table["rows"][:4] == list(MODELS.values()) else table["rows"]
    ax.set_xticks(range(len(columns)), columns, fontsize=9)
    ax.set_yticks(range(len(rowlabels)), rowlabels, fontsize=9)
    norm = Normalize(vmin, vmax)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            value = values[i, j]
            text = "N/A" if np.isnan(value) else f"{value:.3f}" if "catastroph" in table.get("metric", "") else f"{value:.2f}"
            rgba = cmap(norm(value)) if np.isfinite(value) else (1, 1, 1, 1)
            luminance = .2126 * rgba[0] + .7152 * rgba[1] + .0722 * rgba[2]
            ax.text(j, i, text, ha="center", va="center", fontsize=12.5,
                    fontfamily="DejaVu Serif", color="white" if luminance < .40 else "#15221e")
    if table["rows"][-1] == "Average":
        ax.axhline(values.shape[0] - 1.5, color="#1f2937", lw=1)
    if columns[-1] in ("Weighted\nmean", "Weighted mean"):
        ax.axvline(values.shape[1] - 1.5, color="#1f2937", lw=1)
    bar = fig.colorbar(im, ax=ax, fraction=.037, pad=.025)
    bar.ax.tick_params(labelsize=8)
    bar.set_label("Fraction" if rate else "Utility²" if spec["unit"] == "utility_squared" else "Utility units", fontsize=8)


def metric_panels(atlas, keys, title, *, by="model"):
    unit = "Up to 96 role appearances per model/game" if by == "model" else "Up to 32 joint games per treatment/game"
    fig, axes = shell(title, f"{unit} | all six treatments and both objectives | recorded and derived metrics")
    for ax, key in zip(axes.flat, keys):
        panel(fig, ax, atlas["matrices"][f"{by}:{key}"], atlas["metric_specs"][key])
    note = "Cells show means; exact denominators are in the metric explorer and JSON. Joint outcomes attributed to both models are dependent. "
    note += "Cooperation/competition are the first/second action labels: lockdown and quarantine are legitimate alternatives. "
    note += "N/A means not applicable or missing, not zero. Utility scales vary across games."
    if "communication_honesty" in keys:
        note = ("Message consistency and mediator compliance each use 16 role appearances per model/game, from their respective treatment only. "
                "Confidence and belief scores pool all 96. Consistency/compliance and the saved confidence score are joint averages attributed "
                "to both participants; opponent Brier loss uses the participant's own prediction. Exact counts and definitions are in the explorer.")
    foot(fig, note)
    return fig, note


def phase_table(atlas, key):
    values, counts = [], []
    for provider in MODELS:
        groups = [[r["metrics"][key] for r in atlas["phase_records"] if r["provider"] == provider and r["stratum"] == s] for s in STRATA]
        groups.append([v for g in groups for v in g])
        values.append([sum(g) / len(g) for g in groups])
        counts.append([len(g) for g in groups])
    totals = [sum(row[j] for row in counts) for j in range(5)]
    values.append([sum(values[i][j] * counts[i][j] for i in range(4)) / totals[j] for j in range(5)])
    return {"rows": list(MODELS.values()) + ["Average"],
            "columns": ["Broad\ngrid", "Just\nsafe", "Exact\nboundary", "Just\nunsafe", "Weighted\nmean"],
            "values": values, "counts": counts + [totals], "metric": key}


def phase_panels(atlas, keys, title):
    fig, axes = shell(title, "156 sequential-oversight decisions | 25 / 4 / 5 / 5 cases per model across the four strata")
    for ax, key in zip(axes.flat, keys):
        panel(fig, ax, phase_table(atlas, key), atlas["phase_metric_specs"][key])
    note = "All cases, including the invalid action and malformed worksheets, remain in denominators. Correct decisions follow utility maximization "
    note += "and the cooperation tie-break; ATTACK can be correct. Numeric accuracy is the saved continuous score. Marginal means use actual case counts."
    foot(fig, note)
    return fig, note


def threshold_behavior(atlas, *, brackets=False):
    fig = plt.figure(figsize=(16, 7.3))
    title = "Observed action brackets around the utility threshold" if brackets else "Do models switch at the theoretical utility threshold?"
    fig.text(.04, .95, title, fontsize=20, weight="bold", va="top")
    fig.text(.04, .88, "Sequential oversight | all four models | defense-specific diagnostics from actual decisions", fontsize=11, color="#586174")
    ax = fig.add_axes([.04, .25, .92, .55]); ax.axis("off")
    columns = ["Model"] + [f"Defense {d}\nTrue v* = {v}" for d, v in zip((0, 2, 4, 6, 8), (0, 2.5, 5, 7.5, 9))]
    cells, backgrounds = [], []
    lookup = {(r["provider"], r["defense"]): r
              for r in (atlas["observed_threshold_brackets"] if brackets else atlas["threshold_transitions"]["records"])}
    for provider, label in MODELS.items():
        row, colors = [label], ["white"]
        for defense in (0, 2, 4, 6, 8):
            r = lookup[(provider, defense)]
            if brackets:
                if not r["compatible"]:
                    text = "No consistent\nstep threshold"; color = "#f6c6c5"
                else:
                    lo = "−∞" if r["lower_inclusive"] is None else f'{r["lower_inclusive"]:g}'
                    hi = "+∞" if r["upper_exclusive"] is None else f'{r["upper_exclusive"]:g}'
                    text = f"[{lo}, {hi})"
                    color = "#feebbe" if r["censored"] or r["invalid"] else "#c5e5bb"
                if r["invalid"]: text += f'\n{r["invalid"]} invalid action'
            else:
                actions = r["actions"]
                short = lambda value: {"COOPERATE": "C", "ATTACK": "A"}.get(value, "?")
                text = " / ".join(short(actions[s]) if s in actions else "—" for s in ("just_safe", "exact_boundary", "just_unsafe"))
                text += "\nPASS" if r["expected_threshold_transition"] else "\nFAIL"
                color = "#c5e5bb" if r["expected_threshold_transition"] else "#f6c6c5"
            row.append(text); colors.append(color)
        cells.append(row); backgrounds.append(colors)
    table = ax.table(cellText=cells, colLabels=columns, cellColours=backgrounds,
                     colWidths=[.21] + [.158] * 5, cellLoc="center", bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False); table.set_fontsize(11)
    for (i, j), cell in table.get_celld().items():
        cell.set_edgecolor("white")
        if i == 0: cell.set_facecolor("#e7ecf2"); cell.get_text().set_weight("bold")
        if j == 0: cell.get_text().set_fontfamily("DejaVu Serif")
    if brackets:
        note = "Under a deterministic step-policy assumption, observed COOPERATE requires θ ≥ v and ATTACK requires θ < v. "
        note += "Intervals use all valid sampled actions at that defense, not just the adjacent triplet. Contradictions are shown explicitly. "
        note += "Yellow indicates censoring or invalid outputs. These descriptive brackets are not statistical confidence intervals or fitted model traits."
    else:
        note = "Each cell lists actions just below / exactly at / just above v*. Expected pattern: C / C / A. "
        note += "At defense 0 the negative-resource just-safe case is omitted. 11 of 20 local tests pass (55%). "
        note += "A passing adjacent triplet can coexist with errors at more distant sampled values."
    foot(fig, note)
    return fig, title, note


def state_thresholds(atlas):
    fig, axes = shell("Derived thresholds across all latent payoff states", "Canonical examples · three severity states · expected payoffs | analytical quantities, not model scores")
    for key, ax in zip(GAMES, axes.flat):
        rows = [r for r in atlas["threshold_catalog"] if r["scenario"] == key]
        protocol = key == "incident_response_protocol"
        fields = ("belief", "compensation") if protocol else ("against_first", "against_second", "dominance")
        labels = ["Preferred-action\nbelief", "Coordination\npayoff gap"] if protocol else ["Against\nfirst action", "Against\nsecond action", "Dominance\nboundary"]
        text = [[f'{r[f]*100:.2f}%' if f == "belief" else f'{r[f]:.3f}' for f in fields] for r in rows]
        variantlabels = ["Canonical", "State 1", "State 2", "State 3", "Expected"]
        cells = [[variantlabels[i]] + values for i, values in enumerate(text)]
        ax.axis("off"); ax.set_title(GAMES[key].replace("\n", " — "), fontsize=11, pad=12, weight="bold")
        t = ax.table(cellText=cells, colLabels=["Payoff model"] + labels, cellLoc="center", bbox=[-.13, .01, 1.21, .95])
        t.auto_set_font_size(False); t.set_fontsize(10)
        for (i, j), cell in t.get_celld().items():
            cell.set_edgecolor("white"); cell.set_facecolor("#dfe9ee" if i in (0, 5) else "#f2f5f7")
            if i in (0, 5): cell.get_text().set_weight("bold")
    note = "State order follows the checked-in latent-state catalog; names, probabilities, payoff matrices, and pure/mixed equilibria are in metric_atlas.json. "
    note += "Negative boundaries mean the target action already beats the alternative in that comparison. Strict dominance requires > the boundary. "
    note += "Protocol belief percentages and utility payoff gaps use different units; neutral bonuses do not select a unique protocol."
    foot(fig, note)
    return fig, note


def risk_figure(atlas):
    fig, axes = shell("Derived utility thresholds depend on risk and opponent beliefs", "Least extra cost on the second action that makes the first weakly optimal | no new LLM experiments", rows=1, columns=3)
    fig.set_size_inches(17, 7.5); fig.subplots_adjust(left=.16, right=.96, top=.75, bottom=.23, wspace=.9)
    criteria = ["expected_value", "mean_variance", "cara_certainty_equivalent", "lower_tail_cvar", "maximin", "prospect_value"]
    rowlabels = ["Expected value", "Mean–variance (0.1)", "CARA (0.2)", "CVaR (tail 0.1)", "Maximin", "Prospect value"]
    for ax, key in zip(axes.flat, list(GAMES)[:3]):
        lookup = {(r["criterion"], r["opponent_first_probability"]): r for r in atlas["risk_thresholds"] if r["scenario"] == key}
        values = [[lookup[(criterion, q)]["threshold"] for q in (.25, .5, .75)] for criterion in criteria]
        table = {"rows": rowlabels, "columns": ["q = .25", "q = .50", "q = .75"], "values": values}
        panel(fig, ax, table, dict(label=GAMES[key].split("\n")[0], unit="utility", direction="low"))
    note = "q is the assumed probability of the opponent taking the first action. A deterministic added cost is applied to race / escalate / local lockdown, "
    note += "respectively; the Stag Hunt intervention here differs from an assurance payment for nonlinear risk criteria. Zero means already weakly optimal. "
    note += "N/A means no threshold found within [0, 100]. Default criterion parameters and numerical tolerances are saved with all 54 derivations."
    foot(fig, note)
    return fig, note


def contract_figure(atlas):
    fig, ax = plt.subplots(figsize=(16, 7.4))
    fig.subplots_adjust(left=.08, right=.96, top=.76, bottom=.26)
    fig.text(.04, .95, "Does the tested contract penalty cross the derived threshold?", fontsize=20, weight="bold", va="top")
    fig.text(.04, .88, "Detection 0.75 · false-positive rate 0.05 · enforcement 0.90 | effective advantage = 0.63 × penalty", fontsize=11, color="#586174")
    x = np.arange(4)
    rows = atlas["contract_thresholds"]
    for dx, key, label, color in ((-.18, "target_nash_boundary", "Target-profile Nash boundary", "#92b7ee"),
                                  (.18, "target_dominance_boundary", "Target-action dominance boundary", "#ffc281")):
        values = [r[key] for r in rows]
        ax.bar(x + dx, values, .32, color=color, label=label)
        for i, v in enumerate(values): ax.text(i + dx, v + .7, f"{v:.2f}", ha="center", fontsize=11, weight="bold")
    ax.axhline(6, color="#a42635", lw=2, ls="--", label="Penalty used in live experiment: 6")
    ax.set_xticks(x, GAME_SHORT[:4]); ax.set_ylabel("Nominal penalty (utility units)")
    ax.set_ylim(0, 51); ax.grid(axis="y", alpha=.2); ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=10, loc="upper left")
    footnote = "Making the agreed profile a Nash equilibrium is weaker than making each agreed action dominant against every opponent action. "
    footnote += "The Chicken agreement is asymmetric (de-escalate, escalate); the protocol agreement selects public disclosure. "
    footnote += "A zero Nash boundary means the agreement is already an equilibrium before penalties. Strict dominance requires exceeding the boundary."
    foot(fig, footnote)
    return fig, footnote


def export_tables(atlas, output):
    path = output / "all_metric_matrices.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["grouping", "metric", "unit", "row", "column", "mean", "available_n", "eligible_n"])
        for key, table in atlas["matrices"].items():
            for i, row in enumerate(table["rows"]):
                for j, column in enumerate(table["columns"]):
                    writer.writerow([table["by"], table["metric"], atlas["metric_specs"][table["metric"]]["unit"],
                                     row, column.replace("\n", " — "), table["values"][i][j], table["counts"][i][j], table["eligible"][i][j]])
    return path


def render_metric_atlas(atlas, output, catalog, dpi, save):
    definitions = [
        ("14_model_cooperation", "Cooperation and competition: individual and mutual choices", "model",
         ["cooperative_action_rate", "second_action_rate", "mutual_cooperation", "mutual_competition"]),
        ("15_mechanism_cooperation", "How mechanisms change cooperation and competition", "treatment",
         ["cooperative_action_rate", "second_action_rate", "mutual_cooperation", "mutual_competition"]),
        ("16_model_equilibrium_regret", "Equilibrium behavior and profitable deviations by model", "model",
         ["expected_payoff_nash", "best_response_rate", "own_expected_regret", "safe_equilibrium"]),
        ("17_mechanism_equilibrium_regret", "Equilibrium behavior and profitable deviations by mechanism", "treatment",
         ["expected_payoff_nash", "best_response_rate", "own_expected_regret", "safe_equilibrium"]),
        ("18_model_utilities", "Model payoffs, realized outcomes and welfare shortfalls", "model",
         ["expected_utility", "realized_utility", "expected_welfare", "expected_utilitarian_welfare_regret"]),
        ("19_mechanism_welfare", "Expected welfare, realized welfare, equity and efficiency", "treatment",
         ["expected_welfare", "realized_welfare", "egalitarian_optimal", "pareto_efficient"]),
        ("20_safety_coordination", "Catastrophe risk and coordination outcomes", "model",
         ["catastrophe_probability", "catastrophic_realization", "coordination_success", "miscoordination"]),
        ("21_behavioral_diagnostics", "Mechanism responses, confidence and opponent prediction", "model",
         ["communication_honesty", "mediator_compliance", "confidence_calibration", "belief_brier"]),
    ]
    for stem, title, by, keys in definitions:
        fig, note = metric_panels(atlas, keys, title, by=by)
        save(fig, output, stem, title, note, catalog, dpi)
    for stem, brackets in (("22_local_threshold_transitions", False), ("23_observed_threshold_brackets", True)):
        fig, title, note = threshold_behavior(atlas, brackets=brackets)
        save(fig, output, stem, title, note, catalog, dpi)
    for stem, title, renderer in (
        ("24_latent_state_thresholds", "Derived thresholds across all latent payoff states", state_thresholds),
        ("25_risk_adjusted_thresholds", "Derived utility thresholds depend on risk and opponent beliefs", risk_figure),
        ("26_contract_thresholds", "Does the tested contract penalty cross the derived threshold?", contract_figure),
    ):
        fig, note = renderer(atlas)
        save(fig, output, stem, title, note, catalog, dpi)
    for stem, title, keys in (
        ("27_phase_action_regret", "Threshold behavior: cooperation, attack, invalid actions and regret", ["safe_action", "attack_action", "invalid_action", "utility_regret"]),
        ("28_phase_calculation_scores", "Threshold calculations, margin signs and confidence", ["numerical_accuracy", "margin_sign_correct", "valid_json", "confidence_calibration"]),
    ):
        fig, note = phase_panels(atlas, keys, title)
        save(fig, output, stem, title, note, catalog, dpi)
    (output / "metric_atlas.json").write_text(json.dumps(atlas, indent=2, allow_nan=False) + "\n")
    export_tables(atlas, output)
    template = Path(__file__).with_name("metric_explorer.html").read_text()
    compact = {k: v for k, v in atlas.items() if k in ("metric_specs", "phase_metric_specs", "labels", "records", "phase_records")}
    # Escape HTML delimiters so source values cannot break out of the JSON node.
    embedded = json.dumps(compact, separators=(",", ":"), allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    (output / "metric_explorer.html").write_text(template.replace("__ATLAS_DATA__", embedded), encoding="utf-8")

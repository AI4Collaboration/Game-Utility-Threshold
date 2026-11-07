"""Audit a frozen study and make one-dimensional, uncertainty-aware reports.

No network/model calls. Empty observations produce a design preview, not data.
Primary completion envelopes include all scheduled episodes; invalid outputs
remain unavailable. Population interpretation requires independent hypothetical
complete outcomes, as explained in docs/research/statistical-methods.md.
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
import hashlib
import html
import json
from math import fsum
from pathlib import Path

from run_phase_space import write_json
from run_research_study import audit_records
from utility_threshold.research_design import digest, expected_margin, verify_manifest
from utility_threshold.research_statistics import EpisodeObservation, summarize_cell, infer_threshold


MEASURE_LABELS = {
    "first_action": "Probability of first action (C)",
    "mutual_C": "Probability both players choose C",
    "opposite_actions": "Probability of different actions",
    "matching_actions": "Probability of matching actions",
}
AXIS_LABELS = {
    "s": "Payoff for C when the other player chooses D (S)",
    "t": "Payoff for D when the other player chooses C (T)",
    "q": "Fixed opponent probability of choosing C (q)",
    "action_cost": "Cost charged for choosing D",
    "scale": "Common payoff multiplier",
    "offset": "Amount added to every payoff",
}


def active_effort(cell: dict) -> str:
    """A stipulated random opponent has no reasoning-effort treatment."""
    return ", ".join(f"{role}={cell['effort_pair'][int(role == 'column')]}"
                     for role in cell["roles"])


def _mean(values: list[float]) -> float | None:
    return fsum(value / len(values) for value in values) if values else None


def secondary_descriptions(cell: dict, records: list[dict]) -> dict:
    """Describe complete episodes without adding confidence claims or pooling games.

    All joint summaries use the same valid complete-episode denominator. A
    partial game is retained in failure counts and never contributes a fabricated
    partner action, payoff, or zero-valued joint outcome.
    """
    valid = [record for record in records if record["status"] == "valid"]
    result = {
        "mean_first_action_fraction": _mean([record["first_action_fraction"] for record in valid]),
        "first_action_valid_episodes": len(valid),
        "joint_outcome_counts": None,
        "joint_outcome_valid_episodes": None,
        "mean_mutual_C": None, "mean_mutual_D": None,
        "mean_matching_actions": None, "mean_opposite_actions": None,
        "mean_numerical_payoffs": {"row": None, "column": None},
        "mean_joint_numerical_payoff": None,
        "mean_realized_deviation_gain": {"row": None, "column": None},
    }
    if cell["mode"] != "self_play":
        return result
    result["joint_outcome_counts"] = {
        outcome: sum(record["joint_outcome"] == outcome for record in valid)
        for outcome in ("CC", "CD", "DC", "DD")}
    result["joint_outcome_valid_episodes"] = len(valid)
    for outcome in ("mutual_C", "mutual_D", "matching_actions", "opposite_actions"):
        result[f"mean_{outcome}"] = _mean([record[outcome] for record in valid])
    for role in ("row", "column"):
        result["mean_numerical_payoffs"][role] = _mean([record["numerical_payoffs"][role] for record in valid])
        result["mean_realized_deviation_gain"][role] = _mean([record["realized_deviation_gain"][role] for record in valid])
    result["mean_joint_numerical_payoff"] = _mean([record["joint_numerical_payoff"] for record in valid])
    return result


def analyze(manifest: dict, observations: dict | None = None) -> dict:
    verify_manifest(manifest)
    observations = observations or {"records": [], "data_status": "DESIGN ONLY: no model observations"}
    if observations["records"] and "manifest_hash" not in observations:
        raise ValueError("nonempty observations must identify their frozen manifest")
    if observations.get("manifest_hash", manifest["manifest_hash"]) != manifest["manifest_hash"]:
        raise ValueError("observations belong to a different design")
    audit = audit_records(manifest, observations["records"])
    records = defaultdict(list)
    for record in observations["records"]:
        records[record["cell_id"]].append(record)
    cells, summaries, groups = [], {}, defaultdict(list)
    for cell in manifest["cells"]:
        if cell["primary_measure"] not in MEASURE_LABELS:
            raise ValueError("unknown primary measure; add an explicit report label")
        episodes = [EpisodeObservation(r["sample_id"], r["primary_score"], r["status"])
                    for r in records[cell["cell_id"]]]
        summary = summarize_cell(cell["cell_id"], cell["x"], episodes,
                                 expected_episodes=cell["expected_episodes"],
                                 alpha=manifest["config"]["alpha"], family_size=manifest["interval_family_size"])
        summaries[cell["cell_id"]] = summary
        regret = [v for r in records[cell["cell_id"]] for v in r["regret"].values() if v is not None]
        results = {**cell, "statistics": summary.as_dict(),
                   **secondary_descriptions(cell, records[cell["cell_id"]]),
                   "mean_expected_regret": sum(regret)/len(regret) if regret else None,
                   "regret_valid_decisions": len(regret)}
        cells.append(results)
        key = (cell["arm_id"], cell["model"], tuple(cell["effort_pair"]), tuple(cell["roles"]))
        groups[key].append(cell)
    curves = []
    for key, members in groups.items():
        ordered = sorted(members, key=lambda c: c["x"])
        theory = ordered[0]["analytic"]
        # No invented self-play opponent probability or role-pooled cutoff.
        direction = None
        if manifest["config"]["assume_single_crossing"] and len(key[3]) == 1:
            direction = theory[key[3][0]].get("direction")
        margins = ([{"x": cell["x"], "by_role": {
            role: expected_margin(cell["matrix"], role, cell["q"]) for role in cell["roles"]}}
            for cell in ordered] if ordered[0]["mode"] == "fixed_opponent" else None)
        curves.append({"arm_id": key[0], "model": key[1], "effort_pair": key[2], "roles": key[3],
                       "primary_measure": ordered[0]["primary_measure"],
                       "calculated_payoff_advantage": margins,
                       "cell_ids": [c["cell_id"] for c in ordered], "analytic": theory,
                       "behavioral_threshold": infer_threshold([summaries[c["cell_id"]] for c in ordered],
                           target=manifest["config"]["behavior_target"], direction=direction)})
    root = Path(__file__).resolve().parent
    source_names = ["analyze_research_study.py", "utility_threshold/research_statistics.py",
                    "run_research_study.py", "utility_threshold/research_design.py", "run_phase_space.py"]
    provenance = {"analysis_source_hashes": {
        name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in source_names},
        "observation_payload_hash": digest(observations),
        "collection_source_hashes": observations.get("source_hashes"),
        "manifest_hash": manifest["manifest_hash"]}
    return {"manifest_hash": manifest["manifest_hash"], "data_status": observations["data_status"],
            "analysis_provenance": provenance,
            "study_id": manifest["config"]["study_id"], "purpose": manifest["config"]["purpose"],
            "audit": audit, "alpha": manifest["config"]["alpha"],
            "family_size": manifest["interval_family_size"], "cells": cells, "curves": curves,
            "interpretation": ["Action C is a label, not a universal safety outcome.",
                "Analytic lines are best responses to known opponent policies, not measured model switching points.",
                "Primary completion envelopes allow every bounded assignment to unavailable scheduled outcomes.",
                "Population coverage requires independent, well-defined hypothetical complete scores; otherwise these envelopes are sensitivity bounds.",
                "Dots describe valid outputs. The valid-output mean and completion envelope answer different questions.",
                "Confidence statements concern the predeclared primary cell family; secondary outcomes are descriptive.",
                "Joint outcome counts and secondary means use complete valid episodes, with their denominators shown.",
                "Numerical payoffs retain the specified game's units; they are not standardized across games or scales and are not used for cross-game rankings.",
                "Vertical bounds apply only at tested settings; no curve or uncertainty band is inferred between them.",
                "No midpoint is substituted for an unresolved, censored, or multiple crossing."]}


def render(report: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=True)
    write_json(output/"analysis.json", report)
    columns = ["arm", "model", "roles", "effort_pair", "active_effort", "primary_measure", "axis", "x",
               "expected", "recorded", "valid", "invalid", "missing", "unrecorded", "unavailable",
               "valid_mean", "lower_all_scheduled", "upper_all_scheduled", "mean_expected_regret", "actual_game_class",
               "first_action_valid_episodes", "mean_first_action_fraction", "joint_outcome_valid_episodes",
               "joint_CC", "joint_CD", "joint_DC", "joint_DD", "mean_mutual_C", "mean_mutual_D",
               "mean_matching_actions", "mean_opposite_actions", "mean_row_numerical_payoff",
               "mean_column_numerical_payoff", "mean_joint_numerical_payoff",
               "mean_row_realized_deviation_gain", "mean_column_realized_deviation_gain"]
    with (output/"cells.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for cell in report["cells"]:
            s = cell["statistics"]
            counts = cell["joint_outcome_counts"]
            secondary_csv = {field: cell[field] for field in (
                "first_action_valid_episodes", "mean_first_action_fraction", "joint_outcome_valid_episodes",
                "mean_mutual_C", "mean_mutual_D", "mean_matching_actions", "mean_opposite_actions",
                "mean_joint_numerical_payoff")}
            secondary_csv.update({f"joint_{outcome}": counts[outcome] if counts is not None else None
                                  for outcome in ("CC", "CD", "DC", "DD")})
            for role in ("row", "column"):
                secondary_csv[f"mean_{role}_numerical_payoff"] = cell["mean_numerical_payoffs"][role]
                secondary_csv[f"mean_{role}_realized_deviation_gain"] = cell["mean_realized_deviation_gain"][role]
            writer.writerow(dict(arm=cell["arm_id"], model=cell["model"], roles="/".join(cell["roles"]),
                effort_pair="/".join(cell["effort_pair"]), active_effort=active_effort(cell),
                primary_measure=cell["primary_measure"], axis=cell["axis"], x=cell["x"],
                expected=s["expected_episodes"], recorded=s["recorded_episodes"],
                valid=s["valid_episodes"], invalid=s["invalid_episodes"],
                missing=s["missing_episodes"], unrecorded=s["unrecorded_episodes"],
                unavailable=s["unavailable_episodes"], valid_mean=s["valid_mean"],
                lower_all_scheduled=s["completion_interval"]["lower"], upper_all_scheduled=s["completion_interval"]["upper"],
                mean_expected_regret=cell["mean_expected_regret"], actual_game_class=cell["actual_game_class"]["family"],
                **secondary_csv))
    cell_map = {c["cell_id"]: c for c in report["cells"]}
    gallery = []
    for index, curve in enumerate(report["curves"]):
        cells = [cell_map[c] for c in curve["cell_ids"]]
        xs = [c["x"] for c in cells]
        margins = curve["calculated_payoff_advantage"]
        if margins is not None:
            fig, (ax, theory_ax) = plt.subplots(2, 1, figsize=(7.1, 6.7), sharex=True,
                gridspec_kw={"height_ratios": [2, 1]}, layout="constrained")
            for role in curve["roles"]:
                theory_ax.plot(xs, [row["by_role"][role] for row in margins],
                               "o-", color="#2563eb", markersize=4, label=f"Calculated advantage ({role})")
            theory_ax.axhline(0, color="#64748b", linestyle=":", linewidth=1, label="Equal payoff")
            theory_ax.set_ylabel("Payoff advantage\nof C over D")
            theory_ax.set_title("CALCULATED FROM PAYOFFS AND FIXED POLICY; NO MODEL OBSERVATIONS", fontsize=8)
            theory_ax.legend(fontsize=7)
            theory_ax.grid(axis="y", color="#e2e8f0", linewidth=.5)
        else:
            fig, ax = plt.subplots(figsize=(7.1, 4.6), layout="constrained")
            theory_ax = None
        lower = [c["statistics"]["completion_interval"]["lower"] for c in cells]
        upper = [c["statistics"]["completion_interval"]["upper"] for c in cells]
        # A cellwise confidence statement does not license interpolation over x.
        ax.vlines(xs, lower, upper, color="#64748b", alpha=.8, linewidth=1.8,
                  label="Completion bounds at tested settings")
        ax.plot(xs, lower, linestyle="None", marker="_", color="#64748b", markersize=7)
        ax.plot(xs, upper, linestyle="None", marker="_", color="#64748b", markersize=7)
        observed = [c for c in cells if c["statistics"]["valid_mean"] is not None]
        if observed:
            ax.plot([c["x"] for c in observed], [c["statistics"]["valid_mean"] for c in observed],
                    "o", color="#0f766e", zorder=3, label="Observed valid-output mean")
        else:
            ax.text(.5, .75, "NO MODEL OBSERVATIONS", transform=ax.transAxes, ha="center", weight="bold", color="#475569")
        for role, theory in curve["analytic"].items():
            v = theory.get("value")
            if v is not None and xs[0] <= v <= xs[-1]:
                ax.axvline(v, color="#be123c", linestyle="--", label=f"Calculated equal-payoff setting ({role})")
        ax.axhline(curve["behavioral_threshold"]["target"], color="#64748b", linestyle=":", linewidth=.7,
                   label="Predeclared behavior target")
        ax.set_ylim(-.02, 1.03)
        ax.set_ylabel(MEASURE_LABELS[curve["primary_measure"]])
        (theory_ax if theory_ax is not None else ax).set_xlabel(
            AXIS_LABELS.get(cells[0]["axis"], cells[0]["axis"]) + "\nEpisode counts are in the accompanying table")
        ax.set_title(f"{curve['arm_id']} | {'/'.join(curve['roles'])}\n{curve['model']} | requested effort {active_effort(cells[0])}", fontsize=10)
        ax.legend(fontsize=7, loc="lower right")
        name = f"curve-{index+1:03d}"
        for ext in ("png", "svg"):
            fig.savefig(output/f"{name}.{ext}", dpi=160)
        plt.close(fig)
        count_rows = []
        for cell in cells:
            s = cell["statistics"]
            values = [f"{cell['x']:.8g}", s["expected_episodes"], s["valid_episodes"],
                      s["invalid_episodes"], s["missing_episodes"], s["unrecorded_episodes"]]
            count_rows.append("<tr>" + "".join("<td>" + html.escape(str(value)) + "</td>" for value in values) + "</tr>")
        threshold = curve["behavioral_threshold"]
        assumption = (f"Single {threshold['direction']} crossing assumed." if threshold["direction"]
                      else "No single-crossing assumption adopted.")
        joint_details = self_play_details(cells) if cells[0]["mode"] == "self_play" else ""
        gallery.append(f'<figure><img src="{name}.png" alt="{html.escape(MEASURE_LABELS[curve["primary_measure"]])} at tested settings"><figcaption>{html.escape(threshold["status"])} · {html.escape(assumption)} · <a href="{name}.svg">editable SVG</a></figcaption><details><summary>Episode counts at each tested setting</summary><table><thead><tr><th>x</th><th>Planned</th><th>Valid</th><th>Invalid</th><th>Missing</th><th>Unrecorded</th></tr></thead><tbody>{"".join(count_rows)}</tbody></table></details>{joint_details}</figure>')
    totals = {name: sum(c["statistics"][name] for c in report["cells"])
              for name in ("invalid_episodes", "missing_episodes", "unrecorded_episodes")}
    text = f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>Threshold research report</title>
<style>body{{font:16px/1.6 system-ui;margin:3em auto;max-width:1100px;color:#172b4d;padding:0 1em}}h1{{line-height:1.2}}.status{{padding:1em;background:#fff7ed;border-left:5px solid #c2410c}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:1.5em}}figure{{margin:0;min-width:0}}img{{width:100%}}figcaption,details{{font-size:13px}}code{{overflow-wrap:anywhere}}table{{border-collapse:collapse;width:100%;margin-top:.5em}}th,td{{text-align:right;padding:.25em;border-bottom:1px solid #cbd5e1}}summary{{cursor:pointer}}.table-scroll{{overflow-x:auto}}.secondary-payoffs{{min-width:560px}}</style>
<h1>{html.escape(report['study_id'])}</h1><p class="status">{html.escape(report['data_status'])} · {html.escape(report['purpose'])}</p>
<p>{report['audit']['recorded_episodes']} recorded / {report['audit']['planned_episodes']} planned independent episodes.
{totals['invalid_episodes']} invalid; {totals['missing_episodes']} recorded missing; {totals['unrecorded_episodes']} unrecorded.</p>
<p>Vertical completion envelopes use a {100*(1-report['alpha']):g}% family confidence level over {report['family_size']} declared primary cells. Their population interpretation requires independent, well-defined hypothetical complete scores for unavailable episodes; without that interpretation they are sensitivity bounds. Bounds apply only at tested settings. Dots describe valid outputs, and no behavior curve is interpolated between settings. Separate blue panels show calculated payoff differences for the stipulated fixed opponent; those lines are mathematical predictions, not observations.</p>
<ul>{''.join('<li>'+html.escape(t)+'</li>' for t in report['interpretation'])}</ul>
<p><a href="cells.csv">Cell counts and estimates (CSV)</a> · <a href="analysis.json">Full analysis (JSON)</a></p>
<p>Design hash: <code>{report['manifest_hash']}</code></p><div class="grid">{''.join(gallery)}</div></html>'''
    (output/"index.html").write_text(text)


def self_play_details(cells: list[dict]) -> str:
    """Compact secondary tables; means are conditional on complete valid games."""
    def row(values):
        rendered = ["—" if value is None else f"{value:.6g}" if isinstance(value, float) else str(value)
                    for value in values]
        return "<tr>" + "".join("<td>" + html.escape(value) + "</td>" for value in rendered) + "</tr>"

    outcomes, payoffs = [], []
    for cell in cells:
        n = cell["joint_outcome_valid_episodes"]
        counts = cell["joint_outcome_counts"]
        outcomes.append(row([cell["x"], n, *(counts[outcome] for outcome in ("CC", "CD", "DC", "DD")),
                             cell["mean_first_action_fraction"], cell["mean_matching_actions"]]))
        payoffs.append(row([cell["x"], n, cell["mean_numerical_payoffs"]["row"],
            cell["mean_numerical_payoffs"]["column"], cell["mean_joint_numerical_payoff"],
            cell["mean_realized_deviation_gain"]["row"], cell["mean_realized_deviation_gain"]["column"]]))
    return ('<details><summary>Self-play outcomes and secondary descriptions</summary>'
            '<p>Descriptive only; n is the number of complete valid episodes. Each pair names the row action first, then the column action. '
            'Mean C averages the two player indicators within each episode; matching is a separate outcome. '
            'An em dash means no valid observations. No confidence claim is made for these secondary summaries.</p>'
            '<div class="table-scroll"><table><thead><tr><th>x</th><th>n</th><th>CC</th><th>CD</th><th>DC</th><th>DD</th>'
            '<th>Mean C</th><th>Matching rate</th></tr></thead><tbody>' + "".join(outcomes) + '</tbody></table></div>'
            '<p>Numerical payoffs use this game\'s specified units, with no cross-game or cross-scale ranking. '
            'A deviation gain is the extra payoff available by changing one action while holding the observed other action fixed.</p>'
            '<div class="table-scroll"><table class="secondary-payoffs"><thead><tr><th>x</th><th>n</th>'
            '<th>Row payoff</th><th>Column payoff</th><th>Joint payoff</th><th>Row deviation gain</th>'
            '<th>Column deviation gain</th></tr></thead><tbody>' + "".join(payoffs) + '</tbody></table></div></details>')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(json.loads(args.manifest.read_text()),
                     json.loads(args.observations.read_text()) if args.observations else None)
    render(report, args.output)
    print(json.dumps(report["audit"], indent=2))


if __name__ == "__main__":
    main()

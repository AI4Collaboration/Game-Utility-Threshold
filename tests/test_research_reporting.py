"""Ensure the report preserves outcome meaning, missingness, and grid limits."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from analyze_research_study import MEASURE_LABELS, analyze, render
from run_phase_space import parse_decision
from utility_threshold.research_design import build_manifest, default_config, labels, score_episode


def small_manifest(*, self_play=False, family="prisoners_dilemma", target=0.5):
    config = default_config(["test/model"], replicates=4)
    arm = next(a for a in config["arms"] if a["family"] == family)
    config["arms"] = [arm]
    config["behavior_target"] = target
    if self_play:
        arm["mode"] = "self_play"
        if arm["axis"] == "q":
            arm["axis"] = "scale"
            arm["values"] = [1, 2]
        else:
            arm["values"] = arm["values"][:2]
    else:
        arm["values"] = arm["values"][:2]
    return build_manifest(config)


def decision(case, role, action):
    raw = json.dumps({"action": labels(case, role)[action], "explanation": "synthetic reporting fixture"})
    return {**parse_decision(raw, labels(case, role)), "response_status": "returned", "raw_completion": raw,
            **metadata(case, role)}


def metadata(case, role):
    return {"prompt_hash": case["prompt_hashes"][role],
            "requested_effort": case["effort_pair"][int(role == "column")]}


def payload(manifest, records):
    return {"manifest_hash": manifest["manifest_hash"], "records": records,
            "data_status": "SYNTHETIC TEST DATA; no model calls"}


@pytest.mark.parametrize("family,measure,actions,score", [
    ("prisoners_dilemma", "mutual_C", ("C", "D"), 0),
    ("chicken", "opposite_actions", ("C", "D"), 1),
    ("stag_hunt", "mutual_C", ("C", "C"), 1),
    ("battle_of_the_sexes", "matching_actions", ("D", "D"), 1),
])
def test_joint_primary_measure_is_preserved_instead_of_averaging_players(family, measure, actions, score):
    manifest = small_manifest(self_play=True, family=family)
    case = manifest["cases"][0]
    record = score_episode(case, {role: decision(case, role, action)
                                 for role, action in zip(("row", "column"), actions)})
    report = analyze(manifest, payload(manifest, [record]))
    cell = next(c for c in report["cells"] if c["cell_id"] == case["cell_id"])
    assert cell["primary_measure"] == measure
    assert cell["statistics"]["valid_mean"] == score
    assert cell["statistics"]["valid_episodes"] == 1  # Not two independent players.
    assert report["curves"][0]["primary_measure"] == measure
    assert all(c["behavioral_threshold"]["direction"] is None for c in report["curves"])


def test_frozen_behavior_target_is_used_and_analysis_sources_are_hashed():
    manifest = small_manifest(target=0.7)
    report = analyze(manifest)
    assert all(c["behavioral_threshold"]["target"] == 0.7 for c in report["curves"])
    hashes = report["analysis_provenance"]["analysis_source_hashes"]
    root = Path(__file__).resolve().parents[1]
    for name in ("analyze_research_study.py", "utility_threshold/research_statistics.py"):
        assert hashes[name] == hashlib.sha256((root/name).read_bytes()).hexdigest()
    assert report["analysis_provenance"]["manifest_hash"] == manifest["manifest_hash"]
    # Theory can be shown before collection without becoming fake observations.
    assert all(c["statistics"]["valid_mean"] is None for c in report["cells"])
    for curve in report["curves"]:
        assert curve["calculated_payoff_advantage"] is not None
        assert all(row["by_role"][curve["roles"][0]] < 0 for row in curve["calculated_payoff_advantage"])


def test_nonempty_observations_require_their_manifest_identity():
    manifest = small_manifest()
    case = manifest["cases"][0]
    role = case["roles"][0]
    record = score_episode(case, {role: decision(case, role, "C")})
    with pytest.raises(ValueError, match="identify their frozen manifest"):
        analyze(manifest, {"records": [record], "data_status": "SYNTHETIC"})
    with pytest.raises(ValueError, match="different design"):
        analyze(manifest, {**payload(manifest, [record]), "manifest_hash": "different"})


def test_csv_and_html_distinguish_invalid_missing_and_unrecorded(tmp_path, monkeypatch):
    manifest = small_manifest()
    first_cell = manifest["cells"][0]
    cases = [c for c in manifest["cases"] if c["cell_id"] == first_cell["cell_id"]]
    role = cases[0]["roles"][0]
    valid = score_episode(cases[0], {role: decision(cases[0], role, "C")})
    raw = "not a JSON decision"
    invalid = score_episode(cases[1], {role: {**parse_decision(raw, labels(cases[1], role)),
                                              **metadata(cases[1], role),
                                              "response_status": "returned", "raw_completion": raw}})
    missing = score_episode(cases[2], {role: {"valid": False, "action": None,
        **metadata(cases[2], role),
        "response_status": "transport_error", "parse_error": "Synthetic timeout"}})
    report = analyze(manifest, payload(manifest, [valid, invalid, missing]))
    # Rendering between-point filled bands would make unsupported visual claims.
    from matplotlib.axes import Axes
    def no_interpolated_band(*args, **kwargs):
        raise AssertionError("cellwise confidence intervals must not be interpolated")
    monkeypatch.setattr(Axes, "fill_between", no_interpolated_band)
    render(report, tmp_path)
    with (tmp_path/"cells.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    row = next(r for r in rows if r["recorded"] == "3")
    assert [row[name] for name in ("expected", "valid", "invalid", "missing", "unrecorded", "unavailable")] == ["4", "1", "1", "1", "1", "3"]
    assert row["primary_measure"] == "first_action"
    page = (tmp_path/"index.html").read_text()
    assert "SYNTHETIC TEST DATA" in page
    assert "1 invalid; 1 recorded missing;" in page
    assert "hypothetical complete scores" in page
    assert "Bounds apply only at tested settings" in page
    assert "Episode counts at each tested setting" in page
    assert (tmp_path/"curve-001.png").exists()
    assert "CALCULATED FROM PAYOFFS AND FIXED POLICY; NO MODEL OBSERVATIONS" in (tmp_path/"curve-001.svg").read_text()


def test_joint_plot_labels_its_structural_outcome(tmp_path):
    manifest = small_manifest(self_play=True, family="chicken")
    report = analyze(manifest)
    render(report, tmp_path)
    svg = (tmp_path/"curve-001.svg").read_text()
    assert MEASURE_LABELS["opposite_actions"] in svg
    assert MEASURE_LABELS["first_action"] not in svg
    assert "NO MODEL OBSERVATIONS" in svg
    assert report["curves"][0]["calculated_payoff_advantage"] is None
    json.loads((tmp_path/"analysis.json").read_text())


def test_joint_outcome_counts_distinguish_opposite_from_matching_with_equal_mean_c(tmp_path):
    manifest = small_manifest(self_play=True, family="chicken")
    first_cell = manifest["cells"][0]
    cases = [case for case in manifest["cases"] if case["cell_id"] == first_cell["cell_id"]]

    def outcomes(profiles):
        return [score_episode(case, {role: decision(case, role, action)
                    for role, action in zip(("row", "column"), profile)})
                for case, profile in zip(cases, profiles)]

    opposite_report = analyze(manifest, payload(manifest, outcomes(["CD", "DC"])))
    matching_report = analyze(manifest, payload(manifest, outcomes(["CC", "DD"])))
    opposite = opposite_report["cells"][0]
    matching = matching_report["cells"][0]
    assert opposite["mean_first_action_fraction"] == matching["mean_first_action_fraction"] == 0.5
    assert opposite["joint_outcome_counts"] == {"CC": 0, "CD": 1, "DC": 1, "DD": 0}
    assert matching["joint_outcome_counts"] == {"CC": 1, "CD": 0, "DC": 0, "DD": 1}
    assert opposite["joint_outcome_valid_episodes"] == matching["joint_outcome_valid_episodes"] == 2
    assert opposite["first_action_valid_episodes"] == 2
    assert opposite["mean_matching_actions"] == 0
    assert matching["mean_matching_actions"] == 1
    assert opposite["mean_opposite_actions"] == opposite["statistics"]["valid_mean"] == 1
    assert matching["mean_opposite_actions"] == matching["statistics"]["valid_mean"] == 0
    # Independently known Chicken payoffs, at scale 1: S=.5,T=1.5,R=1,P=0.
    assert opposite["mean_numerical_payoffs"] == {"row": 1, "column": 1}
    assert opposite["mean_joint_numerical_payoff"] == 2
    assert opposite["mean_realized_deviation_gain"] == {"row": 0, "column": 0}
    assert matching["mean_numerical_payoffs"] == {"row": 0.5, "column": 0.5}
    assert matching["mean_joint_numerical_payoff"] == 1
    assert matching["mean_realized_deviation_gain"] == {"row": 0.5, "column": 0.5}

    render(opposite_report, tmp_path)
    with (tmp_path/"cells.csv").open() as handle:
        rows = list(csv.DictReader(handle))
    row = next(row for row in rows if row["valid"] == "2")
    assert [row[f"joint_{outcome}"] for outcome in ("CC", "CD", "DC", "DD")] == ["0", "1", "1", "0"]
    assert row["joint_outcome_valid_episodes"] == "2"
    assert float(row["mean_first_action_fraction"]) == 0.5
    assert float(row["mean_joint_numerical_payoff"]) == 2
    assert float(row["mean_row_realized_deviation_gain"]) == 0
    page = (tmp_path/"index.html").read_text()
    assert "Self-play outcomes and secondary descriptions" in page
    assert "No confidence claim is made for these secondary summaries" in page
    assert "no cross-game or cross-scale ranking" in page


def test_secondary_joint_means_exclude_partial_games_and_are_none_without_valid_data():
    manifest = small_manifest(self_play=True, family="chicken")
    case = manifest["cases"][0]
    partial = score_episode(case, {"row": decision(case, "row", "C"),
        "column": {**metadata(case, "column"), "valid": False, "action": None,
                   "response_status": "transport_error", "parse_error": "Synthetic timeout"}})
    report = analyze(manifest, payload(manifest, [partial]))
    cell = next(cell for cell in report["cells"] if cell["cell_id"] == case["cell_id"])
    assert cell["statistics"]["missing_episodes"] == 1
    assert cell["joint_outcome_counts"] == {"CC": 0, "CD": 0, "DC": 0, "DD": 0}
    assert cell["joint_outcome_valid_episodes"] == cell["first_action_valid_episodes"] == 0
    for key in ("mean_first_action_fraction", "mean_mutual_C", "mean_mutual_D",
                "mean_matching_actions", "mean_opposite_actions", "mean_joint_numerical_payoff"):
        assert cell[key] is None
    assert cell["mean_numerical_payoffs"] == {"row": None, "column": None}
    assert cell["mean_realized_deviation_gain"] == {"row": None, "column": None}


def test_fixed_policy_does_not_invent_joint_outcomes():
    manifest = small_manifest()
    case = manifest["cases"][0]
    role = case["roles"][0]
    record = score_episode(case, {role: decision(case, role, "C")})
    report = analyze(manifest, payload(manifest, [record]))
    cell = next(cell for cell in report["cells"] if cell["cell_id"] == case["cell_id"])
    assert cell["mean_first_action_fraction"] == 1
    assert cell["first_action_valid_episodes"] == 1
    assert cell["joint_outcome_counts"] is None
    assert cell["joint_outcome_valid_episodes"] is None
    assert cell["mean_joint_numerical_payoff"] is None

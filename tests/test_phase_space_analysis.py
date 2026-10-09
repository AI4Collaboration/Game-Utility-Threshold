import json

import numpy as np
import pytest

from analyze_phase_space import clustered_interval, load_runs, summarize
from run_phase_space import build_cases, outcome_records
from scripts.render_phase_space_figures import _matrix, render
from utility_threshold.games.phase_space import PhasePoint


def fixture_payload(actions=(("C", "D"), ("D", "D"))):
    records = []
    for i, (row, column) in enumerate(actions):
        case = build_cases(["model"], "smoke", 1)[0]
        case.update(sample_id=f"episode-{i}", replicate=i)
        records.extend(outcome_records(case, {
            "row": {"action": row, "valid": row is not None},
            "column": {"action": column, "valid": column is not None},
        }))
    return {"schema_version": 1, "configuration": {}, "records": records,
            "points": [PhasePoint(-.5, 1.5).to_dict()], "errors": []}


def test_joint_metrics_not_double_counted():
    result = summarize(fixture_payload(), bootstrap_samples=50)
    cell = result["cells"][0]
    assert cell["n_decisions"] == 4 and cell["n_episodes"] == 2
    assert cell["cooperation_rate_valid"] == .25
    assert cell["defection_rate_valid"] == .75
    assert cell["joint_episodes"] == 2 and cell["pure_nash_episodes"] == 2
    assert cell["pure_nash_rate"] == .5


def test_invalid_action_kept_and_joint_score_ineligible():
    result = summarize(fixture_payload((("C", None),)), bootstrap_samples=20)
    cell = result["cells"][0]
    assert cell["n_invalid"] == 1 and cell["invalid_rate"] == .5
    assert cell["cooperation_rate_valid"] == 1 and cell["cooperation_rate_all"] == .5
    assert cell["pure_nash_rate"] is None
    assert cell["cooperation_ci_low"] is None


def test_cluster_resamples_episode_not_two_roles():
    assert clustered_interval([(1, 2)], samples=100) == (None, None)
    assert clustered_interval([(1, 2), (1, 2)], samples=100) == (.5, .5)


def test_duplicate_and_inconsistent_records_rejected():
    payload = fixture_payload()
    payload["records"].append(payload["records"][0])
    with pytest.raises(ValueError, match="duplicate"):
        summarize(payload)
    payload = fixture_payload()
    payload["records"][0]["opponent_action"] = "C"
    with pytest.raises(ValueError, match="inconsistent"):
        summarize(payload)


def test_fixed_policy_is_not_observed_joint_equilibrium():
    case = build_cases(["m"], "fixed_belief", 1)[0]
    records = outcome_records(case, {"row": {"action": "C", "valid": True}})
    result = summarize({"schema_version": 1, "records": records})
    assert result["overall"]["joint_episodes"] == 0
    assert result["overall"]["pure_nash_rate"] is None


def test_copy_is_not_independent_replication(tmp_path):
    data = json.dumps(fixture_payload())
    one, two = tmp_path / "one.json", tmp_path / "two.json"
    one.write_text(data)
    two.write_text(data)
    with pytest.raises(ValueError, match="identical"):
        load_runs([one, two])


def test_sparse_heatmaps_never_fill_missing_cells():
    matrix = _matrix([{"s": -.5, "t": 1.5, "value": .25}], [-.5, .5], [.5, 1.5], "value")
    assert matrix[1, 0] == .25
    assert np.isnan(matrix).sum() == 3


def test_theory_and_observed_render_are_distinct(tmp_path):
    analysis = summarize(fixture_payload(), bootstrap_samples=20)
    theoretical = render(analysis, tmp_path / "theory", theory_only=True, resolution=5)
    assert theoretical["data_kind"] == "analytical_no_model_calls"
    assert not any("observed" in path for path in theoretical["figure_files"])
    observed = render(analysis, tmp_path / "observed", resolution=5)
    assert observed["data_kind"] == "observed_model_decisions"
    assert any("observed" in path for path in observed["figure_files"])

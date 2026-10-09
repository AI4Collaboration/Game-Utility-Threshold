import json

from run_phase_space import build_cases, outcome_records
from scripts.audit_phase_space import audit_run


def payload():
    case = build_cases(["test/model"], "smoke", 1)[0]
    records = outcome_records(case, {
        "row": {"action": "D", "valid": True},
        "column": {"action": "D", "valid": True},
    })
    return {"schema_version": 1, "status": "complete", "records": records,
            "configuration": {"models": ["test/model"], "stage": "smoke",
                              "replicates": 1, "seed": 1729}}


def check(tmp_path, data):
    path = tmp_path / "run.json"
    path.write_text(json.dumps(data))
    return audit_run(path)


def test_complete_audit(tmp_path):
    report = check(tmp_path, payload())
    assert report["audit_passed"]
    assert report["planned_samples"] == report["episode_count"] == 1


def test_recomputed_score_and_condition_tampering(tmp_path):
    data = payload()
    data["records"][0]["regret"] = 10
    data["records"][0]["model"] = "wrong/model"
    report = check(tmp_path, data)
    assert not report["audit_passed"]
    assert report["score_mismatches"] and report["condition_mismatches"]


def test_missing_and_duplicate_decisions_fail(tmp_path):
    data = payload()
    data["records"].pop()
    assert not check(tmp_path, data)["audit_passed"]
    data = payload()
    data["records"].append(data["records"][0].copy())
    assert not check(tmp_path, data)["audit_passed"]
    data["records"] = []
    assert check(tmp_path, data)["missing_samples"]


def test_invalid_model_output_is_not_data_integrity_failure(tmp_path):
    data = payload()
    case = build_cases(["test/model"], "smoke", 1)[0]
    data["records"] = outcome_records(case, {
        "row": {"action": None, "valid": False},
        "column": {"action": "D", "valid": True},
    })
    report = check(tmp_path, data)
    assert report["audit_passed"] and report["invalid_decisions"] == 1

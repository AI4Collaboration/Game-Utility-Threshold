import unittest

from analyze_phase_one_results import (
    analyze,
    audit_policy_summary,
    audit_phase_one_summary,
    threshold_transition_analysis,
)


def _record(provider: str, sample_id: str, stratum: str, action: str, defense: float = 2.0):
    expected = "ATTACK" if stratum == "just_unsafe" else "COOPERATE"
    return {
        "sample_id": sample_id,
        "provider": provider,
        "model": provider + "/model",
        "v": 1.0,
        "d": defense,
        "design_stratum": stratum,
        "threshold_region": "unsafe" if stratum == "just_unsafe" else "safe",
        "near_boundary": True,
        "expected_action": expected,
        "observed_action": action,
        "scores": {
            "valid_json": 1,
            "valid_action": 1,
            "optimal_action": int(action == expected),
            "utility_regret": 0.0 if action == expected else 0.25,
        },
        "prompt_and_messages": [{"role": "user", "content": "prompt"}],
        "model_output": {"completion": action},
    }


class PhaseOneAnalysisTests(unittest.TestCase):
    def test_full_triplets_and_shorter_zero_defense_checks_have_separate_denominators(self):
        records = [
            _record("openai", "safe", "just_safe", "ATTACK", 2),
            _record("openai", "boundary", "exact_boundary", "COOPERATE", 2),
            _record("openai", "unsafe", "just_unsafe", "ATTACK", 2),
            _record("openai", "zero-boundary", "exact_boundary", "COOPERATE", 0),
            _record("openai", "zero-unsafe", "just_unsafe", "ATTACK", 0),
        ]
        report = threshold_transition_analysis({"records": records})
        self.assertEqual(report["expected_transition_rate"], .5)
        self.assertEqual(report["full_triplets"]["rate"], 0)
        self.assertEqual(report["zero_defense_pairs"]["rate"], 1)
        self.assertIsNone(threshold_transition_analysis({"records": []})["full_triplets"]["rate"])

    def test_complete_matrix_audit(self) -> None:
        records = [
            _record("openai", "safe", "just_safe", "COOPERATE"),
            _record("openai", "boundary", "exact_boundary", "COOPERATE"),
            _record("openai", "unsafe", "just_unsafe", "ATTACK"),
        ]
        payload = {
            "configuration": {"providers": ["openai"], "samples_per_provider": 3},
            "completed_providers": ["openai"],
            "failed_providers": [],
            "records": records,
        }
        self.assertTrue(audit_phase_one_summary(payload)["complete"])
        self.assertEqual(
            threshold_transition_analysis(payload)["expected_transition_rate"],
            1.0,
        )
        self.assertEqual(analyze(payload)["incorrect_decisions"], [])

    def test_audit_rejects_duplicate_and_invalid_output(self) -> None:
        record = _record("openai", "one", "just_safe", "UNKNOWN")
        record["scores"]["valid_json"] = 0
        record["scores"]["valid_action"] = 0
        payload = {
            "configuration": {"providers": ["openai"], "samples_per_provider": 1},
            "completed_providers": [],
            "failed_providers": [{"provider": "openai", "error": "failed"}],
            "records": [record, record],
        }
        audit = audit_phase_one_summary(payload)
        self.assertFalse(audit["complete"])
        self.assertTrue(audit["duplicate_cells"])
        self.assertTrue(audit["invalid_actions"])

    def test_schema_noncompliance_is_preserved_as_behavioral_data(self) -> None:
        record = _record("openai", "one", "just_safe", "COOPERATE")
        record["scores"]["valid_json"] = 0
        payload = {
            "configuration": {"providers": ["openai"], "samples_per_provider": 1},
            "completed_providers": ["openai"],
            "failed_providers": [],
            "records": [record],
        }
        audit = audit_phase_one_summary(payload)
        self.assertTrue(audit["complete"])
        self.assertFalse(audit["all_worksheets_valid_json"])
        self.assertTrue(audit["all_actions_parseable"])

    def test_policy_baseline_audit_checks_exact_and_stochastic_certificates(self) -> None:
        records = []
        for policy in ("threshold", "pdupoc"):
            records.append({
                "sample_id": "one",
                "policy": policy,
                "scores": {"optimal_action": 1},
                "probabilistic_certificate": (
                    {"valid": True} if policy == "pdupoc" else None
                ),
            })
        payload = {
            "configuration": {
                "policies": ["threshold", "pdupoc"],
                "samples_per_policy": 1,
            },
            "statuses": {"threshold": "success", "pdupoc": "success"},
            "records": records,
        }
        self.assertTrue(audit_policy_summary(payload)["complete"])


if __name__ == "__main__":
    unittest.main()

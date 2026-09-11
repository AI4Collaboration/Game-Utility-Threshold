import unittest

from analyze_phase_one_results import (
    analyze,
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


if __name__ == "__main__":
    unittest.main()

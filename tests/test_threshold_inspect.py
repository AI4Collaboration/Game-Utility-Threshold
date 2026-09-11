import json
import unittest
from collections import Counter

from utility_threshold_inspect import (
    _analytic_worksheet,
    build_phase_one_samples,
    build_samples,
    parse_action,
    parse_structured_threshold_decision,
)
from utility_threshold.core import GameParams


class ThresholdInspectDatasetTests(unittest.TestCase):
    def test_phase_one_dataset_is_boundary_stratified_and_unique(self) -> None:
        dataset = build_phase_one_samples()
        self.assertEqual(len(dataset), 39)
        self.assertEqual(len({sample.id for sample in dataset}), 39)
        self.assertEqual(
            len({(sample.metadata["v"], sample.metadata["d"]) for sample in dataset}),
            39,
        )
        self.assertEqual(
            Counter(sample.metadata["design_stratum"] for sample in dataset),
            Counter({
                "broad_grid": 25,
                "exact_boundary": 5,
                "just_safe": 4,
                "just_unsafe": 5,
            }),
        )

    def test_boundary_cases_use_cooperation_tie_break(self) -> None:
        boundary = [
            sample
            for sample in build_phase_one_samples()
            if sample.metadata["design_stratum"] == "exact_boundary"
        ]
        self.assertEqual(len(boundary), 5)
        for sample in boundary:
            self.assertAlmostEqual(sample.metadata["safety_margin"], 0.0)
            self.assertEqual(sample.target, "COOPERATE")

    def test_prompt_declares_observability_boundary_and_schema(self) -> None:
        sample = build_samples(GameParams(), (4.0,), (2.0,))[0]
        self.assertIn("observable decision worksheet", sample.input)
        self.assertIn("private hidden chain-of-thought", sample.input)
        self.assertIn('"safety_margin"', sample.input)
        self.assertEqual(parse_action('{"final_action":"ATTACK"}'), "ATTACK")

    def test_structured_parser_and_analytic_worksheet(self) -> None:
        payload = {"final_action": "COOPERATE", "confidence": 0.8}
        self.assertEqual(
            parse_structured_threshold_decision(
                "worksheet follows\n```json\n" + json.dumps(payload) + "\n```"
            ),
            payload,
        )
        self.assertIsNone(parse_structured_threshold_decision("no object"))

        sample = build_phase_one_samples()[0]
        worksheet = _analytic_worksheet(sample.metadata, sample.target)
        self.assertEqual(worksheet["final_action"], sample.target)
        self.assertEqual(worksheet["safety_margin"], sample.metadata["safety_margin"])
        self.assertEqual(set(worksheet), {
            "observed_facts",
            "attack_utility",
            "cooperate_utility",
            "safety_margin",
            "threshold_inequality",
            "final_action",
            "confidence",
        })


if __name__ == "__main__":
    unittest.main()

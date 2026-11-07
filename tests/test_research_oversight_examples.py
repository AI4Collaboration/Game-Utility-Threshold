"""Verify offline demonstration records can be independently replayed exactly."""

from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from utility_threshold.core import GameParams, GameState
from utility_threshold.oversight_uncertainty import (
    ClosedInterval,
    MarginUncertainty,
    PrivateValue,
    TypeDistribution,
    evaluate_private_values,
    minimum_defense_for_attack_probability,
    one_parameter_distances,
    solve_private_value_defense,
    worst_case_margin,
    worst_case_margin_at_defense,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research_oversight_examples.py"
SAVED = ROOT / "results" / "research_theory" / "oversight_examples.json"


def decode_fraction(record):
    if set(record) != {"numerator", "denominator"}:
        raise AssertionError("An exact fraction record is required")
    return Fraction(record["numerator"], record["denominator"])


def decode_interval(record):
    return ClosedInterval(decode_fraction(record["lower"]), decode_fraction(record["upper"]))


class ResearchOversightExamplesTests(unittest.TestCase):
    def test_offline_generation_is_deterministic_and_every_certificate_replays(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "examples.json"
            generated = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output)],
                cwd=directory, check=True, capture_output=True, text=True,
            )
            self.assertIn("THEORY ONLY", generated.stdout)
            self.assertEqual(output.read_bytes(), SAVED.read_bytes())
            checked = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output), "--check"],
                cwd=directory, check=True, capture_output=True, text=True,
            )
            self.assertIn("reproduced", checked.stdout)
            data = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(data["evidence_class"], "THEORY_ONLY")
        self.assertEqual(data["model_calls"], 0)
        example = data["private_priority_example"]
        inputs = example["inputs"]
        params = GameParams(**{name: decode_fraction(value) for name, value in inputs["game_params"].items()})
        prior = TypeDistribution(tuple(
            PrivateValue(decode_fraction(item["v"]), decode_fraction(item["probability"]))
            for item in inputs["type_distribution"]["types"]
        ))
        optimum = solve_private_value_defense(prior, params, decode_fraction(inputs["max_defense"]))
        self.assertEqual(optimum.to_dict(), example["welfare_optimum"])
        self.assertEqual(optimum.defense, Fraction(5, 4))
        self.assertEqual(optimum.expected_human_utility, -Fraction(145, 32))
        for case in example["risk_requirements"]:
            saved = case["result"]
            replayed = minimum_defense_for_attack_probability(
                prior, params, decode_fraction(saved["target_attack_probability"]), decode_fraction(saved["max_defense"]),
            )
            self.assertEqual(replayed.to_dict(), saved)
        self.assertEqual(decode_fraction(example["risk_requirements"][1]["result"]["minimum_defense"]), 10)
        self.assertFalse(example["risk_requirements"][2]["result"]["feasible"])
        for point in example["defense_curve"]:
            replayed = evaluate_private_values(prior, decode_fraction(point["defense"]), params)
            for field in ("attack_probability", "unblocked_attack_probability", "expected_human_utility"):
                self.assertEqual(getattr(replayed, field), decode_fraction(point[field]))
            self.assertEqual(
                min(item.safety_margin for item in replayed.responses if item.probability > 0),
                decode_fraction(point["minimum_margin_over_positive_probability_types"]),
            )

        bounded = data["bounded_error_example"]
        certificate = worst_case_margin_at_defense(
            **{name: decode_interval(interval) for name, interval in bounded["inputs"].items()},
            required_margin=decode_fraction(bounded["required_margin"]),
        )
        self.assertEqual(certificate.to_dict(), bounded["certificate"])
        self.assertEqual(certificate.minimum_margin, Fraction(2, 5))
        self.assertTrue(certificate.required_margin_certified)

        counterexample = data["maximin_is_not_uniform_safety_counterexample"]
        box = MarginUncertainty(**{name: decode_interval(interval) for name, interval in counterexample["inputs"].items()})
        counter_certificate = worst_case_margin(box)
        self.assertEqual(counter_certificate.to_dict(), counterexample["certificate"])
        self.assertEqual(counter_certificate.maximin_action, "COOPERATE")
        self.assertFalse(counter_certificate.uniformly_cooperative)

        fragility = data["one_parameter_fragility_example"]
        fragility_params = GameParams(**{name: decode_fraction(value) for name, value in fragility["game_params"].items()})
        state = GameState(**{name: decode_fraction(value) for name, value in fragility["state"].items()})
        self.assertEqual(one_parameter_distances(state, fragility_params).to_dict(), fragility["certificate"])

    def test_check_fails_when_an_artifact_is_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "altered.json"
            output.write_text('{"evidence_class": "THEORY_ONLY"}\n', encoding="utf-8")
            checked = subprocess.run(
                [sys.executable, str(SCRIPT), "--output", str(output), "--check"],
                cwd=directory, capture_output=True, text=True,
            )
            self.assertEqual(checked.returncode, 1)
            self.assertIn("differs", checked.stderr)
            self.assertEqual(output.read_text(), '{"evidence_class": "THEORY_ONLY"}\n')


if __name__ == "__main__":
    unittest.main()

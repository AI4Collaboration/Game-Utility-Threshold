import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from utility_threshold.games.cli import build_parser, main, run_command


class ExtendedCliTests(unittest.TestCase):
    def test_validate_catalog_command_reports_every_constraint(self) -> None:
        args = build_parser().parse_args(["validate-catalog"])

        result = run_command(args)

        self.assertTrue(result["valid"])
        self.assertEqual(result["failure_count"], 0)
        self.assertGreater(result["check_count"], 150)
        json.dumps(result)

    def test_validate_catalog_can_write_deterministic_json(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory) / "catalog-validation.json"

            exit_code = main(["validate-catalog", "--output", str(output)])
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["failure_count"], 0)

    def test_analyze_supports_asymmetric_equilibrium_selection_thresholds(self) -> None:
        args = build_parser().parse_args([
            "analyze",
            "--scenario", "incident_response_protocol",
        ])
        result = run_command(args)
        self.assertEqual(result["threshold"]["threshold_kind"], "belief_in_preferred_coordination")
        self.assertIn("mixed_equilibrium", result["threshold"])
        self.assertEqual(len(result["threshold"]["pure_nash_equilibria"]), 2)
        json.dumps(result)

    def test_uncertain_command_emits_full_decision_analysis(self) -> None:
        args = build_parser().parse_args([
            "uncertain",
            "--scenario", "autonomous_escalation",
            "--risk-criterion", "cvar",
            "--tail-probability", "0.2",
        ])
        result = run_command(args)
        self.assertEqual(result["decision_analysis"]["criterion"], "lower_tail_cvar")
        self.assertEqual(len(result["uncertain_game"]["states"]), 3)
        json.dumps(result)

    def test_institutional_cli_composes_mechanisms(self) -> None:
        args = build_parser().parse_args([
            "institutional-match",
            "--scenario", "autonomous_escalation",
            "--mechanism", "communication",
            "--mechanism", "contract",
            "--mechanism", "mediator",
            "--rounds", "3",
            "--seed", "17",
        ])
        result = run_command(args)
        match = result["institutional_match"]
        self.assertEqual(match["round_count"], 3)
        self.assertEqual(
            match["rules"]["payoff_mechanisms"], ["contract_with_penalties"]
        )
        self.assertEqual(match["rules"]["communication"], "pre_play_communication")
        self.assertEqual(match["rules"]["mediator"], "trusted_mediator")
        self.assertTrue(all(round_["communication"] for round_ in match["rounds"]))
        json.dumps(result)

    def test_battle_institutional_cli_uses_coordination_subsidy(self) -> None:
        args = build_parser().parse_args([
            "institutional-match",
            "--scenario", "incident_response_protocol",
            "--mechanism", "side_payment",
            "--rounds", "1",
        ])
        result = run_command(args)
        trace = result["institutional_match"]["rules"]["payoff_mechanisms"]
        self.assertEqual(trace, ["coordination_subsidy"])
        json.dumps(result)


if __name__ == "__main__":
    unittest.main()

import copy
import json
from pathlib import Path
import tempfile
import unittest

from utility_threshold.research_design import (
    analytic_boundary, build_manifest, default_config, expected_margin, game_at,
    labels, matrix_record, prompt_for, score_episode, verify_manifest,
)
from run_research_study import audit_records, pending_cases, quote_manifest, ResearchRuntime, validate_resume_pair
from run_phase_space import parse_decision
from analyze_research_study import analyze, render


def config():
    return default_config(["test/model"], replicates=4)


def returned(case, role, action="D"):
    raw = json.dumps({"action": labels(case, role)[action], "explanation": "unit-test fixture"})
    return {**parse_decision(raw, labels(case, role)), "response_status": "returned", "raw_completion": raw,
            "prompt_hash": case["prompt_hashes"][role], "requested_effort": case["effort_pair"][int(role == "column")]}


class ResearchDesignTests(unittest.TestCase):
    def test_pd_sweeps_stay_strict_and_never_predict_cooperation(self):
        for arm in config()["arms"][:2]:
            for x in arm["values"]:
                game = game_at(arm, x)
                self.assertEqual(game.dominant_actions("row", strict=True), ("D",))
                for q in (0, .2, .5, .9, 1):
                    self.assertLess(expected_margin(matrix_record(game), "row", q), 0)
            self.assertFalse(analytic_boundary(arm, "row")["inside_sampled_range"])

    def test_pd_cost_is_one_mechanism_with_fixed_units(self):
        arm = config()["arms"][2]
        before, after = matrix_record(game_at(arm, 0)), matrix_record(game_at(arm, .375))
        self.assertEqual(after[0][0], before[0][0])
        self.assertEqual(after[1][0][0], before[1][0][0]-.375)
        self.assertEqual(after[1][1][0], before[1][1][0]-.375)
        self.assertEqual(after[0][1][0], before[0][1][0])
        self.assertAlmostEqual(analytic_boundary(arm, "row")["value"], .375)
        self.assertAlmostEqual(expected_margin(after, "row", .5), 0)

    def test_all_game_families_have_independently_known_structure(self):
        arms = config()["arms"]
        pd = game_at(arms[0], 1.5)
        chicken, stag, protocol = (game_at(arm, .5) for arm in arms[3:])
        self.assertEqual(pd.pure_nash_equilibria(), (("D", "D"),))
        self.assertEqual(set(chicken.pure_nash_equilibria()), {("C", "D"), ("D", "C")})
        for game in (stag, protocol):
            self.assertEqual(set(game.pure_nash_equilibria()), {("C", "C"), ("D", "D")})
        self.assertEqual(analytic_boundary(arms[3], "row")["direction"], "decreasing")
        self.assertEqual(analytic_boundary(arms[4], "row")["direction"], "increasing")
        self.assertAlmostEqual(analytic_boundary(arms[5], "row")["value"], 11/23)
        self.assertAlmostEqual(analytic_boundary(arms[5], "column")["value"], 12/23)

    def test_positive_scale_and_offset_controls_preserve_incentives(self):
        arm = config()["arms"][0]
        for axis, values in [("scale", [1, 2, 10]), ("offset", [-10, 0, 10])]:
            control = {**arm, "axis": axis, "values": values}
            for x in values:
                self.assertEqual(game_at(control, x).dominant_actions("row", strict=True), ("D",))
            self.assertIsNone(analytic_boundary(control, "row")["value"])
        control = {**arm, "axis": "offset", "values": [-10, 0, 10], "s": -.1, "t": 1.1, "q": .1}
        self.assertEqual(analytic_boundary(control, "row")["kind"], "no_crossing")
        self.assertIsNone(analytic_boundary(control, "row")["value"])

    def test_manifest_is_deterministic_and_balances_both_players_labels(self):
        manifest = build_manifest(config())
        self.assertEqual(manifest, build_manifest(config()))
        verify_manifest(json.loads(json.dumps(manifest)))
        self.assertEqual(len({c["sample_id"] for c in manifest["cases"]}), manifest["planned_episodes"])
        for cell in manifest["cells"]:
            cases = [c for c in manifest["cases"] if c["cell_id"] == cell["cell_id"]]
            self.assertEqual({(labels(c, "row")["C"], labels(c, "column")["C"]) for c in cases},
                             {("A", "A"), ("A", "B"), ("B", "A"), ("B", "B")})
        manifest["cases"][0]["q"] = .123
        with self.assertRaises(ValueError):
            verify_manifest(manifest)

    def test_column_prompt_preserves_asymmetric_payoffs(self):
        settings = config()
        settings["arms"] = settings["arms"][-1:]
        manifest = build_manifest(settings)
        case = next(c for c in manifest["cases"] if c["label_block"] == 0 and c["roles"] == ["column"])
        prompt = prompt_for(case, "column")
        self.assertIn("(A, A) -> (3, 4)", prompt)
        self.assertIn("(B, B) -> (4, 3)", prompt)
        self.assertNotIn("Prisoner", prompt)
        self.assertIn("fixed random policy", prompt)

    def test_config_validation_blocks_misleading_or_unbalanced_designs(self):
        bad = []
        for field, value in [("replicates", 3), ("replicates", True), ("alpha", 0), ("max_tokens", -1), ("models", ["x", "x"])]:
            d = config(); d[field] = value; bad.append(d)
        d = config(); d["purpose"] = "confirmation"; bad.append(d)
        d = config(); d["arms"][0]["values"] = [.5, 1.5]; bad.append(d)
        d = config(); d["arms"][-1]["axis"] = "t"; bad.append(d)
        d = config(); d["arms"][0]["values"] = [float("nan"), 2]; bad.append(d)
        for d in bad:
            with self.subTest(config=d), self.assertRaises(ValueError):
                build_manifest(d)

    def test_ties_accept_either_action_and_invalid_is_not_defection(self):
        manifest = build_manifest(config())
        case = next(c for c in manifest["cases"] if c["q"] == .5 and c["matrix"][1][1][0] == -.375)
        role = case["roles"][0]
        for action in ("C", "D"):
            record = score_episode(case, {role: {"action": action, "valid": True}})
            self.assertEqual(record["optimal_actions"][role], ["C", "D"])
            self.assertEqual(record["regret"][role], 0)
        record = score_episode(case, {role: {"action": None, "valid": False}})
        self.assertIsNone(record["first_action_fraction"])
        self.assertEqual(record["status"], "invalid")

    def test_self_play_is_one_episode_and_has_no_known_opponent_cutoff(self):
        settings = config(); settings["arms"] = settings["arms"][:1]
        settings["arms"][0]["mode"] = "self_play"
        settings["effort_pairs"] = [["low", "high"], ["high", "low"]]
        manifest = build_manifest(settings)
        case = manifest["cases"][0]
        self.assertEqual(case["roles"], ["row", "column"])
        self.assertIsNone(case["q"])
        record = score_episode(case, {"row": {"action": "C", "valid": True}, "column": {"action": "D", "valid": True}})
        self.assertEqual(record["first_action_fraction"], .5)
        self.assertEqual(record["regret"], {})
        self.assertEqual(manifest["cells"][0]["analytic"]["row"]["kind"], "not_identified")
        runtime = ResearchRuntime({}, Path("unused"), None, 1024)
        self.assertEqual(runtime.reasoning_effort(case, "row"), case["effort_pair"][0])
        self.assertEqual(runtime.reasoning_effort(case, "column"), case["effort_pair"][1])

    def test_audit_rejects_duplicates_altered_scores_and_foreign_ids(self):
        manifest = build_manifest(config()); case = manifest["cases"][0]; role = case["roles"][0]
        record = score_episode(case, {role: returned(case, role)})
        self.assertEqual(audit_records(manifest, [record])["recorded_episodes"], 1)
        for records in [[record, record], [{**record, "first_action_fraction": .123}], [{**record, "sample_id": "foreign"}]]:
            with self.assertRaises(ValueError):
                audit_records(manifest, records)

    def test_raw_completion_cannot_disagree_with_saved_action(self):
        manifest = build_manifest(config()); case = manifest["cases"][0]; role = case["roles"][0]
        corrupted = returned(case, role, "D"); corrupted["action"] = "C"
        record = score_episode(case, {role: corrupted})
        with self.assertRaisesRegex(ValueError, "raw completion"):
            audit_records(manifest, [record])
        fabricated = score_episode(case, {role: {"action": "C", "valid": True}})
        with self.assertRaises(ValueError):
            audit_records(manifest, [fabricated])

    def test_transport_failure_is_missing_and_empty_return_is_invalid(self):
        manifest = build_manifest(config()); case = manifest["cases"][0]; role = case["roles"][0]
        missing = score_episode(case, {role: {"response_status": "transport_error", "action": None,
                                             "valid": False, "parse_error": "timeout",
                                             "prompt_hash": case["prompt_hashes"][role],
                                             "requested_effort": case["effort_pair"][int(role == "column")]}})
        invalid = score_episode(case, {role: {**parse_decision("", labels(case, role)),
                                             "response_status": "returned", "raw_completion": ""}})
        self.assertEqual(missing["status"], "missing")
        self.assertEqual(invalid["status"], "invalid")
        audit = audit_records(manifest, [missing])
        self.assertEqual(audit["missing_episodes"], 1)
        self.assertEqual(audit["invalid_episodes"], 0)
        self.assertEqual(audit["unrecorded_episodes"], manifest["planned_episodes"]-1)

    def test_extreme_affine_controls_preserve_display_and_decision_structure(self):
        for axis, values in [("offset", [0, 1e12]), ("scale", [1e-12, 1])]:
            settings = config(); settings["arms"] = settings["arms"][:1]
            settings["arms"][0].update(axis=axis, values=values)
            manifest = build_manifest(settings)
            for cell in manifest["cells"]:
                self.assertEqual(cell["pure_equilibria"], [["D", "D"]])
            for case in manifest["cases"]:
                role = case["roles"][0]
                record = score_episode(case, {role: returned(case, role)})
                self.assertEqual(record["optimal_actions"][role], ["D"])
            if axis == "offset":
                case = next(c for c in manifest["cases"] if c["matrix"][0][0][0] > 1e11)
                self.assertIn("1000000000001", prompt_for(case, case["roles"][0]))
        settings["arms"][0].update(axis="offset", values=[0, 1e20])
        with self.assertRaisesRegex(ValueError, "distinctions"):
            build_manifest(settings)
        settings["arms"][0].update(axis="scale", values=[1, 1e308])
        with self.assertRaisesRegex(ValueError, "arithmetic range"):
            build_manifest(settings)

    def test_self_play_primary_outcomes_follow_game_question(self):
        for source, measure, expected in [(0, "mutual_C", 0), (3, "opposite_actions", 1),
                                           (4, "mutual_C", 0), (5, "matching_actions", 0)]:
            settings = config(); arm = settings["arms"][source]
            arm.update(mode="self_play", axis="scale", values=[1, 2])
            settings["arms"] = [arm]
            case = build_manifest(settings)["cases"][0]
            result = score_episode(case, {"row": returned(case, "row", "C"), "column": returned(case, "column", "D")})
            self.assertEqual(result["primary_measure"], measure)
            self.assertEqual(result["primary_score"], expected)
            self.assertEqual(result["joint_outcome"], "CD")
            self.assertEqual(result["joint_numerical_payoff"], sum(result["numerical_payoffs"].values()))
            self.assertTrue(all(v >= 0 for v in result["realized_deviation_gain"].values()))

    def test_fixed_opponent_rejects_unused_effort_combinations(self):
        settings = config(); settings["effort_pairs"] = [["low", "low"], ["low", "high"]]
        with self.assertRaisesRegex(ValueError, "unequal efforts"):
            build_manifest(settings)

    def test_resume_requires_matching_persistent_budget_ledger(self):
        manifest = build_manifest(config())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"observations.json"
            ledger = validate_resume_pair(output, manifest)
            output.write_text("{}")
            with self.assertRaisesRegex(ValueError, "exist together"):
                validate_resume_pair(output, manifest)
            ledger.write_text(json.dumps({"manifest_hash": "other"}))
            with self.assertRaisesRegex(ValueError, "different"):
                validate_resume_pair(output, manifest)
            ledger.write_text(json.dumps({"manifest_hash": manifest["manifest_hash"]}))
            self.assertEqual(validate_resume_pair(output, manifest), ledger)

    def test_pending_calls_are_not_retried_after_interruption(self):
        manifest = build_manifest(config()); case = manifest["cases"][0]
        pending, interrupted = pending_cases(manifest, [], [{"call_id": case["sample_id"]+":row"}])
        self.assertEqual(interrupted, [case["sample_id"]])
        self.assertNotIn(case, pending)

    def test_offline_quote_and_missing_report_are_explicit(self):
        settings = config(); settings["arms"] = settings["arms"][:1]
        manifest = build_manifest(settings)
        quote = quote_manifest(manifest, {"checked_at": "test", "models": {"test/model": {
            "price_ceiling_per_token": {"prompt": 1e-6, "completion": 2e-6}}}})
        self.assertGreater(quote["initial_call_reservation_usd"], 0)
        report = analyze(manifest)
        self.assertEqual(report["audit"]["recorded_episodes"], 0)
        self.assertEqual(report["curves"][0]["behavioral_threshold"]["status"], "assumption_not_declared")
        for cell in report["cells"]:
            self.assertIsNone(cell["statistics"]["valid_mean"])
            self.assertEqual(cell["statistics"]["completion_interval"], {"lower": 0, "upper": 1})
        with tempfile.TemporaryDirectory() as directory:
            render(report, Path(directory))
            page = (Path(directory)/"index.html").read_text()
            self.assertIn("DESIGN ONLY", page)
            self.assertTrue((Path(directory)/"cells.csv").exists())


if __name__ == "__main__":
    unittest.main()

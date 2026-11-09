from copy import deepcopy
from fractions import Fraction
import json
import math
from pathlib import Path
import tempfile
import unittest

from gut.experiment import (PD, bounds, collect, decision, load_run, make_plan,
                            observations, save_plan, summarize, synthetic)
from gut.proofs import exact_table, export_proofs


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "run"

    def plan(self, **kwargs):
        return save_plan(self.directory, repetitions=2, **kwargs)

    def test_schedule_balances_labels_roles_and_freezes_requests(self):
        plan = self.plan()
        self.assertEqual(len(plan["jobs"]), 80)
        self.assertEqual(plan, make_plan(repetitions=2))
        self.assertNotEqual(plan["jobs"], make_plan(repetitions=2, seed=12)["jobs"])
        for z in {j["z"] for j in plan["jobs"]}:
            for block in (0, 1):
                for role in ("row", "column"):
                    self.assertEqual(sum(j["z"] == z and j["block"] == block and j["role"] == role for j in plan["jobs"]), 2)
        for job in plan["jobs"]:
            self.assertEqual(len(job["request"]["messages"]), 1)
            self.assertFalse(job["request"]["provider"]["allow_fallbacks"])

    def test_rejects_invalid_settings_and_overwrite(self):
        for settings in ({"repetitions": True}, {"temperature": float("nan")},
                         {"seed": -1}, {"max_tokens": 0}, {"mode": "openrouter"}):
            with self.assertRaises(ValueError):
                make_plan(**settings)
        self.plan()
        with self.assertRaises(FileExistsError):
            self.plan()

    def test_tampered_plan_and_records_fail_audit(self):
        self.plan()
        collect(self.directory, max_calls=1)
        log = self.directory / "records.jsonl"
        original = log.read_text()
        for altered in (original + original, original + '{"incomplete":',
                        original.replace('"max_tokens": 512', '"max_tokens": 513')):
            log.write_text(altered)
            with self.assertRaises(ValueError):
                load_run(self.directory)
        log.write_text(original)
        path = self.directory / "plan.json"
        data = json.loads(path.read_text())
        data["jobs"].pop()
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            load_run(self.directory)

    def test_resume_never_repeats_completed_or_interrupted_attempt(self):
        self.plan()
        def crash(job, plan):
            raise RuntimeError("interrupted after durable start")
        with self.assertRaises(RuntimeError):
            collect(self.directory, transport=crash)
        self.assertEqual(collect(self.directory), 79)
        self.assertEqual(collect(self.directory), 0)
        summary = summarize(self.directory)
        self.assertEqual(summary["attempted_decisions"], 80)
        self.assertEqual(summary["decision_statuses"], {"not_completed": 1, "valid": 79})
        self.assertEqual(sum(r["valid_games"] for r in summary["cells"]), 39)

    def test_lock_prevents_concurrent_collection(self):
        self.plan()
        (self.directory / ".collect.lock").write_text("another collector")
        with self.assertRaises(FileExistsError):
            collect(self.directory)
        self.assertFalse((self.directory / "records.jsonl").exists())

    def test_live_requires_explicit_switch_and_call_limit(self):
        self.plan(mode="openrouter", model="vendor/model", provider="vendor")
        for kwargs in ({}, {"live": True}, {"max_calls": 1}):
            with self.assertRaises(ValueError):
                collect(self.directory, **kwargs)
        def failure(job, plan):
            return 429, '{"error":"rate limited"}', "HTTPError"
        self.assertEqual(collect(self.directory, live=True, max_calls=10, transport=failure), 1)
        self.assertEqual(summarize(self.directory)["decision_statuses"]["transport_error"], 1)

    def test_strict_parser_keeps_invalid_and_model_mismatches(self):
        plan = make_plan()
        job = plan["jobs"][0]
        status, body, error = synthetic(job, plan)
        response = json.loads(body)
        finish = {"http_status": status, "body": body, "error": error}
        self.assertIsNotNone(decision(plan, job, finish)[0])
        for content in ('{"final_action":"A","final_action":"B"}', 'Here: {"final_action":"A"}',
                        '{"final_action":"A","extra":1}', 'null', '{"final_action":"C"}'):
            altered = deepcopy(response)
            altered["choices"][0]["message"]["content"] = content
            self.assertIsNone(decision(plan, job, {**finish, "body": json.dumps(altered)})[0])
        response["model"] = "wrong/model"
        self.assertEqual(decision(plan, job, {**finish, "body": json.dumps(response)})[1], "model_mismatch")

    def test_uncertainty_uses_pairs_and_balanced_label_weights(self):
        mean, low, high = bounds([[1]*10, [0]*2])
        self.assertEqual(mean, 0.5)
        radius = math.sqrt(math.log(40)*(1/10+1/2)/8)
        self.assertAlmostEqual(low, max(0, 0.5-radius))
        self.assertAlmostEqual(high, min(1, 0.5+radius))
        self.assertLess(bounds([[1]*10, [1]*10])[1], 1)
        self.assertEqual(bounds([[], [1]]), (None, None, None))

    def test_missing_partner_excluded_and_all_planned_settings_retained(self):
        self.plan()
        empty = summarize(self.directory)
        self.assertEqual(len(empty["cells"]), 10)
        self.assertTrue(all(r["cooperation_rate"] is None for r in empty["cells"]))
        self.assertTrue(all((r["missing_lower"], r["missing_upper"]) == (0, 1) for r in empty["cells"]))
        collect(self.directory, max_calls=1)
        self.assertEqual(sum(r["valid_games"] for r in summarize(self.directory)["cells"]), 0)

    def test_exact_proof_table_matches_python_and_ties(self):
        for z in ("0", "1/2", "1", "1/3", "21/20"):
            denominator, values = exact_table(z)
            self.assertGreater(denominator, 0)
            expected = [PD.matrix(z)[i][j][0] for i in range(2) for j in range(2)]
            self.assertEqual([Fraction(v, denominator) for v in values], expected)
        self.plan()
        collect(self.directory)
        result = export_proofs(self.directory)
        self.assertFalse(result["verified"])
        self.assertEqual(result["mapped_choices"], 80)
        mapping = json.loads((self.directory / "proofs/mapping.json").read_text())
        for row in mapping:
            if row["z"] == "1/2":
                self.assertEqual(row["against_second"], "tied")
            if row["z"] == "1":
                self.assertEqual(row["against_first"], "tied")
        self.assertTrue(any(not r["dominant"] for r in mapping))
        self.assertTrue(any(r["dominant"] for r in mapping))

    def test_invalid_choices_have_no_fabricated_proof(self):
        self.plan()
        def invalid(job, plan):
            return 200, 'not json', None
        collect(self.directory, max_calls=1, transport=invalid)
        result = export_proofs(self.directory)
        self.assertEqual(result["mapped_choices"], 0)
        self.assertEqual(result["unmapped_choices"], 80)


if __name__ == "__main__":
    unittest.main()

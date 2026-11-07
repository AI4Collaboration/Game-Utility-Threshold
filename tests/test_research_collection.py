"""Offline collection integration tests; external network connections are blocked."""

from contextlib import ExitStack
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from run_phase_space import PROVIDER_ROUTES, parse_decision
from run_research_study import audit_records, collect_live
from utility_threshold.research_design import build_manifest, default_config, labels, score_episode

HAS_INSPECT = importlib.util.find_spec("inspect_ai") is not None


def small_manifest(*, self_play=False):
    config = default_config([next(iter(PROVIDER_ROUTES))], replicates=4)
    config["arms"] = config["arms"][:1]
    config["arms"][0]["values"] = [1.05, 1.25]
    if self_play:
        config["arms"][0]["mode"] = "self_play"
        config["effort_pairs"] = [["low", "high"]]
    return build_manifest(config)


def returned(case, role):
    raw = json.dumps({"action": labels(case, role)["C"], "explanation": "offline unit fixture"})
    return {
        **parse_decision(raw, labels(case, role)), "raw_completion": raw, "response_status": "returned",
        "prompt_hash": case["prompt_hashes"][role],
        "requested_effort": case["effort_pair"][int(role == "column")],
    }


def preflight_fixture(manifest):
    return {
        "checked_at": "offline-test-only", "key_limit_remaining": None,
        "models": {
            model: {"provider_route": PROVIDER_ROUTES[model],
                    "price_ceiling_per_token": {"prompt": 1e-6, "completion": 2e-6, "request": 0}}
            for model in manifest["config"]["models"]
        },
    }


class ResearchParsingIntegrityTests(unittest.TestCase):
    def test_nonfinite_constants_and_duplicate_keys_are_invalid_even_after_prose(self):
        invalid = [
            '{"action":"A","explanation":NaN}',
            '{"action":"A","explanation":Infinity}',
            '{"action":"A","explanation":-Infinity}',
            '{"action":"A","explanation":1e999}',
            '{"action":"A","explanation":-1e999}',
            '{"action":"A","action":"B"}',
            '{"action":"A","explanation":{"reason":1,"reason":2}}',
        ]
        for body in invalid:
            for raw in (body, "Reasoning summary. " + body, "```json\n" + body + "\n```"):
                with self.subTest(raw=raw):
                    parsed = parse_decision(raw, {"C": "A", "D": "B"})
                    self.assertFalse(parsed["valid"])
                    self.assertIsNone(parsed["action"])
                    self.assertTrue(parsed["parse_error"])
                    json.dumps(parsed, allow_nan=False)
        # A malformed/conflicting earlier decision is not discarded in favor
        # of a later valid JSON object.
        parsed = parse_decision('Prose {"action":"A","action":"B"} {"action":"A"}', {"C": "A", "D": "B"})
        self.assertFalse(parsed["valid"])

    def test_audit_rejects_numeric_booleans_and_changed_collection_conditions(self):
        manifest = small_manifest()
        case = manifest["cases"][0]
        role = case["roles"][0]
        for field, changed in (("valid", 1), ("json_format_exact", 1),
                               ("prompt_hash", "different"), ("requested_effort", "high")):
            decision = returned(case, role)
            decision[field] = changed
            record = score_episode(case, {role: decision})
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit_records(manifest, [record])
        decision = returned(case, role)
        del decision["parse_error"]
        with self.assertRaises(ValueError):
            audit_records(manifest, [score_episode(case, {role: decision})])

    def test_transport_error_requires_frozen_provenance_too(self):
        manifest = small_manifest()
        case = manifest["cases"][0]
        role = case["roles"][0]
        decision = {
            "response_status": "transport_error", "valid": False, "action": None, "parse_error": "test timeout",
            "prompt_hash": case["prompt_hashes"][role],
            "requested_effort": case["effort_pair"][int(role == "column")],
        }
        record = score_episode(case, {role: decision})
        self.assertEqual(audit_records(manifest, [record])["missing_episodes"], 1)
        decision["requested_effort"] = "high"
        with self.assertRaisesRegex(ValueError, "requested_effort"):
            audit_records(manifest, [score_episode(case, {role: decision})])


@unittest.skipUnless(HAS_INSPECT, "Inspect integration requires the declared inspect-ai dependency")
class ResearchCollectionIntegrationTests(unittest.TestCase):
    def test_preflight_failure_keeps_a_resumable_empty_output_ledger_pair(self):
        manifest = small_manifest()
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            output = Path(directory) / "observations.json"
            stack.enter_context(patch.dict("os.environ", {"OPENROUTER_API_KEY": "offline-test-no-real-key"}))
            stack.enter_context(patch("dotenv.load_dotenv"))
            preflight = stack.enter_context(patch("run_research_study.preflight", side_effect=RuntimeError("offline preflight failure")))
            inspect_eval = stack.enter_context(patch("inspect_ai.eval", side_effect=AssertionError("No evaluation expected")))
            stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Network is forbidden in this test")))
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, "offline preflight failure"):
                    collect_live(manifest, output, 1, Path(directory)/"logs", 4, 2)
                payload = json.loads(output.read_text())
                ledger = json.loads(output.with_suffix(".ledger.json").read_text())
                self.assertEqual(payload["manifest_hash"], manifest["manifest_hash"])
                self.assertEqual(ledger["manifest_hash"], manifest["manifest_hash"])
                self.assertEqual(payload["records"], [])
                self.assertEqual(ledger["calls"], [])
            self.assertEqual(preflight.call_count, 2)
            inspect_eval.assert_not_called()

    def run_mock_collection(self, manifest, budget):
        """Run the actual Inspect task, solver, runtime, ledger, and checkpoints.

        Only the external provider and metadata preflight are replaced. All
        records live in a temporary directory and are never published as data.
        """
        from inspect_ai import eval as actual_eval
        from inspect_ai.model import ModelOutput, get_model as actual_get_model

        prompts, routed = [], []

        class OfflineProvider:
            async def generate(self, prompt, config):
                prompts.append({"prompt": prompt, "effort": config.reasoning_effort,
                                "max_tokens": config.max_tokens, "max_retries": config.max_retries})
                response = ModelOutput.from_content("offline/test-provider", '{"action":"A","explanation":"offline test fixture"}')
                response.metadata = {"phase_space_billing": {"cost_usd": 0.00001, "source": "offline-test-only"}}
                return response

        def route_model(name, *args, **kwargs):
            if name.startswith("phase_openrouter/"):
                routed.append({"name": name, "kwargs": kwargs})
                return OfflineProvider()
            return actual_get_model(name, *args, **kwargs)

        def quiet_eval(*args, **kwargs):
            return actual_eval(*args, **{**kwargs, "display": "none"})

        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            output = root / "observations.json"
            stack.enter_context(patch.dict("os.environ", {"OPENROUTER_API_KEY": "offline-test-no-real-key"}))
            stack.enter_context(patch("dotenv.load_dotenv"))
            stack.enter_context(patch("run_research_study.preflight", return_value=preflight_fixture(manifest)))
            stack.enter_context(patch("inspect_ai.model.get_model", side_effect=route_model))
            stack.enter_context(patch("inspect_ai.eval", side_effect=quiet_eval))
            # Keep Inspect's local trace/cache writes inside this test directory.
            stack.enter_context(patch("inspect_ai._util.appdirs.user_data_path", return_value=root/"data"))
            stack.enter_context(patch("inspect_ai._util.appdirs.user_cache_path", return_value=root/"cache"))
            stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Network is forbidden in this test")))
            audit = collect_live(manifest, output, budget, root/"logs", 4, 2)
            payload = json.loads(output.read_text())
            ledger = json.loads(output.with_suffix(".ledger.json").read_text())
            # A normal resume must not issue another provider call for any
            # checkpointed decision. This also runs source/manifest binding.
            count = len(prompts)
            resumed = collect_live(manifest, output, budget, root/"logs", 4, 2)
            self.assertEqual(len(prompts), count)
            self.assertEqual(resumed, audit)
        return audit, payload, ledger, prompts, routed

    def test_actual_inspect_execution_preserves_roles_effort_and_budget_without_network(self):
        manifest = small_manifest(self_play=True)
        audit, payload, ledger, prompts, routed = self.run_mock_collection(manifest, 1)
        self.assertTrue(audit["complete"])
        self.assertEqual(audit["valid_episodes"], manifest["planned_episodes"])
        self.assertEqual(len(prompts), manifest["planned_decisions"])
        self.assertEqual(len(ledger["calls"]), len(prompts))
        self.assertTrue(all(call["status"] == "returned" for call in ledger["calls"]))
        self.assertEqual({prompt["effort"] for prompt in prompts}, {"low", "high"})
        self.assertTrue(all(prompt["max_retries"] == 0 for prompt in prompts))
        self.assertTrue(all(prompt["max_tokens"] == manifest["config"]["max_tokens"] for prompt in prompts))
        self.assertTrue(all(isinstance(prompt["prompt"], str) for prompt in prompts))
        for record in payload["records"]:
            self.assertEqual(record["decisions"]["row"]["requested_effort"], "low")
            self.assertEqual(record["decisions"]["column"]["requested_effort"], "high")
        for route in routed:
            self.assertFalse(route["kwargs"]["provider"]["allow_fallbacks"])
            self.assertTrue(route["kwargs"]["provider"]["require_parameters"])
            self.assertEqual(route["kwargs"]["max_retries"], 0)
        self.assertEqual(audit_records(manifest, payload["records"]), audit)

    def test_unaffordable_episode_remains_unrecorded_and_issues_no_provider_call(self):
        manifest = small_manifest(self_play=True)
        audit, payload, ledger, prompts, routed = self.run_mock_collection(manifest, 1e-12)
        self.assertEqual(audit["recorded_episodes"], 0)
        self.assertEqual(audit["unrecorded_episodes"], manifest["planned_episodes"])
        self.assertFalse(audit["complete"])
        self.assertEqual(payload["records"], [])
        self.assertEqual(payload["completed_samples"], [])
        self.assertEqual(payload["stop_reason"], "budget_limit")
        self.assertEqual(ledger["calls"], [])
        self.assertEqual(prompts, [])
        self.assertEqual(routed, [])


if __name__ == "__main__":
    unittest.main()

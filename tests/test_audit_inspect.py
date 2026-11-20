import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

if importlib.util.find_spec("inspect_ai"):
    from inspect_ai import eval as inspect_eval
    from inspect_ai.log import read_eval_log
    from inspect_ai.model import ContentReasoning, ContentText, ModelOutput, get_model
    from gut.audit_inspect import audit_task, parse_choice
    from gut.audit_game import demo_game
    from audit_experiment import export_log, mock_attacker


@unittest.skipUnless(importlib.util.find_spec("inspect_ai"), "Install the inspect extra")
class InspectAuditTests(unittest.TestCase):
    def run_task(self, task, directory):
        logs = inspect_eval(task, model=None, log_dir=directory, display="none",
                            max_retries=0, max_samples=1, max_tokens=400)
        return read_eval_log(logs[0].location), logs[0].location

    def test_native_roles_private_views_and_reasoning_survive_round_trip(self):
        defender_prompts, attacker_prompts = [], []
        def defend(messages, *args):
            defender_prompts.append(messages[-1].text)
            return ModelOutput.from_content("mockllm/defender", [
                ContentReasoning(reasoning="SYNTHETIC_DEFENDER_PRIVATE_REASONING"),
                ContentText(text='{"q":"1/2"}')])
        def attack(messages, *args):
            attacker_prompts.append(messages[-1].text)
            return ModelOutput.from_content("mockllm/attacker", [
                ContentReasoning(reasoning="SYNTHETIC_ATTACKER_PRIVATE_REASONING"),
                ContentText(text='{"action":"abstain"}')])
        task = audit_task(demo_game(), {"defender": get_model("mockllm/defender", custom_outputs=defend),
                                       "attacker": get_model("mockllm/attacker", custom_outputs=attack)},
                          defender_mode="model", coverages=["1/2"])
        with tempfile.TemporaryDirectory() as folder:
            log, path = self.run_task(task, folder)
            self.assertEqual(log.status, "success")
            self.assertEqual(len(log.samples), 2)
            self.assertEqual(defender_prompts[0], defender_prompts[1])
            self.assertNotIn('"private_type"', defender_prompts[0])
            for prompt in attacker_prompts:
                self.assertNotIn("SYNTHETIC_DEFENDER_PRIVATE_REASONING", prompt)
                self.assertNotIn("inspected_target", prompt)
            self.assertIn('"private_type": "low"', attacker_prompts[0])
            self.assertIn('"private_type": "high"', attacker_prompts[1])
            for sample in log.samples:
                events = [e for e in sample.events if e.event == "model"]
                self.assertEqual([e.role for e in events], ["defender", "attacker"])
                for event in events:
                    content = event.output.message.content
                    self.assertEqual(content[0].type, "reasoning")
                    self.assertIn("SYNTHETIC_", content[0].reasoning)
                self.assertTrue(sample.metadata["record"]["synthetic"])
                self.assertEqual(sample.scores["audit_outcomes"].value["regret"], 0)
            export_log(path, Path(folder)/"export.jsonl")
            self.assertEqual(len((Path(folder)/"export.jsonl").read_text().splitlines()), 2)

    def test_invalid_is_not_abstention_and_defender_failure_stops_attacker(self):
        for role in ("defender", "attacker"):
            bad = get_model(f"mockllm/{role}", custom_outputs=[ModelOutput.from_content("mockllm", "not JSON")])
            roles = {"attacker": bad} if role == "attacker" else {
                "defender": bad,
                "attacker": get_model("mockllm/attacker", custom_outputs=[])}
            task = audit_task(demo_game("known"), roles, coverages=["1/2"],
                              defender_mode="fixed" if role == "attacker" else "model")
            with tempfile.TemporaryDirectory() as folder:
                log, _ = self.run_task(task, folder)
                row = log.samples[0].metadata["record"]
                self.assertEqual(row["status"], "invalid_"+role)
                self.assertNotIn("action", row)
                self.assertNotIn("outcome", row)
                self.assertEqual(log.samples[0].scores["audit_outcomes"].value, {"valid": 0})
                self.assertEqual(len([e for e in log.samples[0].events if e.event == "model"]), 1)

    def test_api_failure_keeps_partial_native_record(self):
        def fail(*args):
            raise RuntimeError("Synthetic provider failure")
        task = audit_task(demo_game("known"), {"attacker": get_model("mockllm/attacker", custom_outputs=fail)}, coverages=[0])
        with tempfile.TemporaryDirectory() as folder:
            log, path = self.run_task(task, folder)
            self.assertIsNotNone(log.samples[0].error)
            export_log(path, Path(folder)/"export.jsonl")
            row = json.loads((Path(folder)/"export.jsonl").read_text())
            self.assertEqual(row["status"], "error")
            self.assertNotIn("outcome", row["record"])

    def test_scripted_baselines_scored_by_real_environment(self):
        game = demo_game()
        for baseline in ("maximize", "abstain", "target_a", "target_b"):
            task = audit_task(game, {"attacker": mock_attacker(game, baseline)}, coverages=[0, 1])
            with tempfile.TemporaryDirectory() as folder:
                log, _ = self.run_task(task, folder)
                self.assertEqual(log.status, "success")
                self.assertEqual(len(log.samples), 4)
                for sample in log.samples:
                    row = sample.metadata["record"]
                    self.assertEqual(row["status"], "valid")
                    if baseline == "maximize":
                        self.assertEqual(row["regret"], "0")
                    else:
                        self.assertEqual(row["action"], baseline)

    def test_explicit_roles_and_strict_action_parser(self):
        with self.assertRaises(ValueError):
            audit_task(demo_game(), {})
        for text in ('{"q":true}', '{"q":2}', '{"q":"nan"}', '{"q":0,"private":"secret"}', '{"q":0,"q":1}'):
            with self.assertRaises(ValueError):
                parse_choice(text, "q")
        with self.assertRaises(ValueError):
            parse_choice('{"action":"cooperate"}', "action")


if __name__ == "__main__":
    unittest.main()

from decimal import Decimal as D
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from gut.oversight_experiment import (acknowledge_failure, collect, conditions, load_run,
    make_plan, observations, parse_choice, prompt, reservation, save_plan, synthetic)


MODEL = {"id": "synthetic/demo", "provider": "local", "returned_provider": "local",
         "accepted_models": ["synthetic/demo"], "context_length": 1000,
         "prompt_price": "0.00001", "completion_price": "0.0001", "request_price": "0"}


class OversightExperimentTests(unittest.TestCase):
    def plan(self, path, **changes):
        return save_plan(path, **{**dict(models=[MODEL], budget_usd="1", mode="synthetic",
                                        primary_reps=1, framing_reps=1), **changes})

    def test_frozen_design_labels_and_order(self):
        plan = make_plan([MODEL], "50")
        self.assertEqual(sum(j["stage"] == "main" for j in plan["jobs"]), 1220)
        self.assertEqual(sum(j["stage"] == "pilot" for j in plan["jobs"]), 4)
        for condition in conditions():
            texts = [prompt(condition, b) for b in range(4)]
            self.assertEqual(len(set(texts)), 4)
            for b, text in enumerate(texts):
                # Only the line order changes between blocks 0/1 or 2/3.
                lines = text.splitlines()
                if b%2:
                    self.assertEqual(lines[1:3], texts[b-1].splitlines()[1:3][::-1])
            self.assertNotIn("cooperate", texts[0]) if condition["framing"] == "neutral" else self.assertIn("cooperate", texts[0])

    def test_pilot_gate_collection_resume_and_exact_scoring(self):
        with TemporaryDirectory() as path:
            plan = self.plan(path)
            with self.assertRaises(ValueError):
                collect(path, stage="main")
            self.assertEqual(collect(path, max_calls=10)["attempted_now"], 4)
            self.assertEqual(collect(path, stage="main", max_calls=5)["attempted_now"], 5)
            self.assertEqual(collect(path, stage="main", max_calls=100)["attempted_now"], 51)
            self.assertEqual(collect(path, stage="main", max_calls=100)["attempted_now"], 0)
            _, rows = observations(path)
            self.assertEqual(len(rows), 56)
            self.assertTrue(all(r["status"] == "valid" and r["regret"] == "0" for r in rows))
            self.assertEqual(load_run(path)[3], 0)
            # Published compressed artifacts reproduce without permitting live append.
            for name in ("plan.json", "records.jsonl"):
                original = Path(path)/name
                (Path(path)/(name+".gz")).write_bytes(gzip.compress(original.read_bytes(), mtime=0))
                original.unlink()
            self.assertEqual(observations(path)[1], rows)
            with self.assertRaises(ValueError):
                collect(path)

    def test_strict_parsing_and_provider_identity(self):
        plan = make_plan([MODEL], "1", mode="synthetic", primary_reps=1, framing_reps=1)
        for block in range(4):
            job = next(j for j in plan["jobs"] if j["stage"] == "main" and j["block"] == block)
            status, body, error = synthetic(job, plan)
            finish = {"http_status": status, "body": body, "error": error}
            self.assertEqual(parse_choice(plan, job, finish)[1], "valid")
            for key, value, expected in (("provider", "other", "provider_mismatch"),
                                         ("model", "other", "model_mismatch")):
                changed = json.loads(body); changed[key] = value
                self.assertEqual(parse_choice(plan, job, {**finish, "body": json.dumps(changed)})[1], expected)
            changed = json.loads(body)
            changed["choices"][0]["message"]["content"] = '{"final_action":"A","final_action":"B"}'
            self.assertNotEqual(parse_choice(plan, job, {**finish, "body": json.dumps(changed)})[1], "valid")

    def test_reservations_enforce_cap_across_concurrency_and_resume(self):
        with TemporaryDirectory() as path:
            reserve = reservation(MODEL)
            self.plan(path, budget_usd=str(reserve*2))
            def charged(job, plan):
                status, body, error = synthetic(job, plan)
                response = json.loads(body); response["usage"]["cost"] = str(reserve)
                return status, json.dumps(response), error
            result = collect(path, max_calls=100, workers=8, transport=charged)
            self.assertEqual(result["attempted_now"], 2)
            self.assertEqual(result["stop"], "budget_cap")
            self.assertEqual(load_run(path)[3], reserve*2)
            self.assertEqual(collect(path, max_calls=100, transport=charged)["attempted_now"], 0)

    def test_missing_cost_retains_reservation_and_blocks_resume(self):
        with TemporaryDirectory() as path:
            self.plan(path)
            def no_cost(job, plan):
                status, body, error = synthetic(job, plan)
                response = json.loads(body); del response["usage"]
                return status, json.dumps(response), error
            collect(path, workers=1, transport=no_cost)
            plan, started, _, committed = load_run(path)
            self.assertEqual(committed, reservation(MODEL))
            with self.assertRaises(ValueError):
                collect(path)
            jid = next(iter(started))
            acknowledge_failure(path, jid, "Inspected missing cost; retain full reserve and do not retry this request.")
            collect(path, max_calls=1)
            self.assertEqual(len(load_run(path)[1]), 2)
            self.assertEqual(load_run(path)[3], reservation(MODEL))

    def test_identity_failure_with_known_cost_blocks_resume(self):
        with TemporaryDirectory() as path:
            self.plan(path)
            def wrong_provider(job, plan):
                status, body, error = synthetic(job, plan)
                response = json.loads(body); response["provider"] = "unexpected"
                return status, json.dumps(response), error
            collect(path, workers=1, transport=wrong_provider)
            with self.assertRaises(ValueError):
                collect(path)

    def test_plan_tampering_lock_and_invalid_prices(self):
        for price in ("-1", "NaN", "Infinity"):
            with self.assertRaises(ValueError):
                make_plan([{**MODEL, "request_price": price}], "50")
        with TemporaryDirectory() as path:
            plan = self.plan(path)
            lock = Path(path)/".collect.lock"; lock.write_text("other collector")
            with self.assertRaises(FileExistsError):
                collect(path)
            lock.unlink()
            plan["jobs"][0]["request"]["temperature"] = 1
            (Path(path)/"plan.json").write_text(json.dumps(plan))
            with self.assertRaises(ValueError):
                load_run(path)

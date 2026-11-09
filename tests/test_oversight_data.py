"""Audit the published study independently from the game/payoff scoring code."""
from collections import Counter
from decimal import Decimal
from fractions import Fraction
import gzip
from hashlib import sha256
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]/"data/oversight/2026-11-09"


class PublishedOversightTests(unittest.TestCase):
    def test_source_hashes_raw_choices_and_costs(self):
        for name, expected in json.loads((ROOT/"checksums.json").read_text()).items():
            self.assertEqual(sha256((ROOT/name).read_bytes()).hexdigest(), expected, name)
        plan = json.loads(gzip.decompress((ROOT/"plan.json.gz").read_bytes()))
        events = [json.loads(line) for line in gzip.decompress((ROOT/"records.jsonl.gz").read_bytes()).splitlines()]
        starts = {e["id"]: e for e in events if e["event"] == "started"}
        finishes = {e["id"]: e for e in events if e["event"] == "finished"}
        self.assertEqual(len(events), 7344)
        self.assertEqual(len(starts), len(finishes))
        self.assertEqual(set(starts), {j["id"] for j in plan["jobs"]})
        losses, totals, ids, cost = Counter(), Counter(), set(), Decimal(0)
        for job in plan["jobs"]:
            request = starts[job["id"]]["request"]
            self.assertEqual(request, job["request"])
            self.assertEqual(finishes[job["id"]]["http_status"], 200)
            response = json.loads(finishes[job["id"]]["body"])
            self.assertNotIn(response["id"], ids)
            ids.add(response["id"])
            cost += Decimal(str(response["usage"]["cost"]))
            chosen = json.loads(response["choices"][0]["message"]["content"])["final_action"]
            # Independently parse displayed numbers, without the game oracle,
            # action decoder or reporting code.
            displayed = dict(re.findall(r"Action ([AB])(?: \((?:cooperate|attack)\))?: your points = ([^;]+);",
                                        request["messages"][0]["content"]))
            self.assertEqual(set(displayed), {"A", "B"})
            values = {k: Fraction(v) for k, v in displayed.items()}
            if job["stage"] == "main":
                totals[job["model"]] += 1
                losses[job["model"]] += values[chosen] < max(values.values())
        provenance = json.loads((ROOT/"provenance.json").read_text())
        self.assertEqual(cost, Decimal(provenance["total_reported_cost_usd"]))
        summary = json.loads((ROOT/"analysis/summary.json").read_text())
        for row in summary["model_totals"]:
            self.assertEqual(row["planned"], totals[row["model"]])
            self.assertEqual(row["strict_disagreements"], losses[row["model"]])

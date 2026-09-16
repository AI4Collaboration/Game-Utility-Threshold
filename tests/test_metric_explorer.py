"""Run the shipped browser aggregator in Node and compare with Python truth."""

import json
from pathlib import Path
import shutil
import subprocess
import unittest

from utility_threshold.figure_data import OBJECTIVES, STRATA
from utility_threshold.research_metrics import build_metric_atlas, matrix

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node is needed to verify the browser aggregation")
class MetricExplorerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atlas = build_metric_atlas(
            json.loads((ROOT / "results/model_gameplay_replication_02.json").read_text()),
            json.loads((ROOT / "results/phase_one_model_eval_replication_02.json").read_text()),
        )
        cls.template = (ROOT / "scripts/metric_explorer.html").read_text()
        function = cls.template.split("function computeTable(settings) {", 1)[1].split("function fillMetrics()", 1)[0]
        cls.script = """
const fs = require('fs');
const {atlas,requests} = JSON.parse(fs.readFileSync(0,'utf8'));
const own = (object,key) => Object.prototype.hasOwnProperty.call(object,key);
const flattenLabel = label => label.replace(/\\n/g,' — ');
const strata = {broad_grid:'Broad grid',just_safe:'Just safe',exact_boundary:'Exact boundary',just_unsafe:'Just unsafe'};
function computeTable(settings) {""" + function + "\nprocess.stdout.write(JSON.stringify(requests.map(computeTable)));"

    def run_browser_aggregation(self, requests, atlas=None):
        result = subprocess.run([shutil.which("node"), "-e", self.script],
                                input=json.dumps(dict(atlas=atlas or self.atlas, requests=requests)),
                                capture_output=True, text=True, check=True, timeout=30)
        return json.loads(result.stdout)

    def request(self, metric, **changes):
        return dict(dataset="gameplay", metric=metric, group="model", objective="all", treatment="all", game="all") | changes

    def assert_table_matches_python(self, request, actual):
        expected = matrix(self.atlas["records"], request["metric"], by=request["group"],
                          objective=request["objective"], treatment=request["treatment"], game=request["game"])
        self.assertEqual(actual["rows"], [s.replace("\n", " — ") for s in expected["rows"]])
        self.assertEqual(actual["columns"], [s.replace("\n", " — ") for s in expected["columns"]])
        for i, row in enumerate(actual["values"]):
            for j, cell in enumerate(row):
                self.assertEqual(cell["n"], expected["counts"][i][j])
                self.assertEqual(cell["eligible"], expected["eligible"][i][j])
                value = expected["values"][i][j]
                if value is None:
                    self.assertIsNone(cell["mean"])
                else:
                    self.assertAlmostEqual(cell["mean"], value)

    def test_all_102_gameplay_tables_match_python(self):
        requests = [self.request(metric, group=group) for metric in self.atlas["metric_specs"]
                    for group in ("model", "treatment", "crossplay")]
        for request, result in zip(requests, self.run_browser_aggregation(requests)):
            with self.subTest(request=request):
                self.assert_table_matches_python(request, result)

    def test_all_objective_treatment_game_combinations(self):
        requests = [self.request("own_expected_regret", group="crossplay", objective=objective,
                                 treatment=treatment, game=game)
                    for objective in OBJECTIVES for treatment in self.atlas["labels"]["treatments"]
                    for game in self.atlas["labels"]["games"]]
        for request, result in zip(requests, self.run_browser_aggregation(requests)):
            self.assert_table_matches_python(request, result)
            self.assertEqual(result["matched"], 16)

    def test_phase_metrics_keep_unequal_stratum_weights(self):
        requests = [self.request(metric, dataset="phase") for metric in self.atlas["phase_metric_specs"]]
        for request, actual in zip(requests, self.run_browser_aggregation(requests)):
            self.assertEqual(actual["matched"], 156)
            for i, provider in enumerate(self.atlas["labels"]["models"]):
                rows = [r for r in self.atlas["phase_records"] if r["provider"] == provider]
                for j, stratum in enumerate(list(STRATA) + ["all"]):
                    values = [r["metrics"][request["metric"]] for r in rows if stratum in ("all", r["stratum"])]
                    self.assertAlmostEqual(actual["values"][i][j]["mean"], sum(values) / len(values))
                    self.assertEqual(actual["values"][i][j]["n"], len(values))

    def test_inapplicable_mechanism_is_not_zero(self):
        request = self.request("communication_honesty", treatment="baseline")
        result = self.run_browser_aggregation([request])[0]
        self.assertEqual(result["values"][-1][-1], dict(mean=None, n=0, eligible=256))

    def test_missing_role_override_does_not_fall_back_to_joint_mean(self):
        request = self.request("declared_confidence")
        result = self.run_browser_aggregation([request])[0]
        self.assert_table_matches_python(request, result)
        self.assertLess(result["values"][-1][-1]["n"], result["values"][-1][-1]["eligible"])

    def test_objective_controls_use_real_condition_keys(self):
        for objective in OBJECTIVES:
            self.assertIn(f'value="{objective}"', self.template)
        self.assertNotIn("fetch(", self.template)
        self.assertNotIn("https://", self.template)


if __name__ == "__main__":
    unittest.main()

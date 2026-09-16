"""Integrity checks for the checked-in, downloadable research deliverable."""

import csv
import hashlib
import json
from pathlib import Path
import re
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "results/figures/replication_02"


class ResearchFigurePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((OUTPUT / "manifest.json").read_text())
        cls.atlas = json.loads((OUTPUT / "metric_atlas.json").read_text())

    def test_source_and_artifact_checksums_are_current(self):
        for source in self.manifest["sources"]:
            self.assertEqual(hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest(), source["sha256"], source["path"])
        for name, digest in self.manifest["artifacts"].items():
            self.assertEqual(hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest(), digest, name)

    def test_bundle_contains_all_28_figures_and_exact_artifact_bytes(self):
        self.assertEqual(len(self.manifest["figures"]), 28)
        with zipfile.ZipFile(OUTPUT / "research-figures.zip") as archive:
            expected = set(self.manifest["artifacts"]) | {"manifest.json"}
            self.assertEqual(set(archive.namelist()), expected)
            for name in expected:
                self.assertEqual(archive.read(name), (OUTPUT / name).read_bytes(), name)

    def test_csv_preserves_all_values_and_denominators(self):
        with (OUTPUT / "all_metric_matrices.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        expected_count = sum(len(t["rows"]) * len(t["columns"]) for t in self.atlas["matrices"].values())
        self.assertEqual(len(rows), expected_count)
        for row in rows:
            table = self.atlas["matrices"][row["grouping"] + ":" + row["metric"]]
            i = table["rows"].index(row["row"])
            j = [c.replace("\n", " — ") for c in table["columns"]].index(row["column"])
            self.assertEqual(int(row["available_n"]), table["counts"][i][j])
            self.assertEqual(int(row["eligible_n"]), table["eligible"][i][j])
            value = table["values"][i][j]
            if value is None:
                self.assertEqual(row["mean"], "")
            else:
                self.assertEqual(float(row["mean"]), value)

    def test_embedded_explorer_data_matches_numeric_export(self):
        page = (OUTPUT / "metric_explorer.html").read_text()
        embedded = re.search(r'<script id="atlas-data" type="application/json">(.*?)</script>', page, re.S).group(1)
        decoded = json.loads(embedded)
        self.assertEqual(set(decoded), {"metric_specs", "phase_metric_specs", "labels", "records", "phase_records"})
        for key, value in decoded.items():
            self.assertEqual(value, self.atlas[key])
        self.assertNotRegex(page, r"sk-or-v1-[a-zA-Z0-9]{20,}")
        self.assertNotIn("__ATLAS_DATA__", page)


if __name__ == "__main__":
    unittest.main()

"""Reproduce the post from raw choices and protect its planned denominator."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from gut.study import DATA_DIR, load_study, validate_records


class StudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = [json.loads(line) for line in gzip.decompress(
            (DATA_DIR / "records.jsonl.gz").read_bytes()).splitlines()]
        cls.blocks = [json.loads((DATA_DIR / f"block-{rep}.json").read_text()) for rep in (0, 1)]
        cls.study = load_study()

    def changed_record(self, change):
        records = list(self.records)
        records[0] = deepcopy(records[0])
        change(records[0])
        return records

    def test_post_totals_and_strict_dominance(self):
        summary = self.study.summary()
        expected = {"planned_games": 1352, "valid_games": 1350, "excluded_games": 2,
                    "planned_decisions": 2704, "recorded_decisions": 2704,
                    "valid_decisions": 2702, "invalid_decisions": 2,
                    "paired_decisions": 2700, "excluded_valid_decisions": 2,
                    "dominance_correct": 1277, "dominance_decisions": 1280,
                    "CC": 954, "CD": 57, "DC": 59, "DD": 280, "C_choices": 2024}
        for key, value in expected.items():
            with self.subTest(key=key):
                self.assertEqual(summary[key], value)
        self.assertEqual(summary["dominance_rate"], 1277 / 1280)
        self.assertEqual([summary["by_model"][m]["valid_games"] for m in ("glm", "qwen", "astra", "fable")],
                         [337, 338, 338, 337])

    def test_post_region_rates_use_complete_pairs(self):
        regions = {(r["model_key"], r["region"]): r for r in self.study.regions()}
        for model, region, numerator in [("qwen", "stag_hunt", 51), ("qwen", "chicken", 93),
                                         ("fable", "stag_hunt", 102), ("fable", "chicken", 114)]:
            row = regions[model, region]
            self.assertEqual(row["C_choices"], numerator)
            self.assertEqual(row["paired_decisions"], 128)
            self.assertEqual(row["cooperation_rate"], numerator / 128)
        self.assertEqual(regions["glm", "chicken"]["paired_decisions"], 126)
        self.assertEqual(regions["fable", "boundary"]["paired_decisions"], 98)

    def test_cells_retain_both_label_blocks_and_failures(self):
        cells = self.study.cells()
        self.assertEqual(len(cells), 4 * 13 * 13)
        self.assertTrue(all(c["planned_games"] == 2 for c in cells))
        self.assertEqual(sum(c["valid_games"] for c in cells), 1350)
        self.assertEqual(sum(c["excluded_games"] for c in cells), 2)
        invalid = [g for g in self.study.games if not g.valid]
        self.assertEqual({(g.model_key, g.s, g.t, g.replicate) for g in invalid},
                         {("glm", 0.25, 1.25, 0), ("fable", 0, 1, 1)})
        self.assertTrue(all(g.row_action is None and g.column_action in ("C", "D") for g in invalid))

    def test_missing_or_duplicate_record_rejected(self):
        for records in (self.records[:-1], self.records + self.records[:1]):
            with self.assertRaises(ValueError):
                validate_records(records, self.blocks)

    def test_manifest_cannot_silently_drop_a_pair(self):
        blocks = deepcopy(self.blocks)
        blocks[0]["job_ids"].pop()
        with self.assertRaisesRegex(ValueError, "manifest"):
            validate_records(self.records, blocks)

    def test_pair_identity_payoffs_labels_and_prompt_must_agree(self):
        mutations = [lambda r: r.update(role="column"),
                     lambda r: r.update(model="another/model"),
                     lambda r: r["case"].update(replicate=1),
                     lambda r: r["case"]["payoffs"].update(S=-0.125),
                     lambda r: r.update(label_mapping={"C": "B", "D": "A"}),
                     lambda r: r["request"]["messages"][0].update(content="changed matrix"),
                     lambda r: r["request"].update(reasoning={"effort": "high"}),
                     lambda r: r["response"].update(model="another/model")]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_records(self.changed_record(mutation), self.blocks)

    def test_invalid_partner_is_not_invented_or_scored_as_defection(self):
        records = self.changed_record(lambda r: r["response"]["choices"][0]["message"].update(content="not JSON"))
        summary = validate_records(records, self.blocks).summary()
        self.assertEqual(summary["planned_games"], 1352)
        self.assertEqual(summary["valid_games"], 1349)
        self.assertEqual(summary["invalid_decisions"], 3)
        self.assertEqual(summary["paired_decisions"], 2698)
        self.assertEqual(summary["excluded_valid_decisions"], 3)

    def test_archived_action_and_derived_scores_are_not_trusted(self):
        def alter_cached_fields(record):
            record["decision"] = {"action": "invented", "valid": False}
            record["case"]["payoffs"]["regime"] = "invented"
            record["case"]["payoffs"]["strict_pd"] = False
        replay = validate_records(self.changed_record(alter_cached_fields), self.blocks)
        self.assertEqual(replay.summary(), self.study.summary())

    def test_ambiguous_json_response_remains_invalid(self):
        records = self.changed_record(lambda r: r["response"]["choices"][0]["message"].update(
            content='{"final_action":"A","final_action":"B"}'))
        self.assertEqual(validate_records(records, self.blocks).summary()["invalid_decisions"], 3)

    def test_changed_source_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name in ("manifest.json", "block-0.json", "block-1.json", "records.jsonl.gz"):
                shutil.copyfile(DATA_DIR / name, directory / name)
            with (directory / "records.jsonl.gz").open("ab") as handle:
                handle.write(b"changed")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load_study(directory)


if __name__ == "__main__":
    unittest.main()

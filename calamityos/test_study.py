import csv
import json
import tempfile
import unittest
from pathlib import Path

from calamityos import study


class StudyProtocolTest(unittest.TestCase):
    def test_prepare_freeze_and_score(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/"study"
            study.prepare(root)
            items = json.loads((root/"vignettes.json").read_text())
            self.assertEqual(len({item["id"] for item in items}), 80)
            self.assertEqual(len({item["template"] for item in items}), 16)
            with self.assertRaises(ValueError):
                study.freeze(root)
            # Deliberately wrong fixture labels verify scoring without using
            # the candidate pipeline to author a gold standard.
            for name in ("annotator1","annotator2","reconciled"):
                with (root/f"{name}.csv").open("w", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=["id","answer"])
                    writer.writeheader()
                    writer.writerows({"id":item["id"],"answer":"incorrect_fixture"} for item in items)
            study.freeze(root)
            study.pipeline(root)
            result = study.score(root)
            self.assertEqual(result["independent_agreement"], 80)
            self.assertEqual(result["systems"]["P"]["total"], 400)
            self.assertEqual(result["systems"]["P"]["correct"], 0)
            self.assertEqual(result["systems"]["P"]["accuracy_95pct_template_cluster_bootstrap"], [0,0])
            (root/"annotator1.csv").write_text("tampered")
            with self.assertRaises(ValueError):
                study.score(root)

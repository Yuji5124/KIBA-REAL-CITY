import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class OSMBuildPipelineTests(unittest.TestCase):
    def test_retained_snapshot_build_and_edit_diff_survives_regeneration(self):
        output = ROOT / "phase5a/processed/viewer_features.json"
        self.assertTrue(output.is_file(), "Run phase5a/scripts/build_feature_data.py before this test")
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["crs"], "EPSG:6677")
        self.assertEqual(data["threeAxes"], "X=east, Y=up, Z=-north")
        self.assertEqual((len(data["roads"]), len(data["trees"]), len(data["vegetation"])), (334, 43, 27))
        ids = [f["featureId"] for group in (data["roads"], data["trees"], data["vegetation"]) for f in group]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(data["terrain"]["status"], "BLOCKED")
        for item in data["trees"]:
            self.assertIsNone(item["height"])
            self.assertIsNone(item["species"])

        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / "phase5a"
            command = [sys.executable, str(ROOT / "phase5a/scripts/build_feature_data.py"), "--output", str(output_dir)]
            subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
            edits_path = output_dir / "edits/edits.json"
            edits = json.loads(edits_path.read_text(encoding="utf-8"))
            feature = json.loads((output_dir / "processed/viewer_features.json").read_text(encoding="utf-8"))["trees"][0]
            edits["edits"][feature["featureId"]] = {"baseFeatureHash": feature["sourceHash"], "set": {"height": 7.0}}
            edits_path.write_text(json.dumps(edits), encoding="utf-8")
            subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
            after = json.loads(edits_path.read_text(encoding="utf-8"))
            self.assertEqual(after["edits"][feature["featureId"]]["set"]["height"], 7.0)


if __name__ == "__main__":
    unittest.main()

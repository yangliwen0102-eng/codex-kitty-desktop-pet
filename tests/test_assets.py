from __future__ import annotations

import json
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
GENERATED = ROOT / "assets" / "generated"


class GeneratedAssetTests(unittest.TestCase):
    def test_validation_and_manifest(self) -> None:
        manifest = json.loads(
            (GENERATED / "asset-manifest.json").read_text(encoding="utf-8")
        )
        self.assertTrue(manifest["sourceOnly"])
        self.assertEqual(manifest["canvas"], [320, 320])
        self.assertEqual(
            set(manifest["states"]),
            {
                "idle",
                "hover",
                "dragging",
                "working",
                "bored",
                "permission",
                "completed",
                "failed",
                "closing",
            },
        )
        expected_scales = {
            "idle": 0.72,
            "hover": 0.78,
            "working": 0.76,
            "permission": 0.74,
            "failed": 0.76,
        }
        for state_name, expected in expected_scales.items():
            self.assertEqual(manifest["states"][state_name]["sourceScale"], expected)

    def test_all_frames_are_transparent_rgba(self) -> None:
        manifest = json.loads(
            (GENERATED / "asset-manifest.json").read_text(encoding="utf-8")
        )
        for state in manifest["states"].values():
            self.assertEqual(len(state["frames"]), len(state["durationsMs"]))
            for relative_path in state["frames"]:
                image = Image.open(GENERATED / relative_path)
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (320, 320))
                self.assertEqual(image.getchannel("A").getextrema()[0], 0)


if __name__ == "__main__":
    unittest.main()

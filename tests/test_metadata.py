"""Tests for release metadata consistency."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


class MetadataTest(unittest.TestCase):
    def test_manifest_and_const_versions_match_release_version(self) -> None:
        manifest = json.loads(
            Path("custom_components/commax_iot/manifest.json").read_text()
        )
        const_py = Path("custom_components/commax_iot/const.py").read_text()

        self.assertEqual(manifest["version"], "2026.7.22")
        self.assertIn('VERSION = "2026.7.22"', const_py)


if __name__ == "__main__":
    unittest.main()

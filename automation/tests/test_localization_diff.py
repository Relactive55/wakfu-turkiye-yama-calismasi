from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from automation.update_wakfu_localization import diff, property_records, snapshot


class LocalizationDiffTests(unittest.TestCase):
    def test_duplicate_keys_are_retained_by_occurrence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            jar = Path(temp) / "source.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("texts_en.properties", "same=first\nsame=second\n")
                archive.writestr("texts_en_cleaned.properties", "same=third\n")
            records = property_records(jar)
            self.assertEqual(records["texts_en.properties:same#1"], "first")
            self.assertEqual(records["texts_en.properties:same#2"], "second")
            self.assertEqual(records["texts_en_cleaned.properties:same#1"], "third")
            before = snapshot(jar, "1.92.1", "a" * 40)
            records["texts_en.properties:same#2"] = "changed"
            after = dict(before)
            after["records"] = dict(before["records"])
            after["records"]["texts_en.properties:same#2"] = "different"
            report = diff(before, after)
            self.assertEqual(report["MODIFIED"], ["texts_en.properties:same#2"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from automation.release_pipeline import build_test_fixture
from automation.release_validation import ReleaseValidationError, validate_release


class ReleaseValidationTests(unittest.TestCase):
    def test_fixture_manifest_and_properties_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "release"
            result = build_test_fixture(output_dir=output, game_version="6.0_1.92.1.5172.314", patch_version="2026.09.05.1")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["size"], (output / "i18n.jar").stat().st_size)

    def test_duplicate_order_or_missing_record_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.jar"
            patch = root / "patch.jar"
            manifest_dir = root / "release"
            build_test_fixture(output_dir=manifest_dir, game_version="1.92.1.5172.314", patch_version="2026.09.05.1")
            with zipfile.ZipFile(source, "w") as archive, zipfile.ZipFile(manifest_dir / "i18n.jar") as original:
                for name in original.namelist():
                    text = original.read(name).decode("utf-8")
                    archive.writestr(name, text)
            with zipfile.ZipFile(patch, "w") as archive:
                archive.writestr("texts_en.properties", "fixture.unchanged=changed\n")
                archive.writestr("texts_en_cleaned.properties", "fixture.unchanged=changed\n")
            with self.assertRaises(ReleaseValidationError):
                validate_release(source_jar=source, patch_jar=patch, manifest_path=manifest_dir / "manifest.json", game_version="1.92.1.5172.314", patch_version="2026.09.05.1")


if __name__ == "__main__":
    unittest.main()

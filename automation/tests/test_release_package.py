from __future__ import annotations

import json
import zipfile
from pathlib import Path

import tempfile
import unittest

from automation.release_package import build_release_assets, sha256


def jar(path: Path, main: str = "english") -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("texts_en.properties", "key=" + main + "\n")
        archive.writestr("texts_en_cleaned.properties", "key=" + main + "\n")


class ReleasePackageTests(unittest.TestCase):
    def test_release_assets_include_hash_size_and_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, patch, output = root / "source.jar", root / "patch.jar", root / "release"
            jar(source, "English")
            jar(patch, "Türkçe")
            manifest = build_release_assets(patch_jar=patch, source_jar=source, game_version="1.92.1.5172.314", patch_version="2026.09.05.2", output_dir=output)
            persisted = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted, manifest)
            self.assertEqual(persisted["sha256"], sha256(output / "i18n.jar"))
            self.assertEqual(persisted["source_i18n_sha256"], sha256(source))
            self.assertEqual(persisted["size"], (output / "i18n.jar").stat().st_size)

    def test_release_versions_fail_closed(self) -> None:
        for game, patch_version in (("v1", "2026.09.05.2"), ("1.92", "2026-09-05")):
            with tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                source, payload = root / "source.jar", root / "patch.jar"
                jar(source)
                jar(payload)
                with self.assertRaises(ValueError):
                    build_release_assets(patch_jar=payload, source_jar=source, game_version=game, patch_version=patch_version, output_dir=root / "out")


if __name__ == "__main__":
    unittest.main()

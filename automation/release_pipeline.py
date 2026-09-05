"""Deterministic release-package helpers used by the guarded workflow.

The ``--test-fixture`` mode is deliberately small and self-contained.  It is
for a pre-release smoke test only; it never reads or writes production
translation memory, state, baseline, or a game installation.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from .release_package import build_release_assets
from .release_validation import validate_release


def _write_jar(path: Path, rows: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in ("texts_en.properties", "texts_en_cleaned.properties"):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, "\n".join(rows) + "\n")


def build_test_fixture(*, output_dir: Path, game_version: str, patch_version: str) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="wakfu-release-fixture-") as temp:
        root = Path(temp)
        source = root / "source.jar"
        patch = root / "patch.jar"
        _write_jar(source, [
            "fixture.unchanged=Hello adventurer.",
            r"fixture.placeholder=You have [#1] items.",
            "fixture.tag=<b>Damage</b>",
            r"fixture.conditional={[condition]?Yes:No}",
        ])
        _write_jar(patch, [
            "fixture.unchanged=Merhaba maceracı.",
            r"fixture.placeholder= [#1] eşyan var.",
            "fixture.tag=<b>Hasar</b>",
            r"fixture.conditional={[condition]?Evet:Hayır}",
        ])
        manifest = build_release_assets(patch_jar=patch, source_jar=source, game_version=game_version, patch_version=patch_version, output_dir=output_dir)
        result = validate_release(source_jar=source, patch_jar=output_dir / "i18n.jar", manifest_path=output_dir / "manifest.json", game_version=game_version, patch_version=patch_version)
        result["fixture"] = True
        result["source_sha256"] = manifest["source_i18n_sha256"]
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-fixture", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--patch-version", required=True)
    args = parser.parse_args()
    if not args.test_fixture:
        parser.error("only --test-fixture is available locally; production build is guarded by the workflow")
    result = build_test_fixture(output_dir=args.output_dir, game_version=args.game_version, patch_version=args.patch_version)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

"""Build the two immutable GitHub Release assets from a validated patch.

This module never publishes a Release.  The workflow is responsible for the
human-approved publishing boundary; this code only produces deterministic,
hash-addressed assets for that boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import zipfile
from pathlib import Path

from .state import atomic_json_write

PATCH_VERSION = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d+$")
GAME_VERSION = re.compile(r"^\d+(?:\.\d+){1,10}$")
REQUIRED_ENTRIES = ("texts_en.properties", "texts_en_cleaned.properties")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_i18n_jar(path: Path) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError(f"missing or empty i18n JAR: {path}")
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"invalid i18n JAR: {path}") from exc
    missing = [name for name in REQUIRED_ENTRIES if name not in names]
    if missing:
        raise ValueError("i18n JAR lacks required entries: " + ", ".join(missing))


def build_release_assets(*, patch_jar: Path, source_jar: Path, game_version: str, patch_version: str, output_dir: Path) -> dict[str, object]:
    if not GAME_VERSION.fullmatch(game_version):
        raise ValueError("game_version must be numeric dot-separated version text")
    if not PATCH_VERSION.fullmatch(patch_version):
        raise ValueError("patch_version must be YYYY.MM.DD.N")
    verify_i18n_jar(patch_jar)
    verify_i18n_jar(source_jar)
    output_dir.mkdir(parents=True, exist_ok=True)
    staged = output_dir / "i18n.jar.part"
    final = output_dir / "i18n.jar"
    shutil.copyfile(patch_jar, staged)
    if sha256(staged) != sha256(patch_jar):
        staged.unlink(missing_ok=True)
        raise ValueError("staged i18n JAR hash mismatch")
    staged.replace(final)
    manifest: dict[str, object] = {
        "game_version": game_version,
        "patch_version": patch_version,
        "file": "i18n.jar",
        "sha256": sha256(final),
        "size": final.stat().st_size,
        # Required by Setup EXE before it can apply a patch to a game folder.
        "source_i18n_sha256": sha256(source_jar),
    }
    atomic_json_write(output_dir / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--patch-jar", type=Path, required=True)
    parser.add_argument("--source-jar", type=Path, required=True)
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--patch-version", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_release_assets(
        patch_jar=args.patch_jar,
        source_jar=args.source_jar,
        game_version=args.game_version,
        patch_version=args.patch_version,
        output_dir=args.output_dir,
    )
    print("RELEASE_ASSETS_OK|{patch_version}|{sha256}".format(**manifest))


if __name__ == "__main__":
    main()

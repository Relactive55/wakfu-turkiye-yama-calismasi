"""Fail-closed validation for the two files published by a WAKFU Release.

The production workflow builds from a freshly verified Ankama source JAR and
then runs this module before publishing anything.  It intentionally validates
the source/patch properties as ordered records, not as a normal dictionary;
that preserves duplicate-key occurrence and Java's last-occurrence semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

# Reuse the production audit's formatter so conditional branches are checked
# structurally while their human-readable words may be translated.
from Kaynak_Kodu.wakfu_audit import format_ok

ENTRIES = ("texts_en.properties", "texts_en_cleaned.properties")
GAME_VERSION = re.compile(r"^\d+(?:\.\d+){1,10}(?:_\d+(?:\.\d+){1,10})?$")
PATCH_VERSION = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.(?:0|[1-9]\d*)$")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class ReleaseValidationError(ValueError):
    """A release input is not safe to publish."""


def _digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_properties(archive: zipfile.ZipFile, entry: str) -> tuple[list[tuple[str, str]], list[str]]:
    try:
        raw = archive.read(entry)
    except KeyError as exc:
        raise ReleaseValidationError(f"missing required JAR entry: {entry}") from exc
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ReleaseValidationError(f"{entry} is not valid UTF-8") from exc
    records: list[tuple[str, str]] = []
    identities: list[str] = []
    occurrences: dict[str, int] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line or line.startswith(("#", "!")):
            continue
        if "=" not in line:
            raise ReleaseValidationError(f"malformed properties line {entry}:{line_number}")
        key, value = line.split("=", 1)
        if not key:
            raise ReleaseValidationError(f"empty properties key {entry}:{line_number}")
        occurrences[key] = occurrences.get(key, 0) + 1
        identity = f"{entry}:{key}#{occurrences[key]}"
        identities.append(identity)
        records.append((identity, value))
    return records, identities


def _jar_records(path: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ReleaseValidationError(f"missing or empty JAR: {path}")
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReleaseValidationError(f"invalid JAR: {path}") from exc
    try:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ReleaseValidationError(f"duplicate ZIP entry in {path}")
        values: dict[str, str] = {}
        order: dict[str, list[str]] = {}
        for entry in ENTRIES:
            rows, identities = _read_properties(archive, entry)
            order[entry] = identities
            values.update(dict(rows))
        return values, order
    finally:
        archive.close()


def validate_manifest(manifest_path: Path, *, jar_path: Path, source_jar: Path, game_version: str, patch_version: str, release_tag: str | None = None) -> dict[str, object]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseValidationError("manifest.json could not be read") from exc
    if not isinstance(manifest, dict):
        raise ReleaseValidationError("manifest.json must be an object")
    required = {"game_version", "patch_version", "file", "sha256", "size", "source_i18n_sha256"}
    if not required.issubset(manifest):
        raise ReleaseValidationError("manifest.json is missing required fields")
    if manifest["game_version"] != game_version or not isinstance(game_version, str) or not GAME_VERSION.fullmatch(game_version):
        raise ReleaseValidationError("manifest game_version does not match the approved source")
    if manifest["patch_version"] != patch_version or not isinstance(patch_version, str) or not PATCH_VERSION.fullmatch(patch_version):
        raise ReleaseValidationError("manifest patch_version does not match the requested patch")
    if manifest["file"] != "i18n.jar":
        raise ReleaseValidationError("manifest file must be i18n.jar")
    if not isinstance(manifest["sha256"], str) or not SHA256.fullmatch(manifest["sha256"]):
        raise ReleaseValidationError("manifest sha256 is invalid")
    if not isinstance(manifest["source_i18n_sha256"], str) or not SHA256.fullmatch(manifest["source_i18n_sha256"]):
        raise ReleaseValidationError("manifest source_i18n_sha256 is invalid")
    if not isinstance(manifest["size"], int) or manifest["size"] <= 0:
        raise ReleaseValidationError("manifest size is invalid")
    if release_tag is not None and release_tag != f"tr-{patch_version}":
        raise ReleaseValidationError("stable Release tag does not match patch_version")
    if manifest["size"] != jar_path.stat().st_size:
        raise ReleaseValidationError("manifest size does not match i18n.jar")
    if manifest["sha256"].lower() != _digest(jar_path, "sha256"):
        raise ReleaseValidationError("manifest SHA-256 does not match i18n.jar")
    if manifest["source_i18n_sha256"].lower() != _digest(source_jar, "sha256"):
        raise ReleaseValidationError("manifest source SHA-256 does not match source JAR")
    return manifest


def validate_translation(*, source_jar: Path, patch_jar: Path) -> dict[str, int]:
    source, source_order = _jar_records(source_jar)
    patch, patch_order = _jar_records(patch_jar)
    if source_order != patch_order:
        raise ReleaseValidationError("properties order or duplicate-key occurrence structure changed")
    if set(source) != set(patch):
        missing = sorted(set(source) - set(patch))
        extra = sorted(set(patch) - set(source))
        raise ReleaseValidationError(f"properties records differ; missing={missing[:3]} extra={extra[:3]}")
    changed = 0
    for identity, source_value in source.items():
        target = patch[identity]
        if not target.strip() and source_value.strip():
            raise ReleaseValidationError(f"empty translation: {identity}")
        if not format_ok(source_value, target):
            raise ReleaseValidationError(f"placeholder/tag mismatch: {identity}")
        if source_value != target:
            changed += 1
    return {"records": len(source), "changed": changed}


def validate_release(*, source_jar: Path, patch_jar: Path, manifest_path: Path, game_version: str, patch_version: str, release_tag: str | None = None) -> dict[str, object]:
    manifest = validate_manifest(manifest_path, jar_path=patch_jar, source_jar=source_jar, game_version=game_version, patch_version=patch_version, release_tag=release_tag)
    records = validate_translation(source_jar=source_jar, patch_jar=patch_jar)
    return {"status": "PASS", "manifest": manifest, "translation": records, "sha256": manifest["sha256"], "size": manifest["size"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-jar", type=Path, required=True)
    parser.add_argument("--patch-jar", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--patch-version", required=True)
    parser.add_argument("--release-tag")
    args = parser.parse_args()
    result = validate_release(source_jar=args.source_jar, patch_jar=args.patch_jar, manifest_path=args.manifest, game_version=args.game_version, patch_version=args.patch_version, release_tag=args.release_tag)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

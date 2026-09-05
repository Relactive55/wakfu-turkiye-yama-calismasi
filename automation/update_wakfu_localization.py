"""Read-only-first Ankama localization baseline and diff inspector.

It preserves duplicate properties keys by addressing every record as
``key#occurrence``.  A first dry-run never creates a baseline: it verifies the
operator-supplied local source against the CDN manifest and stops.  Therefore
the automation cannot silently guess which game build the existing translation
memory belongs to.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from .ankama_cdn import AnkamaCdnClient
from .errors import AutomationError, VerificationError
from .state import atomic_json_write, read_json

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.json"
SNAPSHOTS = ROOT / "snapshots"
ENTRIES = ("texts_en.properties", "texts_en_cleaned.properties")


def sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def property_records(jar: Path) -> dict[str, str]:
    records: dict[str, str] = {}
    with zipfile.ZipFile(jar) as archive:
        for entry in ENTRIES:
            with archive.open(entry) as handle:
                counts: dict[str, int] = {}
                for raw in handle.read().decode("utf-8-sig").splitlines():
                    if not raw or raw.startswith(("#", "!")) or "=" not in raw:
                        continue
                    key, value = raw.split("=", 1)
                    occurrence = counts.get(key, 0) + 1
                    counts[key] = occurrence
                    # Prefix with ZIP entry so duplicate keys across the two
                    # properties files cannot overwrite each other either.
                    records[f"{entry}:{key}#{occurrence}"] = value
    return records


def snapshot(jar: Path, version: str, manifest_sha1: str) -> dict[str, object]:
    records = property_records(jar)
    per_entry: dict[str, dict[str, int]] = {}
    occurrences: dict[tuple[str, str], int] = {}
    for identity in records:
        entry, key_occurrence = identity.split(":", 1)
        key, occurrence_text = key_occurrence.rsplit("#", 1)
        occurrence = int(occurrence_text)
        occurrences[(entry, key)] = occurrence
        per_entry.setdefault(entry, {"records": 0, "duplicate_keys": 0, "duplicate_occurrences": 0})["records"] += 1
    for (entry, _key), count in occurrences.items():
        if count > 1:
            per_entry[entry]["duplicate_keys"] += 1
            per_entry[entry]["duplicate_occurrences"] += count - 1
    return {
        "schema": 1,
        "game_version": version,
        "source_sha1": manifest_sha1,
        "properties_metadata": {"entries": per_entry, "identity": "<zip-entry>:<key>#<one-based-occurrence>", "java_effective_value": "last occurrence for a key within each properties entry"},
        "records": {key: hashlib.sha256(value.encode("utf-8")).hexdigest() for key, value in records.items()},
    }


def diff(previous: dict[str, object], current: dict[str, object]) -> dict[str, list[str]]:
    old = previous["records"]
    new = current["records"]
    assert isinstance(old, dict) and isinstance(new, dict)
    return {
        "NEW": sorted(set(new) - set(old)),
        "MODIFIED": sorted(key for key in set(new) & set(old) if new[key] != old[key]),
        "REMOVED": sorted(set(old) - set(new)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--accept-baseline", action="store_true", help="explicitly save a verified first snapshot")
    parser.add_argument("--local-source-jar", type=Path, help="existing local i18n_en.jar for first baseline verification")
    args = parser.parse_args()
    if args.dry_run and args.accept_baseline:
        parser.error("--dry-run and --accept-baseline cannot be used together")
    client = AnkamaCdnClient()
    version = client.latest_version()
    entry, _ = client.target_entry(version)
    state = read_json(STATE_PATH, default=None)
    if state is None:
        if args.local_source_jar is None or not args.local_source_jar.is_file():
            raise VerificationError("BASELINE_REQUIRED: first dry-run needs --local-source-jar; no state or snapshot was written")
        # Download the exact CDN file even on the first dry-run.  The client
        # verifies every range/chunk and the assembled SHA-1; neither a
        # manifest claim nor a local file hash alone is trusted as baseline.
        with tempfile.TemporaryDirectory(prefix="wakfu-cdn-first-dry-run-") as temporary:
            downloaded = Path(temporary) / "i18n_en.jar"
            client.download_localization(version, downloaded)
            if sha1(args.local_source_jar) != entry.sha1 or sha1(downloaded) != entry.sha1:
                raise VerificationError("BASELINE_MISMATCH: local i18n_en.jar does not match the verified current CDN localization; no baseline was written")
            current = snapshot(downloaded, version, entry.sha1)
        report = {"status": "BASELINE_VERIFIED_NOT_WRITTEN", "game_version": version, "source_sha1": entry.sha1, "records": len(current["records"])}
        if args.accept_baseline:
            SNAPSHOTS.mkdir(parents=True, exist_ok=True)
            snap_path = SNAPSHOTS / f"{version}.json"
            atomic_json_write(snap_path, current)
            atomic_json_write(STATE_PATH, {"schema": 1, "baseline": str(snap_path.relative_to(ROOT)).replace("\\", "/"), "game_version": version, "source_sha1": entry.sha1})
            report["status"] = "BASELINE_SAVED"
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return
    baseline_name = state.get("baseline") if isinstance(state, dict) else None
    if not isinstance(baseline_name, str):
        raise AutomationError("state.json baseline pointer is invalid")
    baseline_path = ROOT / baseline_name
    previous = read_json(baseline_path, default=None)
    if not isinstance(previous, dict):
        raise AutomationError("baseline snapshot is missing or invalid")
    with tempfile.TemporaryDirectory(prefix="wakfu-cdn-dry-run-") as temporary:
        downloaded = Path(temporary) / "i18n_en.jar"
        client.download_localization(version, downloaded)
        current = snapshot(downloaded, version, entry.sha1)
        report = {"status": "DIFF_ONLY", "game_version": version, "source_sha1": entry.sha1, "diff": diff(previous, current)}
    # This command is deliberately read-only. Translation, validation and PR
    # creation are a later, separately reviewed write stage.
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

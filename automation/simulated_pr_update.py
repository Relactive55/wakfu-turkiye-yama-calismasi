"""Produce a review-only simulated localization update for the PR pipeline.

The fixture is deliberately isolated from the production translation memory,
baseline snapshot and state file.  It still executes the same duplicate-aware
diff, translation-provider priority, placeholder validation and JAR build
helpers that the production update path uses.  Only small text/JSON artifacts
are written to the caller-provided fixture directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path

from .argos_engine import install_locked_model
from .localization_pipeline import (
    ENTRIES,
    diff_records,
    format_ok,
    records_from_jar,
    resolve_changes,
    validate_proposals,
)
from .release_package import build_release_assets, verify_i18n_jar


ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA256 = "2d553a00880a0c21dea5b1c375535659e6bf18c9bf2ce9847c2a2fd2ff50316a"
GAME_VERSION = "1.92.1.5172.314"
PATCH_VERSION = "2026.09.05.1"


VERSION_A_MAIN = """# simulated WAKFU version A
fixture.unchanged=Same unchanged text
fixture.tm=Old [#1] items
fixture.argos=Old greeting
fixture.duplicate=First duplicate
fixture.duplicate=Second duplicate
fixture.removed=Removed from the game
"""

VERSION_B_MAIN = """# simulated WAKFU version B
fixture.unchanged=Same unchanged text
fixture.tm=New [#1] items
fixture.argos=Hello adventurer.
fixture.duplicate=Second duplicate
fixture.duplicate=First duplicate
fixture.glossary=Damage <b>value</b>
"""


def _write_jar(path: Path, main: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("texts_en.properties", main.encode("utf-8"))
        archive.writestr("texts_en_cleaned.properties", b"")


def _load_translation_data() -> tuple[dict[str, str], dict[str, str], tuple[dict, dict, dict]]:
    data_dir = ROOT / "Ceviri_Verileri"
    translations = json.loads((data_dir / "wakfu_tr_ceviri.json").read_text(encoding="utf-8-sig"))
    manual = json.loads((data_dir / "manual_repairs_v23.json").read_text(encoding="utf-8-sig"))
    glossary = json.loads((data_dir / "terim_duzeltmeleri.json").read_text(encoding="utf-8-sig"))
    return translations, manual, (
        glossary.get("keys", {}),
        glossary.get("values", {}),
        glossary.get("phrases", {}),
    )


def _write_translated_jar(source_jar: Path, destination: Path, proposals: dict[str, str]) -> None:
    occurrence_by_entry_key: dict[tuple[str, str], int] = {}
    with zipfile.ZipFile(source_jar, "r") as source, zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED
    ) as output:
        for info in source.infolist():
            raw = source.read(info.filename)
            if info.filename not in ENTRIES:
                output.writestr(info, raw)
                continue
            text = raw.decode("utf-8-sig")
            rewritten: list[str] = []
            for line in text.splitlines(keepends=True):
                newline = ""
                body = line
                if line.endswith("\r\n"):
                    body, newline = line[:-2], "\r\n"
                elif line.endswith("\n"):
                    body, newline = line[:-1], "\n"
                if not body or body.startswith(("#", "!")) or "=" not in body:
                    rewritten.append(line)
                    continue
                key, source_value = body.split("=", 1)
                marker = (info.filename, key)
                occurrence_by_entry_key[marker] = occurrence_by_entry_key.get(marker, 0) + 1
                identity = f"{info.filename}:{key}#{occurrence_by_entry_key[marker]}"
                rewritten.append(f"{key}={proposals.get(identity, source_value)}{newline}")
            output.writestr(info.filename, "".join(rewritten).encode("utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _render_main_properties(jar: Path) -> str:
    with zipfile.ZipFile(jar) as archive:
        return archive.read("texts_en.properties").decode("utf-8")


def run(*, output_dir: Path, model_path: Path, model_lock: Path) -> dict[str, object]:
    if _sha256(model_path) != MODEL_SHA256:
        raise ValueError("model SHA-256 does not match the locked Argos fixture")

    state_path = ROOT / "automation" / "state.json"
    state_before = _sha256(state_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="wakfu-test-pr-pipeline-") as temporary:
        temp_root = Path(temporary)
        version_a = temp_root / "version_a.jar"
        version_b = temp_root / "version_b.jar"
        translated = temp_root / "translated.jar"
        _write_jar(version_a, VERSION_A_MAIN)
        _write_jar(version_b, VERSION_B_MAIN)

        before = records_from_jar(version_a)
        after = records_from_jar(version_b)
        delta = diff_records(before, after)
        if not all(delta[kind] for kind in ("UNCHANGED", "NEW", "MODIFIED", "REMOVED")):
            raise AssertionError("fixture must exercise every diff category")

        duplicate_modified = [
            record.identity
            for record in delta["MODIFIED"]
            if record.key == "fixture.duplicate"
        ]
        if duplicate_modified != [
            "texts_en.properties:fixture.duplicate#1",
            "texts_en.properties:fixture.duplicate#2",
        ]:
            raise AssertionError(f"duplicate occurrence tracking failed: {duplicate_modified}")

        translations, manual, terms = _load_translation_data()
        # These are fixture-only overlays.  The production files are read but
        # never written or mutated on disk.
        translations["fixture.tm"] = "Yeni [#1] eşya"
        manual["fixture.duplicate"] = "Yinelenen metin"
        terms[1]["Damage <b>value</b>"] = "Hasar <b>değeri</b>"

        translate = install_locked_model(model_path, model_lock)
        proposals, origins = resolve_changes(
            delta["NEW"] + delta["MODIFIED"],
            translations=translations,
            manual=manual,
            terms=terms,
            argos=translate,
        )
        validate_proposals(
            diff=delta,
            proposals=proposals,
            baseline_translations={record.identity: record.source for record in before},
        )

        origin_counts = {
            "manual": list(origins.values()).count("manual"),
            "tm": list(origins.values()).count("memory"),
            "glossary": sum(
                list(origins.values()).count(name) for name in ("glossary-key", "glossary-value")
            ),
            "argos": list(origins.values()).count("argos"),
        }
        if origin_counts["tm"] != 1 or origin_counts["glossary"] != 1 or origin_counts["argos"] != 1:
            raise AssertionError(f"provider fixture counts are wrong: {origin_counts}")

        _write_translated_jar(version_b, translated, proposals)
        translated_records = {record.identity: record for record in records_from_jar(translated)}
        source_records = {record.identity: record for record in after}
        for identity, source_record in source_records.items():
            target = translated_records.get(identity)
            if target is None:
                raise AssertionError(f"translated output lost record: {identity}")
            if not format_ok(source_record.source, target.source):
                raise AssertionError(f"placeholder/tag validation failed: {identity}")

        # Use the existing audit implementation as the second validation gate.
        import sys

        sys.path.insert(0, str(ROOT / "Kaynak_Kodu"))
        from wakfu_audit import format_ok as audit_format_ok  # type: ignore

        for identity, source_record in source_records.items():
            if not audit_format_ok(source_record.source, translated_records[identity].source):
                raise AssertionError(f"wakfu_audit validation failed: {identity}")

        release_dir = temp_root / "release"
        manifest = build_release_assets(
            patch_jar=translated,
            source_jar=version_b,
            game_version=GAME_VERSION,
            patch_version=PATCH_VERSION,
            output_dir=release_dir,
        )
        verify_i18n_jar(release_dir / "i18n.jar")
        if manifest["sha256"] != _sha256(release_dir / "i18n.jar"):
            raise AssertionError("simulated build hash mismatch")

        state_after = _sha256(state_path)
        if state_after != state_before:
            raise AssertionError("production state changed during test fixture generation")

        # Capture the validated output before the temporary JAR directory is
        # removed; only this text form is written into the test PR.
        translated_text = _render_main_properties(translated)

        report: dict[str, object] = {
            "status": "TEST_PIPELINE_ONLY",
            "simulated_game_version": "fixture-1.92.1.5172.314",
            "simulated_patch_version": PATCH_VERSION,
            "diff": {kind: len(delta[kind]) for kind in ("UNCHANGED", "NEW", "MODIFIED", "REMOVED")},
            "translation_counts": origin_counts,
            "duplicate_modified": duplicate_modified,
            "placeholder_and_tag_validation": "PASS",
            "validation": "PASS",
            "build": {
                "status": "PASS",
                "file": "i18n.jar (temporary; not committed)",
                "size": manifest["size"],
                "sha256": manifest["sha256"],
            },
            "production_state_unchanged": True,
            "production_translation_files_unchanged": True,
            "release_created": False,
        }

    (output_dir / "version_a.properties").write_text(VERSION_A_MAIN, encoding="utf-8")
    (output_dir / "version_b.properties").write_text(VERSION_B_MAIN, encoding="utf-8")
    (output_dir / "translated_output.properties").write_text(
        translated_text, encoding="utf-8"
    )
    (output_dir / "simulated_update_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "README.md").write_text(
        "# TEST PIPELINE ONLY\n\n"
        "DO NOT MERGE. This directory is a disposable simulated WAKFU update.\n"
        "It does not modify production translation memory, baseline, state, or Release assets.\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--model-lock", type=Path, required=True)
    args = parser.parse_args()
    report = run(output_dir=args.output_dir, model_path=args.model_path, model_lock=args.model_lock)
    print("SIMULATED_PR_PIPELINE_OK|" + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

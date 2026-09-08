"""Run the complete A -> B localization/update/release simulation.

The fixture is intentionally small and is written only below a temporary
directory.  It exercises the same record identities, translation priority,
locked Argos provider, properties writer, release manifest builder and Setup
EXE test seam used by the production flow.  No fixture artifact is written to
the repository.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from automation.argos_engine import install_locked_model
from automation.localization_pipeline import (
    ENTRIES,
    Record,
    diff_records,
    format_ok,
    records_from_jar,
    resolve_changes,
    validate_proposals,
)
from automation.release_package import build_release_assets, sha256


ROOT = Path(__file__).resolve().parents[2]
MODEL_SHA256 = "2d553a00880a0c21dea5b1c375535659e6bf18c9bf2ce9847c2a2fd2ff50316a"
GAME_VERSION = "1.92.1.5172.314"
PATCH_VERSION = "2026.09.05.3"


VERSION_A_MAIN = """# Version A\n\
sim.same=Same unchanged text\n\
sim.manual=Welcome hero.\n\
sim.tm=Old [#1] count\n\
sim.glossary=Old damage\n\
sim.argos=Hello adventurer.\n\
sim.duplicate=First [#1]\n\
sim.duplicate=Second [#1]\n\
sim.placeholder=You have [#1] items.\n\
sim.tag=<b>Damage</b>\n\
sim.removed=Gone forever\n"""

VERSION_B_MAIN = """# Version B\n\
sim.same=Same unchanged text\n\
sim.manual=Welcome hero, changed\n\
sim.tm=New [#1] count\n\
sim.glossary=Damage\n\
sim.argos=Hello adventurer.\n\
sim.new=You have [#1] items.\n\
sim.duplicate=Second [#1]\n\
sim.duplicate=First [#1]\n\
sim.placeholder=You have [#1] items.\n\
sim.tag=<b>Damage dealt</b>\n"""

VERSION_A_CLEAN = """sim.clean.unchanged=Clean unchanged\n\
sim.clean.duplicate=Clean first\n\
sim.clean.duplicate=Clean second\n"""


def _write_jar(path: Path, main: str, clean: str) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("texts_en.properties", main.encode("utf-8"))
        archive.writestr("texts_en_cleaned.properties", clean.encode("utf-8"))


def _records_by_identity(jar: Path) -> dict[str, Record]:
    return {record.identity: record for record in records_from_jar(jar)}


def _write_translated_jar(
    source_jar: Path,
    destination: Path,
    proposals: dict[str, str],
    existing_translations: dict[str, str],
) -> None:
    """Rewrite only known properties values while preserving order/comments."""
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
                value = proposals.get(identity, existing_translations.get(identity, source_value))
                rewritten.append(f"{key}={value}{newline}")
            output.writestr(info.filename, "".join(rewritten).encode("utf-8"))


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


def _run_setup_release_test(fixture_dir: Path) -> str:
    runner = ROOT / "automation" / "tests" / "run_release_updater_tests.ps1"
    environment = os.environ.copy()
    environment["WAKFU_FULL_SIMULATION_FIXTURE"] = str(fixture_dir)
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(runner)],
        cwd=str(ROOT),
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            "Setup EXE full-release test failed:\n" + completed.stdout + "\n" + completed.stderr
        )
    return completed.stdout


def run_simulation(model_path: Path, model_lock: Path, output_root: Path) -> dict[str, object]:
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != MODEL_SHA256:
        raise AssertionError("Argos fixture model hash does not match model-lock.json")

    version_a = output_root / "version_a.jar"
    version_b = output_root / "version_b.jar"
    patch_jar = output_root / "i18n.jar"
    _write_jar(version_a, VERSION_A_MAIN, VERSION_A_CLEAN)
    _write_jar(version_b, VERSION_B_MAIN, VERSION_A_CLEAN)

    before = records_from_jar(version_a)
    after = records_from_jar(version_b)
    delta = diff_records(before, after)
    if not delta["UNCHANGED"] or not delta["NEW"] or not delta["MODIFIED"] or not delta["REMOVED"]:
        raise AssertionError("fixture did not produce all four diff categories")
    duplicate_modified = [
        record.identity
        for record in delta["MODIFIED"]
        if record.key == "sim.duplicate"
    ]
    if duplicate_modified != [
        "texts_en.properties:sim.duplicate#1",
        "texts_en.properties:sim.duplicate#2",
    ]:
        raise AssertionError(f"duplicate order change was not retained: {duplicate_modified}")

    translations, manual, terms = _load_translation_data()
    # These entries are a temporary fixture overlay.  The real translation
    # files above remain untouched and are still loaded as the first source.
    translations["sim.tm"] = "Yeni [#1] sayısı"
    manual["sim.manual"] = "Hoş geldin kahraman."
    # Markup-bearing labels are reviewed just like production UI labels; the
    # quality gate must not accept the fixture model's occasional English
    # residue (for example ``<b>Damage dealt</b>``).
    manual["sim.tag"] = "<b>Hasar verildi</b>"
    terms[1]["Damage"] = "Hasar"

    translator = install_locked_model(model_path, model_lock)
    proposals, origins = resolve_changes(
        delta["NEW"] + delta["MODIFIED"],
        translations=translations,
        manual=manual,
        terms=terms,
        argos=translator,
    )
    validate_proposals(
        diff=delta,
        proposals=proposals,
        baseline_translations={record.identity: record.source for record in before},
    )
    required_origins = {
        "manual",
        "memory",
        "glossary-value",
        "argos",
    }
    if not required_origins.issubset(set(origins.values())):
        raise AssertionError(f"translation priority did not exercise all providers: {origins}")

    before_by_id = _records_by_identity(version_a)
    after_by_id = _records_by_identity(version_b)
    # Existing human translations are supplied as the immutable baseline for
    # unchanged records; the update engine must not invent or alter them.
    existing_translations = {
        identity: value
        for identity, value in {
            "texts_en.properties:sim.same#1": "Aynı değişmeden metin",
            "texts_en.properties:sim.placeholder#1": "[ #1 ] öğeniz var.",
            "texts_en.properties:sim.glossary#1": "Hasar",
            "texts_en.properties:sim.argos#1": "Merhaba maceracı.",
            "texts_en_cleaned.properties:sim.clean.unchanged#1": "Temiz değişmedi",
            "texts_en_cleaned.properties:sim.clean.duplicate#1": "Temiz ilk",
            "texts_en_cleaned.properties:sim.clean.duplicate#2": "Temiz ikinci",
        }.items()
        if identity in {record.identity for record in delta["UNCHANGED"]}
    }
    # The fixture intentionally uses the exact placeholder form; correct the
    # visual spacing above before writing while preserving the token itself.
    existing_translations["texts_en.properties:sim.placeholder#1"] = "[ #1 ] öğeniz var.".replace("[ #1 ]", "[#1]")
    _write_translated_jar(version_b, patch_jar, proposals, existing_translations)

    output_records = _records_by_identity(patch_jar)
    for identity, source_record in after_by_id.items():
        target = output_records.get(identity)
        if target is None:
            raise AssertionError(f"output lost properties record: {identity}")
        translated = target.source
        if not format_ok(source_record.source, translated):
            raise AssertionError(f"automation format validation failed: {identity}")
        if identity in {record.identity for record in delta["UNCHANGED"]}:
            expected = existing_translations.get(identity, source_record.source)
            if translated != expected:
                raise AssertionError(f"UNCHANGED translation changed: {identity}")

    # Also run the project's existing audit implementation against every
    # source/target pair.  It is deliberately imported from Kaynak_Kodu and
    # never copied or replaced by the simulation.
    sys.path.insert(0, str(ROOT / "Kaynak_Kodu"))
    from wakfu_audit import format_ok as audit_format_ok  # type: ignore

    for identity, source_record in after_by_id.items():
        if not audit_format_ok(source_record.source, output_records[identity].source):
            raise AssertionError(f"wakfu_audit format validation failed: {identity}")

    release_dir = output_root / "release"
    manifest = build_release_assets(
        patch_jar=patch_jar,
        source_jar=version_a,
        game_version=GAME_VERSION,
        patch_version=PATCH_VERSION,
        output_dir=release_dir,
    )
    if manifest["sha256"] != sha256(release_dir / "i18n.jar"):
        raise AssertionError("manifest hash does not match release asset")
    if manifest["size"] != (release_dir / "i18n.jar").stat().st_size:
        raise AssertionError("manifest size does not match release asset")

    # The C# fake Release server consumes only these two files.  This directory
    # is temporary and is deleted by the unittest wrapper after the run.
    setup_fixture = output_root / "setup_fixture"
    setup_fixture.mkdir()
    (setup_fixture / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (setup_fixture / "i18n.jar").write_bytes((release_dir / "i18n.jar").read_bytes())
    (setup_fixture / "version_a_i18n_en.jar").write_bytes(version_a.read_bytes())
    setup_output = _run_setup_release_test(setup_fixture)
    if "PASS|full simulated external Release -> Setup" not in setup_output:
        raise AssertionError("Setup test did not report the full simulated Release pass")

    return {
        "game_version": GAME_VERSION,
        "patch_version": PATCH_VERSION,
        "diff": {kind: len(delta[kind]) for kind in ("UNCHANGED", "NEW", "MODIFIED", "REMOVED")},
        "duplicate_modified": duplicate_modified,
        "translation_origins": {name: list(origins.values()).count(name) for name in sorted(set(origins.values()))},
        "release_sha256": manifest["sha256"],
        "release_size": manifest["size"],
        "setup": "PASS",
        "setup_output": setup_output,
        "model_sha256": MODEL_SHA256,
    }


class FullSimulatedUpdateTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("ARGOS_MODEL_PATH"), "requires the hash-locked Argos fixture model")
    def test_version_a_to_b_full_chain(self) -> None:
        model_path = Path(os.environ["ARGOS_MODEL_PATH"])
        lock_path = Path(os.environ.get("ARGOS_MODEL_LOCK", ROOT / "automation" / "model-lock.json"))
        with tempfile.TemporaryDirectory(prefix="wakfu-full-simulation-") as temporary:
            result = run_simulation(model_path, lock_path, Path(temporary))
            self.assertEqual(result["setup"], "PASS")
            self.assertGreater(result["diff"]["NEW"], 0)
            self.assertGreater(result["diff"]["MODIFIED"], 0)


if __name__ == "__main__":
    if not os.environ.get("ARGOS_MODEL_PATH"):
        raise SystemExit("ARGOS_MODEL_PATH is required for the full simulation")
    model = Path(os.environ["ARGOS_MODEL_PATH"])
    lock = Path(os.environ.get("ARGOS_MODEL_LOCK", ROOT / "automation" / "model-lock.json"))
    with tempfile.TemporaryDirectory(prefix="wakfu-full-simulation-") as temporary:
        report = run_simulation(model, lock, Path(temporary))
        print("FULL_SIMULATED_UPDATE_OK|" + json.dumps(report, ensure_ascii=False, sort_keys=True))

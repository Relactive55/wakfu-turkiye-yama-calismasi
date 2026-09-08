from __future__ import annotations
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from automation.localization_pipeline import Record, diff_records, records_from_jar, resolve_changes, validate_proposals
from automation.errors import TranslationProviderUnavailable, VerificationError
import automation.production_pr_update as production_pr_update
from automation.production_pr_update import build_provider_unavailable_report
from automation.update_wakfu_localization import sha1, snapshot

def make_jar(path: Path, main: str, clean: str) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("texts_en.properties", main)
        z.writestr("texts_en_cleaned.properties", clean)

class PipelineSimulation(unittest.TestCase):
    def test_argos_placeholder_loss_retries_without_sending_tokens(self) -> None:
        record = Record(
            "texts_en.properties:placeholder#1",
            "texts_en.properties",
            "placeholder",
            1,
            "Use [#1] now",
        )
        calls: list[str] = []

        def provider(text: str) -> str:
            calls.append(text)
            if "ZXQ" in text:
                return "Kullan şimdi"
            return text.replace("Use", "Kullan").replace("now", "şimdi")

        proposals, origins = resolve_changes(
            [record], translations={}, manual={}, terms=({}, {}, {}), argos=provider
        )
        self.assertEqual(proposals[record.identity], "Kullan [#1] şimdi")
        self.assertEqual(origins[record.identity], "argos")
        self.assertGreaterEqual(len(calls), 3)
        self.assertTrue(all("ZXQ" not in call for call in calls[1:]))

    def test_full_fixture_diff_memory_argos_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); before=root/'before.jar'; after=root/'after.jar'
            make_jar(before, "same=Same\nmod=Old [#1]\ndup=A\ndup=B\nremoved=Gone\ntag=<b>Tag</b>\n", "clean=Clean\n")
            make_jar(after, "same=Same\nmod=New [#1]\ndup=A\ndup=C\nnew=New\ntag=<b>Tag</b>\n", "clean=Clean\n")
            delta=diff_records(records_from_jar(before),records_from_jar(after))
            self.assertEqual([x.key for x in delta['UNCHANGED']], ['dup','same','tag','clean'])
            self.assertEqual([x.identity for x in delta['MODIFIED']], ['texts_en.properties:dup#2','texts_en.properties:mod#1'])
            self.assertEqual([x.key for x in delta['NEW']], ['new'])
            self.assertEqual([x.key for x in delta['REMOVED']], ['removed'])
            tm={'mod':'Yeni [#1]'}; manual={}; terms=({}, {'New':'Yeni'}, {})
            proposed, origin=resolve_changes(delta['NEW']+delta['MODIFIED'],translations=tm,manual=manual,terms=terms,argos=lambda text: text.replace('C','Ç'))
            self.assertEqual(origin['texts_en.properties:mod#1'],'memory')
            self.assertEqual(origin['texts_en.properties:new#1'],'glossary-value')
            self.assertEqual(origin['texts_en.properties:dup#2'],'argos')
            validate_proposals(diff=delta,proposals=proposed,baseline_translations=tm)
            with self.assertRaises(VerificationError): validate_proposals(diff=delta,proposals={'texts_en.properties:same#1':'Değişti'},baseline_translations=tm)
            with self.assertRaises(TranslationProviderUnavailable):
                resolve_changes(delta['NEW'] + delta['MODIFIED'], translations={}, manual={}, terms=({}, {}, {}), argos=None)
            no_changes, no_change_origins = resolve_changes(
                [],
                translations={},
                manual={},
                terms=({}, {}, {}),
                argos=None,
            )
            self.assertEqual(no_changes, {})
            self.assertEqual(no_change_origins, {})

    def test_provider_unavailable_report_is_fail_closed_and_sanitized(self) -> None:
        unresolved = [Record("texts_en.properties:new.secret#1", "texts_en.properties", "new.secret", 1, "do not copy this")]
        report = build_provider_unavailable_report(
            game_version="6.5.12",
            source_sha1="abc123",
            diff={"UNCHANGED": 10, "NEW": 1, "MODIFIED": 2, "REMOVED": 0},
            unresolved=unresolved,
            reason_code="ARGOS_RUNTIME_OR_MODEL_UNAVAILABLE",
        )
        self.assertEqual(report["status"], "PROVIDER_UNAVAILABLE")
        self.assertEqual(report["unresolved_count"], 1)
        self.assertEqual(report["unresolved_keys"], ["texts_en.properties:new.secret#1"])
        self.assertFalse(report["state_written_in_candidate_branch"])
        self.assertFalse(report["translation_memory_changed"])
        self.assertFalse(report["release_created"])
        self.assertNotIn("do not copy this", str(report))

    def test_production_update_provider_stop_does_not_write_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "automation" / "snapshots").mkdir(parents=True)
            (root / "Ceviri_Verileri").mkdir(parents=True)
            before = root / "before.jar"
            after = root / "after.jar"
            make_jar(before, "same=Same\n", "clean=Clean\n")
            make_jar(after, "same=Same\nnew=Unresolved\n", "clean=Clean\n")
            state_path = root / "automation" / "state.json"
            baseline_path = root / "automation" / "snapshots" / "baseline.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "baseline": "snapshots/baseline.json",
                        "game_version": "old",
                        "source_sha1": sha1(before),
                    }
                ),
                encoding="utf-8",
            )
            baseline_path.write_text(json.dumps(snapshot(before, "old", sha1(before))), encoding="utf-8")
            translation_path = root / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"
            manual_path = root / "Ceviri_Verileri" / "manual_repairs_v23.json"
            terms_path = root / "Ceviri_Verileri" / "terim_duzeltmeleri.json"
            translation_path.write_text(json.dumps({"same": "Aynı"}), encoding="utf-8")
            manual_path.write_text("{}", encoding="utf-8")
            terms_path.write_text(json.dumps({"keys": {}, "values": {}, "phrases": {}}), encoding="utf-8")
            state_before = state_path.read_bytes()
            translation_before = translation_path.read_bytes()

            class FakeClient:
                def latest_version(self):
                    return "new"

                def target_entry(self, _version):
                    return SimpleNamespace(sha1="after-manifest"), None

                def download_localization(self, version, destination):
                    shutil.copyfile(before if version == "old" else after, destination)

            with patch.object(production_pr_update, "ROOT", root), \
                patch.object(production_pr_update, "STATE_PATH", state_path), \
                patch.object(production_pr_update, "TRANSLATION_PATH", translation_path), \
                patch.object(production_pr_update, "MANUAL_PATH", manual_path), \
                patch.object(production_pr_update, "TERMS_PATH", terms_path), \
                patch.object(production_pr_update, "AnkamaCdnClient", FakeClient):
                report = production_pr_update.run(
                    output_dir=root / "output",
                    model_path=None,
                    model_lock=None,
                    allow_provider_unavailable=True,
                )

            self.assertEqual(report["status"], "PROVIDER_UNAVAILABLE")
            self.assertEqual(state_path.read_bytes(), state_before)
            self.assertEqual(translation_path.read_bytes(), translation_before)
            self.assertFalse((root / "automation" / "snapshots" / "new.json").exists())
            self.assertTrue((root / "output" / "production_update_report.json").is_file())

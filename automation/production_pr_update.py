"""Build a production localization candidate for the scheduled PR workflow.

The command writes only the candidate translation memory, the verified source
snapshot and state pointer in the caller's checkout.  It never creates a
branch or PR and never publishes a release by itself.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from .ankama_cdn import AnkamaCdnClient
from .argos_engine import install_locked_model
from .errors import TranslationProviderUnavailable, VerificationError
from .localization_pipeline import Record, diff_records, format_ok, records_from_jar, resolve_changes, validate_proposals
from .state import atomic_json_write, read_json
from .update_wakfu_localization import sha1, snapshot

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "automation" / "state.json"
TRANSLATION_PATH = ROOT / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"
MANUAL_PATH = ROOT / "Ceviri_Verileri" / "manual_repairs_v23.json"
TERMS_PATH = ROOT / "Ceviri_Verileri" / "terim_duzeltmeleri.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_properties(source: Path, output: Path, proposals: dict[str, str]) -> None:
    occurrence: dict[tuple[str, str], int] = {}
    with zipfile.ZipFile(source) as archive, zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in archive.infolist():
            raw = archive.read(info.filename)
            if info.filename not in ("texts_en.properties", "texts_en_cleaned.properties"):
                target.writestr(info, raw)
                continue
            text = raw.decode("utf-8-sig")
            result: list[str] = []
            for line in text.splitlines(keepends=True):
                body, newline = line, ""
                if line.endswith("\r\n"):
                    body, newline = line[:-2], "\r\n"
                elif line.endswith("\n"):
                    body, newline = line[:-1], "\n"
                if not body or body.startswith(("#", "!")) or "=" not in body:
                    result.append(line)
                    continue
                key, value = body.split("=", 1)
                marker = (info.filename, key)
                occurrence[marker] = occurrence.get(marker, 0) + 1
                identity = f"{info.filename}:{key}#{occurrence[marker]}"
                result.append(f"{key}={proposals.get(identity, value)}{newline}")
            target.writestr(info.filename, "".join(result).encode("utf-8"))


def coalesce_proposals_by_key(records: list[Record], proposals: dict[str, str]) -> dict[str, str]:
    """Choose one safe translation for duplicate key occurrences.

    WAKFU ships both a normally-cased properties file and a lower-cased
    ``*_cleaned`` copy.  The same key can therefore receive harmless casing or
    whitespace differences from a machine-translation pass.  When the source
    occurrences are equivalent ignoring case/outer whitespace, prefer the
    normal properties entry and require that value to remain format-valid for
    every occurrence.  Truly different source strings still fail closed.
    """
    grouped: dict[str, list[Record]] = {}
    for record in records:
        grouped.setdefault(record.key, []).append(record)

    by_key: dict[str, str] = {}
    for key, group in grouped.items():
        ordered = sorted(group, key=lambda item: (item.entry != "texts_en.properties", item.identity))
        candidates: list[str] = []
        for record in ordered:
            if record.identity not in proposals:
                raise VerificationError("MISSING_PROPOSAL: " + record.identity)
            value = proposals[record.identity]
            if value not in candidates:
                candidates.append(value)
        if len(candidates) == 1:
            by_key[key] = candidates[0]
            continue

        equivalent_sources = len({record.source.strip().casefold() for record in group}) == 1
        if equivalent_sources:
            for candidate in candidates:
                if all(format_ok(record.source, candidate) for record in group):
                    by_key[key] = candidate
                    break
            else:
                raise VerificationError(f"DUPLICATE_PROPOSAL_FORMAT_CONFLICT: {key}")
            continue
        raise VerificationError(f"DUPLICATE_PROPOSAL_CONFLICT: {key}")
    return by_key


def build_provider_unavailable_report(
    *,
    game_version: str,
    source_sha1: str,
    diff: dict[str, int],
    unresolved: list[Record],
    reason_code: str,
) -> dict[str, object]:
    """Describe a safe, non-publishing stop when Argos cannot be used.

    The report intentionally contains identities and counts only.  It never
    copies upstream source text or an exception (which could contain a local
    path) into an issue, PR, or artifact.  Most importantly, this result is
    emitted before any project state or translation-memory file is written.
    """
    return {
        "status": "PROVIDER_UNAVAILABLE",
        "provider": "argos",
        "reason_code": reason_code,
        "game_version": game_version,
        "source_sha1": source_sha1,
        "diff": diff,
        "unresolved_count": len(unresolved),
        "unresolved_keys": [record.identity for record in unresolved[:100]],
        "removed_report_only": True,
        "validation": "SKIPPED_PROVIDER_UNAVAILABLE",
        "build": "SKIPPED_PROVIDER_UNAVAILABLE",
        "state_written_in_candidate_branch": False,
        "translation_memory_changed": False,
        "release_created": False,
    }


def _write_report(output_dir: Path, report: dict[str, object]) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "production_update_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def run(
    *,
    output_dir: Path,
    model_path: Path | None,
    model_lock: Path | None,
    allow_provider_unavailable: bool = False,
) -> dict[str, object]:
    state = read_json(STATE_PATH, default=None)
    if not isinstance(state, dict) or not isinstance(state.get("baseline"), str):
        raise VerificationError("BASELINE_REQUIRED: approved baseline state is missing")
    baseline_path = ROOT / "automation" / str(state["baseline"])
    baseline = read_json(baseline_path, default=None)
    if not isinstance(baseline, dict):
        raise VerificationError("baseline snapshot is missing or invalid")
    client = AnkamaCdnClient()
    approved_version = state.get("game_version")
    approved_sha1 = state.get("source_sha1")
    if not isinstance(approved_version, str) or not approved_version:
        raise VerificationError("BASELINE_REQUIRED: approved game version is missing")
    if not isinstance(approved_sha1, str) or not approved_sha1:
        raise VerificationError("BASELINE_REQUIRED: approved source SHA-1 is missing")
    if baseline.get("game_version") != approved_version or baseline.get("source_sha1") != approved_sha1:
        raise VerificationError("BASELINE_MISMATCH: snapshot metadata does not match automation state")

    with tempfile.TemporaryDirectory(prefix="wakfu-production-update-") as temporary:
        # GitHub-hosted runners start from a clean checkout, so the approved
        # source JAR is intentionally not kept in the repository.  Re-fetch
        # the exact baseline recorded in state.json from the allow-listed
        # Ankama CDN and verify its assembled SHA-1 before using it for the
        # source diff.  This keeps the production workflow reproducible
        # without committing proprietary game data or trusting a local file.
        local_source = Path(temporary) / "approved-i18n_en.jar"
        client.download_localization(approved_version, local_source)
        if sha1(local_source).lower() != approved_sha1.lower():
            raise VerificationError("BASELINE_MISMATCH: downloaded approved source does not match automation state")

        version = client.latest_version()
        entry, _ = client.target_entry(version)
        source = Path(temporary) / "i18n_en.jar"
        client.download_localization(version, source)
        current = snapshot(source, version, entry.sha1)
        old_records = {key: value for key, value in baseline["records"].items()}
        before = records_from_jar(local_source)
        after = records_from_jar(source)
        delta = diff_records(before, after)
        counts = {kind: len(delta[kind]) for kind in ("UNCHANGED", "NEW", "MODIFIED", "REMOVED")}
        if not delta["NEW"] and not delta["MODIFIED"] and not delta["REMOVED"]:
            return {"status": "NO_CHANGES", "game_version": version, "source_sha1": entry.sha1, "diff": counts}

        translations = _load(TRANSLATION_PATH)
        manual = _load(MANUAL_PATH)
        glossary = _load(TERMS_PATH)
        terms = (glossary.get("keys", {}), glossary.get("values", {}), glossary.get("phrases", {}))
        unresolved = [record for record in delta["NEW"] + delta["MODIFIED"] if record.key not in manual and not translations.get(record.key) and record.key not in terms[0] and record.source not in terms[1]]
        translate = None

        def provider_stop(reason_code: str) -> dict[str, object]:
            return _write_report(
                output_dir,
                build_provider_unavailable_report(
                    game_version=version,
                    source_sha1=entry.sha1,
                    diff=counts,
                    unresolved=unresolved,
                    reason_code=reason_code,
                ),
            )

        if unresolved:
            if model_path is None or model_lock is None:
                if allow_provider_unavailable:
                    return provider_stop("ARGOS_INPUT_MISSING")
                raise TranslationProviderUnavailable("TRANSLATION_PROVIDER_UNAVAILABLE: Argos model is required for unresolved production records")
            try:
                translate = install_locked_model(model_path, model_lock)
            except Exception:
                if not allow_provider_unavailable:
                    raise
                return provider_stop("ARGOS_RUNTIME_OR_MODEL_UNAVAILABLE")
        if translate is not None:
            provider = translate

            def guarded_translate(text: str) -> str:
                try:
                    return provider(text)
                except Exception as exc:
                    raise TranslationProviderUnavailable("TRANSLATION_PROVIDER_UNAVAILABLE: Argos translation call failed") from exc

            translate = guarded_translate
        try:
            proposals, origins = resolve_changes(delta["NEW"] + delta["MODIFIED"], translations=translations, manual=manual, terms=terms, argos=translate)
        except TranslationProviderUnavailable:
            if not allow_provider_unavailable:
                raise
            return provider_stop("ARGOS_TRANSLATION_RUNTIME_UNAVAILABLE")
        validate_proposals(diff=delta, proposals=proposals, baseline_translations={r.identity: r.source for r in before})

        by_key = coalesce_proposals_by_key(delta["NEW"] + delta["MODIFIED"], proposals)
        for key, value in by_key.items():
            if key not in manual:
                translations[key] = value

        output_dir.mkdir(parents=True, exist_ok=True)
        TRANSLATION_PATH.write_text(json.dumps(translations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        snapshot_path = ROOT / "automation" / "snapshots" / f"{version}.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json_write(snapshot_path, current)
        atomic_json_write(STATE_PATH, {"schema": 1, "baseline": str(snapshot_path.relative_to(ROOT / "automation")).replace("\\", "/"), "game_version": version, "source_sha1": entry.sha1})

        candidate_jar = output_dir / "candidate-i18n.jar"
        subprocess.run([
            sys.executable, str(ROOT / "Kaynak_Kodu" / "build_wakfu_jar.py"),
            "--source-jar", str(source), "--output-jar", str(candidate_jar),
            "--project", str(TRANSLATION_PATH), "--terminology", str(TERMS_PATH),
            "--manual-repairs", str(MANUAL_PATH),
        ], cwd=ROOT, check=True, capture_output=True, text=True)
        audit = subprocess.run([
            sys.executable, str(ROOT / "Kaynak_Kodu" / "wakfu_audit.py"),
            "--source-jar", str(source), "--project", str(TRANSLATION_PATH),
            "--terminology", str(TERMS_PATH), "--manual-repairs", str(MANUAL_PATH),
            "--output-dir", str(ROOT / "Raporlar"), "--stage", "full",
        ], cwd=ROOT, check=True, capture_output=True, text=True)
        if "AUDIT|" not in audit.stdout or not audit.stdout.strip().endswith("|0"):
            raise VerificationError("PRODUCTION_AUDIT_FAILED: " + audit.stdout[-500:])

        report = {
            "status": "PRODUCTION_CANDIDATE",
            "game_version": version,
            "source_sha1": entry.sha1,
            "diff": counts,
            "translation_counts": {name: list(origins.values()).count(name) for name in ("manual", "memory", "glossary-key", "glossary-value", "argos")},
            "removed_report_only": True,
            "validation": "PASS",
            "build": "PASS",
            "state_written_in_candidate_branch": True,
            "baseline": str(snapshot_path.relative_to(ROOT)).replace("\\", "/"),
        }
        return _write_report(output_dir, report)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-path", type=Path)
    parser.add_argument("--model-lock", type=Path)
    parser.add_argument(
        "--allow-provider-unavailable",
        action="store_true",
        help="Stop safely without state/PR/release writes when Argos cannot be loaded",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                output_dir=args.output_dir,
                model_path=args.model_path,
                model_lock=args.model_lock,
                allow_provider_unavailable=args.allow_provider_unavailable,
            ),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

"""Build a production localization candidate for the scheduled PR workflow.

The command writes only the candidate translation memory, the verified source
snapshot and state pointer in the caller's checkout.  It never creates a
branch or PR and never publishes a release by itself.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from .ankama_cdn import AnkamaCdnClient
from .argos_engine import install_locked_model
from .errors import TranslationProviderUnavailable, VerificationError
from .localization_pipeline import (
    Record,
    diff_records,
    format_ok,
    glossary_key_source_matches,
    manual_source_matches,
    memory_source_matches,
    records_from_jar,
    resolve_changes,
    source_fingerprint,
    validate_proposals,
)
from .state import atomic_json_write, read_json
from .update_wakfu_localization import sha1, snapshot

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "automation" / "state.json"
TRANSLATION_PATH = ROOT / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"
MANUAL_PATH = ROOT / "Ceviri_Verileri" / "manual_repairs_v23.json"
TERMS_PATH = ROOT / "Ceviri_Verileri" / "terim_duzeltmeleri.json"
# Kept separate from the human-facing translation map so old key-only entries
# cannot be silently reused after an upstream key is repurposed.
MEMORY_SOURCES_PATH = ROOT / "Ceviri_Verileri" / "translation_memory_sources.json"


# The cleaned upstream properties copy is lower-cased as a preprocessing step.
# Its format tokens therefore may differ from the normal properties entry only
# by letter case.  Keep this matcher local to duplicate coalescing so the
# normal candidate validation remains strict everywhere else.
_DUPLICATE_FORMAT_ATOM = re.compile(
    r"\{\[[^\]]+\]\?|\\[ntr]|<(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>|"
    r"\[(?:[#$=,<>/-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|"
    r"%[A-Za-z_][A-Za-z0-9_.-]*%"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _normalize_source_metadata(value: object) -> dict:
    """Normalize the source-approval sidecar without trusting legacy shapes."""
    if not isinstance(value, dict):
        raise VerificationError("translation memory source metadata is invalid")
    # A pre-schema-3 flat map was memory-only.  Preserve it in that namespace
    # while making manual and glossary-key approvals explicitly empty.
    if not any(name in value for name in ("memory", "manual", "glossary_keys", "invalidated")):
        value = {"memory": dict(value)}
    metadata = dict(value)
    try:
        schema = int(metadata.get("schema", 0) or 0)
    except (TypeError, ValueError):
        schema = 0
    metadata["schema"] = max(3, schema)
    for namespace in ("memory", "manual", "glossary_keys"):
        bucket = metadata.get(namespace)
        metadata[namespace] = dict(bucket) if isinstance(bucket, dict) else {}
    invalidated = metadata.get("invalidated")
    if not isinstance(invalidated, dict):
        invalidated = {}
    metadata["invalidated"] = {
        namespace: sorted({str(key) for key in invalidated.get(namespace, []) if isinstance(key, str)})
        if isinstance(invalidated.get(namespace), list) else []
        for namespace in ("memory", "manual", "glossary_keys")
    }
    return metadata


def _append_source_hash(metadata: dict, namespace: str, key: str, source: str) -> None:
    bucket = metadata.setdefault(namespace, {})
    existing = bucket.get(key)
    values = [existing] if isinstance(existing, str) else list(existing) if isinstance(existing, list) else []
    digest = source_fingerprint(source)
    if digest not in values:
        values.append(digest)
    bucket[key] = sorted(set(values))


def _seed_source_metadata(metadata: dict, records: list[Record], manual_keys: object, term_keys: object, translation_keys: object) -> None:
    """Bind legacy records to the exact approved baseline text.

    This keeps unchanged translations usable after migration while modified
    keys are still forced through the strict per-record check below.
    """
    wanted = {
        "manual": set(manual_keys) if isinstance(manual_keys, dict) else set(),
        "glossary_keys": set(term_keys) if isinstance(term_keys, dict) else set(),
        "memory": set(translation_keys) if isinstance(translation_keys, dict) else set(),
    }
    for record in records:
        for namespace, keys in wanted.items():
            if record.key in keys:
                _append_source_hash(metadata, namespace, record.key, record.source)


def _invalidate_changed_keys(metadata: dict, records: list[Record]) -> None:
    changed = sorted({record.key for record in records})
    for namespace in ("memory", "manual", "glossary_keys"):
        current = set(metadata.setdefault("invalidated", {}).setdefault(namespace, []))
        current.update(changed)
        metadata["invalidated"][namespace] = sorted(current)


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


def _normalize_duplicate_token_case(source: str, candidate: str) -> str | None:
    """Align case-only token spelling differences with one source occurrence.

    WAKFU's ``texts_en_cleaned.properties`` entry is lower-cased, including
    placeholder names.  The translation itself must still be shared by both
    duplicate occurrences, so this helper creates a validation-only view with
    the source occurrence's token spelling.  It never changes the value kept
    in translation memory or written to the candidate.
    """
    source_atoms = list(_DUPLICATE_FORMAT_ATOM.finditer(source))
    candidate_atoms = list(_DUPLICATE_FORMAT_ATOM.finditer(candidate))
    if len(source_atoms) != len(candidate_atoms):
        return None
    if any(source_atom.group().casefold() != candidate_atom.group().casefold()
           for source_atom, candidate_atom in zip(source_atoms, candidate_atoms)):
        return None
    pieces = list(candidate)
    for source_atom, candidate_atom in reversed(list(zip(source_atoms, candidate_atoms))):
        pieces[candidate_atom.start():candidate_atom.end()] = source_atom.group()
    return "".join(pieces)


def _duplicate_format_ok(source: str, candidate: str) -> bool:
    """Validate a shared duplicate candidate, tolerating cleaned-token case."""
    if format_ok(source, candidate):
        return True
    normalized = _normalize_duplicate_token_case(source, candidate)
    return normalized is not None and format_ok(source, normalized)


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
                if all(_duplicate_format_ok(record.source, candidate) for record in group):
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
        raw_source_metadata = _load(MEMORY_SOURCES_PATH) if MEMORY_SOURCES_PATH.is_file() else {}
        source_metadata = _normalize_source_metadata(raw_source_metadata)
        # A package-level source identity is used only for legacy unchanged
        # entries by the builder/audit.  New or modified records below always
        # require one of the per-key hashes seeded from the approved baseline.
        source_metadata.setdefault("source_sha1", approved_sha1)
        manual = _load(MANUAL_PATH)
        glossary = _load(TERMS_PATH)
        terms = (glossary.get("keys", {}), glossary.get("values", {}), glossary.get("phrases", {}))
        _seed_source_metadata(source_metadata, before, manual, terms[0], translations)
        unresolved = [
            record
            for record in delta["NEW"] + delta["MODIFIED"]
            if not manual_source_matches(record, source_metadata)
            and not (
                translations.get(record.key)
                and memory_source_matches(record, source_metadata)
            )
            and not glossary_key_source_matches(record, source_metadata)
            and record.source not in terms[1]
        ]
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
            proposals, origins = resolve_changes(
                delta["NEW"] + delta["MODIFIED"],
                translations=translations,
                manual=manual,
                terms=terms,
                argos=translate,
                memory_sources=source_metadata,
                source_metadata=source_metadata,
            )
        except TranslationProviderUnavailable:
            if not allow_provider_unavailable:
                raise
            return provider_stop("ARGOS_TRANSLATION_RUNTIME_UNAVAILABLE")
        validate_proposals(diff=delta, proposals=proposals, baseline_translations={r.identity: r.source for r in before})

        by_key = coalesce_proposals_by_key(delta["NEW"] + delta["MODIFIED"], proposals)
        source_by_key: dict[str, str] = {}
        records_by_key: dict[str, list[Record]] = {}
        origins_by_key: dict[str, set[str]] = {}
        for record in delta["NEW"] + delta["MODIFIED"]:
            source_by_key.setdefault(record.key, record.source)
            records_by_key.setdefault(record.key, []).append(record)
            if record.identity in origins:
                origins_by_key.setdefault(record.key, set()).add(origins[record.identity])
        for key, value in by_key.items():
            current_records = records_by_key.get(key, [])
            manual_still_valid = bool(current_records) and all(
                manual_source_matches(record, source_metadata) for record in current_records
            )
            if key not in manual or not manual_still_valid:
                translations[key] = value
            # Every value written to the compact translation map is a memory
            # candidate for the next run.  Direct manual/glossary approvals
            # are also kept in their own source-bound namespace.
            if key in source_by_key and key in translations and translations[key] == value:
                for record in current_records:
                    _append_source_hash(source_metadata, "memory", key, record.source)
            if key in source_by_key and "manual" in origins_by_key.get(key, set()):
                for record in current_records:
                    _append_source_hash(source_metadata, "manual", key, record.source)
            if key in source_by_key and "glossary-key" in origins_by_key.get(key, set()):
                for record in current_records:
                    _append_source_hash(source_metadata, "glossary_keys", key, record.source)
        _invalidate_changed_keys(source_metadata, delta["NEW"] + delta["MODIFIED"])
        source_metadata["source_sha1"] = entry.sha1

        output_dir.mkdir(parents=True, exist_ok=True)
        TRANSLATION_PATH.write_text(json.dumps(translations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        atomic_json_write(MEMORY_SOURCES_PATH, source_metadata)
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
            "--source-metadata", str(MEMORY_SOURCES_PATH),
        ], cwd=ROOT, check=True, capture_output=True, text=True)
        audit = subprocess.run([
            sys.executable, str(ROOT / "Kaynak_Kodu" / "wakfu_audit.py"),
            "--source-jar", str(source), "--project", str(TRANSLATION_PATH),
            "--terminology", str(TERMS_PATH), "--manual-repairs", str(MANUAL_PATH),
            "--source-metadata", str(MEMORY_SOURCES_PATH),
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

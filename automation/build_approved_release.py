"""Build a stable Release package from the approved main-branch inputs.

This is intentionally separate from the PR updater.  It downloads the exact
current Ankama source, proves that it is the approved baseline, rebuilds the
Turkish JAR from tracked translation data, runs the existing audit, and only
then emits the two Release assets.  No GitHub API or Release creation happens
in this module.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .ankama_cdn import AnkamaCdnClient
from .pr_guard import release_wakfu_gate
from .release_package import build_release_assets
from .release_validation import validate_release
from .state import read_json
from .update_wakfu_localization import diff, sha1, snapshot

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
STATE_PATH = ROOT / "state.json"
SOURCE_JAR_NAME = "i18n_en.jar"
AUDIT_ISSUES = re.compile(r"(?:gereken|required)\s*:\s*(\d+)\s*$", re.IGNORECASE | re.MULTILINE)


def _approved_baseline(game_version: str) -> tuple[dict[str, object], Path]:
    state = read_json(STATE_PATH, default=None)
    if not isinstance(state, dict) or state.get("game_version") != game_version or not isinstance(state.get("source_sha1"), str):
        raise RuntimeError("approved state does not match the requested game_version")
    pointer = state.get("baseline")
    if not isinstance(pointer, str):
        raise RuntimeError("approved state has no baseline pointer")
    baseline = (ROOT / pointer).resolve()
    if ROOT.resolve() not in baseline.parents or not baseline.is_file():
        raise RuntimeError("approved baseline path is invalid")
    data = read_json(baseline, default=None)
    if not isinstance(data, dict) or data.get("game_version") != game_version or data.get("source_sha1") != state["source_sha1"] or not isinstance(data.get("records"), dict):
        raise RuntimeError("approved baseline metadata is inconsistent")
    return state, baseline


def _diagnostic_dir(output_dir: Path) -> Path:
    configured = os.environ.get("WAKFU_RELEASE_DIAGNOSTIC_DIR")
    return Path(configured) if configured else output_dir / "release-diagnostics"


def _write_diagnostic_text(directory: Path, name: str, text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text or "", encoding="utf-8")


def _run(command: list[str], *, label: str, diagnostics: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=PROJECT_ROOT, check=False, capture_output=True, text=True)
    _write_diagnostic_text(diagnostics, f"{label}.stdout.txt", result.stdout)
    _write_diagnostic_text(diagnostics, f"{label}.stderr.txt", result.stderr)
    if result.returncode:
        raise RuntimeError(
            f"{label} failed with exit code {result.returncode}. Diagnostics: {diagnostics}"
        )
    return result


def _preserve_audit_diagnostics(audit_dir: Path, patch: Path, diagnostics: Path) -> None:
    diagnostics.mkdir(parents=True, exist_ok=True)
    if audit_dir.is_dir():
        destination = diagnostics / "audit"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(audit_dir, destination)
    skipped = patch.with_suffix(".skipped.tsv")
    if skipped.is_file():
        shutil.copy2(skipped, diagnostics / "i18n.skipped.tsv")


def _write_failure_metadata(diagnostics: Path, *, stage: str, error: Exception) -> None:
    diagnostics.mkdir(parents=True, exist_ok=True)
    (diagnostics / "release_failure.json").write_text(
        json.dumps(
            {
                "status": "FAILED",
                "stage": stage,
                "error": str(error),
                "diagnostics": str(diagnostics),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _audit_issue_count(summary_path: Path) -> int:
    text = summary_path.read_text(encoding="utf-8-sig")
    matches = AUDIT_ISSUES.findall(text)
    if not matches:
        raise RuntimeError("wakfu_audit summary did not expose a critical-issue count")
    return int(matches[-1])


def build_approved_release(*, game_version: str, patch_version: str, output_dir: Path) -> dict[str, object]:
    state, baseline_path = _approved_baseline(game_version)
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostics = _diagnostic_dir(output_dir)
    if diagnostics.exists():
        shutil.rmtree(diagnostics)
    with tempfile.TemporaryDirectory(prefix="wakfu-approved-release-") as temp:
        work = Path(temp)
        source = work / SOURCE_JAR_NAME
        patch = work / "i18n.jar"
        audit_dir = work / "audit"

        client = AnkamaCdnClient()
        current_version = client.latest_version()
        current_entry, _ = client.target_entry(current_version)
        gate = release_wakfu_gate(
            approved_game_version=game_version,
            approved_source_sha1=str(state["source_sha1"]),
            current_game_version=current_version,
            current_source_sha1=current_entry.sha1,
        )
        if gate["status"] != "PASS":
            raise RuntimeError(gate["code"])
        entry = client.download_localization(game_version, source)
        if entry.sha1 != state["source_sha1"] or sha1(source) != entry.sha1:
            raise RuntimeError("RELEASE_BLOCKED_WAKFU_VERSION_CHANGED")
        current_snapshot = snapshot(source, game_version, entry.sha1)
        baseline = read_json(baseline_path, default=None)
        if diff(baseline, current_snapshot)["NEW"] or diff(baseline, current_snapshot)["MODIFIED"] or diff(baseline, current_snapshot)["REMOVED"]:
            raise RuntimeError("CDN source differs from the approved baseline; release stopped")

        try:
            _run([
                sys.executable,
                str(PROJECT_ROOT / "Kaynak_Kodu" / "build_wakfu_jar.py"),
                "--source-jar", str(source),
                "--output-jar", str(patch),
                "--project", str(PROJECT_ROOT / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"),
                "--terminology", str(PROJECT_ROOT / "Ceviri_Verileri" / "terim_duzeltmeleri.json"),
                "--manual-repairs", str(PROJECT_ROOT / "Ceviri_Verileri" / "manual_repairs_v23.json"),
                "--source-metadata", str(PROJECT_ROOT / "Ceviri_Verileri" / "translation_memory_sources.json"),
            ], label="build", diagnostics=diagnostics)
        except Exception as error:
            # The builder writes its skipped-row report next to the temporary
            # patch even when it exits non-zero.  Preserve it with the other
            # diagnostics so a failed run remains actionable instead of
            # requiring a rerun just to discover which rows were rejected.
            _preserve_audit_diagnostics(audit_dir, patch, diagnostics)
            _write_failure_metadata(diagnostics, stage="build", error=error)
            raise
        try:
            _run([
                sys.executable,
                str(PROJECT_ROOT / "Kaynak_Kodu" / "wakfu_audit.py"),
                "--source-jar", str(source),
                "--project", str(PROJECT_ROOT / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"),
                "--terminology", str(PROJECT_ROOT / "Ceviri_Verileri" / "terim_duzeltmeleri.json"),
                "--manual-repairs", str(PROJECT_ROOT / "Ceviri_Verileri" / "manual_repairs_v23.json"),
                "--source-metadata", str(PROJECT_ROOT / "Ceviri_Verileri" / "translation_memory_sources.json"),
                "--output-dir", str(audit_dir),
                "--stage", "RELEASE",
            ], label="audit", diagnostics=diagnostics)
            issue_count = _audit_issue_count(audit_dir / "Wakfu_Ceviri_Ozet.txt")
            if issue_count:
                raise RuntimeError(f"wakfu_audit reported {issue_count} critical issue(s)")
        except Exception as error:
            _preserve_audit_diagnostics(audit_dir, patch, diagnostics)
            _write_failure_metadata(diagnostics, stage="audit", error=error)
            raise
        # Re-read the lightweight CDN identity immediately before staging the
        # Release assets.  A WAKFU rollout during the build must not result in
        # an old source being tagged as current.
        final_version = client.latest_version()
        final_entry, _ = client.target_entry(final_version)
        final_gate = release_wakfu_gate(
            approved_game_version=game_version,
            approved_source_sha1=str(state["source_sha1"]),
            current_game_version=final_version,
            current_source_sha1=final_entry.sha1,
        )
        if final_gate["status"] != "PASS":
            raise RuntimeError(final_gate["code"])
        manifest = build_release_assets(patch_jar=patch, source_jar=source, game_version=game_version, patch_version=patch_version, output_dir=output_dir)
        validation = validate_release(source_jar=source, patch_jar=output_dir / "i18n.jar", manifest_path=output_dir / "manifest.json", game_version=game_version, patch_version=patch_version, release_tag=f"tr-{patch_version}")
        result = {"status": "PASS", "mode": "stable", "game_version": game_version, "patch_version": patch_version, "audit_issues": issue_count, "manifest": manifest, "validation": validation["translation"]}
        if diagnostics.exists():
            shutil.rmtree(diagnostics)
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--patch-version", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_approved_release(game_version=args.game_version, patch_version=args.patch_version, output_dir=args.output_dir), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

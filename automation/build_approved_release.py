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
import re
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


def _run(command: list[str]) -> None:
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def _audit_issue_count(summary_path: Path) -> int:
    text = summary_path.read_text(encoding="utf-8-sig")
    matches = AUDIT_ISSUES.findall(text)
    if not matches:
        raise RuntimeError("wakfu_audit summary did not expose a critical-issue count")
    return int(matches[-1])


def build_approved_release(*, game_version: str, patch_version: str, output_dir: Path) -> dict[str, object]:
    state, baseline_path = _approved_baseline(game_version)
    output_dir.mkdir(parents=True, exist_ok=True)
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

        _run([
            sys.executable,
            str(PROJECT_ROOT / "Kaynak_Kodu" / "build_wakfu_jar.py"),
            "--source-jar", str(source),
            "--output-jar", str(patch),
            "--project", str(PROJECT_ROOT / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"),
            "--terminology", str(PROJECT_ROOT / "Ceviri_Verileri" / "terim_duzeltmeleri.json"),
            "--manual-repairs", str(PROJECT_ROOT / "Ceviri_Verileri" / "manual_repairs_v23.json"),
        ])
        _run([
            sys.executable,
            str(PROJECT_ROOT / "Kaynak_Kodu" / "wakfu_audit.py"),
            "--source-jar", str(source),
            "--project", str(PROJECT_ROOT / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"),
            "--terminology", str(PROJECT_ROOT / "Ceviri_Verileri" / "terim_duzeltmeleri.json"),
            "--manual-repairs", str(PROJECT_ROOT / "Ceviri_Verileri" / "manual_repairs_v23.json"),
            "--output-dir", str(audit_dir),
            "--stage", "RELEASE",
        ])
        issue_count = _audit_issue_count(audit_dir / "Wakfu_Ceviri_Ozet.txt")
        if issue_count:
            raise RuntimeError(f"wakfu_audit reported {issue_count} critical issue(s)")
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
        return {"status": "PASS", "mode": "stable", "game_version": game_version, "patch_version": patch_version, "audit_issues": issue_count, "manifest": manifest, "validation": validation["translation"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--patch-version", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_approved_release(game_version=args.game_version, patch_version=args.patch_version, output_dir=args.output_dir), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

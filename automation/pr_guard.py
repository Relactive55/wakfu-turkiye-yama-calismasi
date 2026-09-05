"""Fail-closed guards for production WAKFU localization pull requests.

The updater can have several open candidates while Ankama publishes builds.
This module keeps those candidates distinguishable from disposable fixture PRs
and makes the two safety decisions (merge-time and release-time) pure and
testable.  It deliberately does not call GitHub: the workflow supplies the
read-only PR JSON and performs the minimum write operations only after these
decisions pass.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


PRODUCTION_BRANCH_PREFIX = "codex/wakfu-production-"
PRODUCTION_PR_MARKER = "<!-- WAKFU-PR-TYPE: production-localization -->"
PRODUCTION_BASE_BRANCH = "main"
SHA1 = re.compile(r"^[0-9a-fA-F]{40}$")
COMMIT_SHA = re.compile(r"^[0-9a-fA-F]{7,40}$")
GAME_VERSION = re.compile(r"^\d+(?:\.\d+){1,10}(?:_\d+(?:\.\d+){1,10})?$")
STATUS = re.compile(r"^[A-Z][A-Z0-9_-]{1,31}$")


class PRMetadataError(ValueError):
    """PR metadata is missing, ambiguous, or does not satisfy the contract."""


@dataclass(frozen=True)
class ProductionPRMetadata:
    game_version: str
    source_sha1: str
    base_main_sha: str
    created_at: str
    status: str = "OPEN"
    patch_version: str | None = None

    def __post_init__(self) -> None:
        if not GAME_VERSION.fullmatch(self.game_version):
            raise PRMetadataError("invalid game_version")
        if not SHA1.fullmatch(self.source_sha1):
            raise PRMetadataError("source_sha1 must be a 40-character SHA-1")
        if not COMMIT_SHA.fullmatch(self.base_main_sha):
            raise PRMetadataError("base_main_sha must be a commit SHA")
        if not STATUS.fullmatch(self.status):
            raise PRMetadataError("invalid PR status")
        try:
            timestamp = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PRMetadataError("created_at must be ISO-8601") from exc
        if timestamp.tzinfo is None:
            raise PRMetadataError("created_at must include a timezone")
        if self.patch_version is not None and not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}\.(?:0|[1-9]\d*)", self.patch_version):
            raise PRMetadataError("invalid patch_version")

    @classmethod
    def now(
        cls,
        *,
        game_version: str,
        source_sha1: str,
        base_main_sha: str,
        status: str = "OPEN",
        patch_version: str | None = None,
    ) -> "ProductionPRMetadata":
        return cls(
            game_version=game_version,
            source_sha1=source_sha1.lower(),
            base_main_sha=base_main_sha,
            created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            status=status,
            patch_version=patch_version,
        )

    def as_dict(self) -> dict[str, str]:
        value = {
            "game_version": self.game_version,
            "source_sha1": self.source_sha1.lower(),
            "base_main_sha": self.base_main_sha,
            "created_at": self.created_at,
            "status": self.status,
        }
        if self.patch_version is not None:
            value["patch_version"] = self.patch_version
        return value


def production_branch(game_version: str, source_sha1: str) -> str:
    """Return the only branch shape accepted for a production candidate."""
    if not GAME_VERSION.fullmatch(game_version) or not SHA1.fullmatch(source_sha1):
        raise PRMetadataError("cannot construct a production branch from unverified metadata")
    version = re.sub(r"[^0-9A-Za-z]+", "-", game_version).strip("-")
    return f"{PRODUCTION_BRANCH_PREFIX}{version}-{source_sha1.lower()[:12]}"


def render_pr_body(
    metadata: ProductionPRMetadata,
    *,
    new: int = 0,
    modified: int = 0,
    removed: int = 0,
    unchanged: int = 0,
    tm: int | None = None,
    glossary: int | None = None,
    argos: int | None = None,
    validation: str = "PENDING",
) -> str:
    """Render a parseable body with the immutable source identity up front."""
    lines = [
        PRODUCTION_PR_MARKER,
        "## WAKFU localization update",
        "",
        f"WAKFU Game Version: `{metadata.game_version}`",
        f"Source SHA-1: `{metadata.source_sha1.lower()}`",
        f"Base Main Commit: `{metadata.base_main_sha}`",
        f"Created At (UTC): `{metadata.created_at}`",
        f"Status: `{metadata.status}`",
        "",
        f"- NEW: `{new}`",
        f"- MODIFIED: `{modified}`",
        f"- REMOVED: `{removed}`",
        f"- UNCHANGED: `{unchanged}`",
    ]
    if tm is not None:
        lines.append(f"- Translation Memory: `{tm}`")
    if glossary is not None:
        lines.append(f"- Glossary: `{glossary}`")
    if argos is not None:
        lines.append(f"- Argos: `{argos}`")
    lines.extend(
        [
            f"- Validation: `{validation}`",
            "",
            "The candidate is computed from the last approved production baseline and current main.",
            "No state or baseline is advanced until this PR is reviewed and merged.",
        ]
    )
    return "\n".join(lines) + "\n"


def _field(body: str, label: str) -> str | None:
    match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*`([^`]+)`\s*$", body)
    return match.group(1).strip() if match else None


def parse_pr_body(body: str | None) -> ProductionPRMetadata:
    """Parse exactly one metadata value from a production PR body."""
    if not body or PRODUCTION_PR_MARKER not in body:
        raise PRMetadataError("production PR marker is missing")
    values = {
        "game_version": _field(body, "WAKFU Game Version"),
        "source_sha1": _field(body, "Source SHA-1"),
        "base_main_sha": _field(body, "Base Main Commit"),
        "created_at": _field(body, "Created At (UTC)"),
        "status": _field(body, "Status") or "OPEN",
    }
    if any(values[name] is None for name in ("game_version", "source_sha1", "base_main_sha", "created_at")):
        raise PRMetadataError("production PR metadata is incomplete")
    patch_version = _field(body, "Patch Version")
    return ProductionPRMetadata(**values, patch_version=patch_version)  # type: ignore[arg-type]


def _repo_name(value: Mapping[str, Any]) -> str | None:
    head = value.get("head")
    if isinstance(head, Mapping):
        repo = head.get("repo")
        if isinstance(repo, Mapping) and isinstance(repo.get("full_name"), str):
            return repo["full_name"]
    if isinstance(value.get("head_repo_full_name"), str):
        return value["head_repo_full_name"]
    return None


def is_production_pr(value: Mapping[str, Any], *, repository: str | None = None) -> bool:
    """Recognize only open, same-repository production candidates.

    Test branches (including ``codex/test-*``) and fork PRs are intentionally
    ignored even if a malicious body imitates the metadata fields.
    """
    if str(value.get("state", "open")).lower() != "open":
        return False
    base = value.get("base")
    base_ref = base.get("ref") if isinstance(base, Mapping) else value.get("base_ref")
    if base_ref != PRODUCTION_BASE_BRANCH:
        return False
    head = value.get("head")
    head_ref = head.get("ref") if isinstance(head, Mapping) else value.get("head_ref")
    if not isinstance(head_ref, str) or not head_ref.startswith(PRODUCTION_BRANCH_PREFIX):
        return False
    if "test" in head_ref.lower() or "fixture" in head_ref.lower():
        return False
    if repository is not None and _repo_name(value) != repository:
        return False
    try:
        parse_pr_body(value.get("body"))
    except PRMetadataError:
        return False
    return True


@dataclass(frozen=True)
class PRDecision:
    action: str
    reason: str
    reused_number: int | None = None
    outdated_numbers: tuple[int, ...] = ()
    outdated_comments: tuple[tuple[int, str], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "reused_number": self.reused_number,
            "outdated_numbers": list(self.outdated_numbers),
            "outdated_comments": [
                {"number": number, "body": body} for number, body in self.outdated_comments
            ],
        }


def decide_open_prs(
    prs: Iterable[Mapping[str, Any]],
    *,
    game_version: str,
    source_sha1: str,
    repository: str | None = None,
    has_changes: bool = True,
) -> PRDecision:
    """Decide duplicate reuse/outdating before any branch or PR write."""
    current_sha = source_sha1.lower()
    candidates: list[tuple[Mapping[str, Any], ProductionPRMetadata]] = []
    for pr in prs:
        if not is_production_pr(pr, repository=repository):
            continue
        metadata = parse_pr_body(pr.get("body"))
        candidates.append((pr, metadata))
    if not has_changes:
        outdated_pairs = [
            (int(pr["number"]), metadata)
            for pr, metadata in candidates
            if metadata.game_version != game_version or metadata.source_sha1.lower() != current_sha
        ]
        outdated_pairs.sort(key=lambda item: item[0])
        comments = tuple(
            (
                number,
                superseded_comment(old, current_game_version=game_version)
                if old.game_version != game_version
                else (
                    "OUTDATED WAKFU SOURCE SHA-1\n\n"
                    f"WAKFU Game Version:\n{old.game_version}\n\n"
                    f"Current source SHA-1:\n{current_sha}\n\n"
                    "This PR must not be merged or released until it is regenerated from the current source.\n"
                ),
            )
            for number, old in outdated_pairs
        )
        return PRDecision(
            "NO_CHANGES",
            "NEW/MODIFIED/REMOVED are all zero",
            outdated_numbers=tuple(number for number, _ in outdated_pairs),
            outdated_comments=comments,
        )
    matching = [
        (pr, metadata)
        for pr, metadata in candidates
        if metadata.game_version == game_version and metadata.source_sha1.lower() == current_sha
    ]
    if matching:
        number = matching[0][0].get("number")
        return PRDecision("EXISTING_PR_REUSED", "same game_version and source_sha1 already open", int(number) if number is not None else None)
    outdated_pairs = [
        (int(pr["number"]), metadata)
        for pr, metadata in candidates
        if metadata.game_version != game_version or metadata.source_sha1.lower() != current_sha
    ]
    outdated_pairs.sort(key=lambda item: item[0])
    comments = tuple(
        (
            number,
            superseded_comment(old, current_game_version=game_version)
            if old.game_version != game_version
            else (
                "OUTDATED WAKFU SOURCE SHA-1\n\n"
                f"WAKFU Game Version:\n{old.game_version}\n\n"
                f"Current source SHA-1:\n{current_sha}\n\n"
                "This PR must not be merged or released until it is regenerated from the current source.\n"
            ),
        )
        for number, old in outdated_pairs
    )
    return PRDecision(
        "PREPARE_NEW_PR",
        "no matching production PR",
        outdated_numbers=tuple(number for number, _ in outdated_pairs),
        outdated_comments=comments,
    )


def superseded_comment(old: ProductionPRMetadata, *, current_game_version: str) -> str:
    return (
        "SUPERSEDED BY NEWER WAKFU VERSION\n\n"
        f"Old game version:\n{old.game_version}\n\n"
        f"Current game version:\n{current_game_version}\n\n"
        "This PR must not be released for the current WAKFU version.\n"
    )


def current_wakfu_merge_gate(metadata: ProductionPRMetadata, *, game_version: str, source_sha1: str) -> dict[str, str]:
    """Required status check for merging a production localization PR."""
    if metadata.game_version == game_version and metadata.source_sha1.lower() == source_sha1.lower():
        return {"status": "PASS", "code": "CURRENT_WAKFU_PR"}
    return {
        "status": "FAIL",
        "code": "OUTDATED_WAKFU_PR",
        "message": "PR metadata does not match the current Ankama WAKFU version/source SHA-1",
    }


def release_wakfu_gate(
    *,
    approved_game_version: str,
    approved_source_sha1: str,
    current_game_version: str,
    current_source_sha1: str,
) -> dict[str, str]:
    """Repeat the source identity check immediately before Release creation."""
    if approved_game_version == current_game_version and approved_source_sha1.lower() == current_source_sha1.lower():
        return {"status": "PASS", "code": "CURRENT_WAKFU_RELEASE"}
    return {
        "status": "FAIL",
        "code": "RELEASE_BLOCKED_WAKFU_VERSION_CHANGED",
        "message": "Ankama published a different game version or source SHA-1 during release preparation",
    }


def candidate_conflicts(old_source: Mapping[str, str], current_source: Mapping[str, str]) -> list[str]:
    """Return changed identities; old human candidates are never blindly reused."""
    return sorted(identity for identity in set(old_source) & set(current_source) if old_source[identity] != current_source[identity])


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate open production WAKFU PRs without writing GitHub state")
    parser.add_argument("--prs-json", type=Path, required=True)
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--source-sha1", required=True)
    parser.add_argument("--repository")
    parser.add_argument("--no-changes", action="store_true")
    args = parser.parse_args()
    payload = json.loads(args.prs_json.read_text(encoding="utf-8"))
    prs = payload.get("items", payload) if isinstance(payload, Mapping) else payload
    if not isinstance(prs, list):
        raise SystemExit("open PR JSON must be a list or an {items: [...]} object")
    decision = decide_open_prs(
        prs,
        game_version=args.game_version,
        source_sha1=args.source_sha1,
        repository=args.repository,
        has_changes=not args.no_changes,
    )
    print(json.dumps(decision.as_dict(), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

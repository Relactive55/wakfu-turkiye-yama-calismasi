"""GitHub pull_request status check for the current Ankama WAKFU source.

This workflow is read-only and runs on the untrusted ``pull_request`` event,
never ``pull_request_target``.  Fixture/test branches are skipped.  A
production candidate must carry the metadata produced by :mod:`pr_guard` and
must still point at the source currently advertised by the CDN.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ankama_cdn import AnkamaCdnClient
from .pr_guard import (
    PRODUCTION_BASE_BRANCH,
    PRODUCTION_BRANCH_PREFIX,
    current_wakfu_merge_gate,
    is_production_pr,
    parse_pr_body,
)


def run(event_path: Path, *, repository: str | None = None) -> dict[str, str]:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise RuntimeError("GitHub event payload is not an object")
    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        return {"status": "SKIP", "code": "NOT_A_PULL_REQUEST"}
    # Test/fixture PRs are not production candidates and must not consume the
    # CDN gate.  is_production_pr also rejects fork branches when repository
    # is supplied by the workflow.
    if not is_production_pr(pr, repository=repository):
        return {"status": "SKIP", "code": "NON_PRODUCTION_PR"}
    metadata = parse_pr_body(pr.get("body"))
    client = AnkamaCdnClient()
    game_version = client.latest_version()
    entry, _ = client.target_entry(game_version)
    result = current_wakfu_merge_gate(metadata, game_version=game_version, source_sha1=entry.sha1)
    result = {**result, "game_version": game_version, "source_sha1": entry.sha1}
    if result["status"] != "PASS":
        raise RuntimeError(result["code"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--repository")
    args = parser.parse_args()
    result = run(args.event, repository=args.repository)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)

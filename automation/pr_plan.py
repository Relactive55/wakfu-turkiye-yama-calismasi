"""Render a production PR plan without calling GitHub.

The plan is metadata-first: the source identity is part of the PR body and
the branch name, while state/baseline advancement is deliberately left to the
post-merge transaction.  This keeps an open candidate from becoming an
approved baseline merely because a branch was created.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .pr_guard import ProductionPRMetadata, production_branch, render_pr_body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-version", required=True)
    parser.add_argument("--source-sha1", required=True)
    parser.add_argument("--base-main-sha", required=True)
    parser.add_argument("--new", type=int, required=True)
    parser.add_argument("--modified", type=int, required=True)
    parser.add_argument("--removed", type=int, required=True)
    parser.add_argument("--unchanged", type=int, default=0)
    parser.add_argument("--tm", type=int)
    parser.add_argument("--glossary", type=int)
    parser.add_argument("--argos", type=int)
    parser.add_argument("--created-at", help="UTC ISO-8601 timestamp; defaults to now")
    args = parser.parse_args()
    created_at = args.created_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    metadata = ProductionPRMetadata(
        game_version=args.game_version,
        source_sha1=args.source_sha1.lower(),
        base_main_sha=args.base_main_sha,
        created_at=created_at,
    )
    body = render_pr_body(
        metadata,
        new=args.new,
        modified=args.modified,
        removed=args.removed,
        unchanged=args.unchanged,
        tm=args.tm,
        glossary=args.glossary,
        argos=args.argos,
    )
    changed = [
        "Ceviri_Verileri/wakfu_tr_ceviri.json",
        f"Raporlar/wakfu-update-{args.game_version}.json",
    ]
    print(
        json.dumps(
            {
                "branch": production_branch(args.game_version, args.source_sha1),
                "commit": f"WAKFU localization update for {args.game_version}",
                "changed_files": changed,
                "pr_title": f"WAKFU localization update: {args.game_version}",
                "pr_body": body,
                "metadata": metadata.as_dict(),
                "state_advanced": False,
                "baseline_advanced": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

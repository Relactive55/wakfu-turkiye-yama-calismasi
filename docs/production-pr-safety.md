# Production WAKFU PR safety

Production localization candidates are source-identity bound.  A generated
candidate uses the branch shape
`codex/wakfu-production-<game-version>-<source-sha1-prefix>` and its body must
contain the marker `WAKFU-PR-TYPE: production-localization` plus:

- `WAKFU Game Version`
- `Source SHA-1`
- `Base Main Commit`
- `Created At (UTC)`
- `Status`

`automation.pr_guard` is the single decision point before a write stage:

- an open candidate with the same `(game_version, source_sha1)` is reused and
  reported as `EXISTING_PR_REUSED`;
- a candidate with a different source identity is marked
  `SUPERSEDED/OUTDATED` by comment, but is not closed, merged, or released;
- fixture/test branches are ignored;
- `NEW=MODIFIED=REMOVED=0` is `NO_CHANGES` and cannot create a branch or PR.

The current-version workflow runs on `pull_request`, never
`pull_request_target`, and has read-only permissions.  It fails with
`OUTDATED_WAKFU_PR` when the current CDN game version or source SHA-1 differs
from the PR metadata.  The Release builder repeats the same identity check
before staging assets and immediately before Release creation; a mismatch is
`RELEASE_BLOCKED_WAKFU_VERSION_CHANGED`.

Human translations from an old candidate are review material only.  They are
not copied into a new candidate without an identity/conflict check.  The new
candidate is always computed from the last approved baseline and current main.
State and baseline files are advanced only by the post-merge transaction, not
by opening a PR.

Configure the status check named **Current WAKFU version/source gate** as a
required check on `main` after verifying the repository's branch-protection
settings.  Do not enable auto-merge or auto-approval.

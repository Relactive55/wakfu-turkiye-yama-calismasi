from __future__ import annotations

import unittest

from automation.pr_guard import (
    PRODUCTION_BRANCH_PREFIX,
    ProductionPRMetadata,
    candidate_conflicts,
    current_wakfu_merge_gate,
    decide_open_prs,
    is_production_pr,
    production_branch,
    release_wakfu_gate,
    render_pr_body,
    superseded_comment,
)


REPOSITORY = "Relactive/wakfu-turkiye-yama-calismasi"
SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40


def production_pr(number: int, version: str, source_sha: str, *, created_at: str = "2026-09-05T00:00:00Z") -> dict:
    metadata = ProductionPRMetadata(version, source_sha, "1" * 40, created_at)
    return {
        "number": number,
        "state": "open",
        "base": {"ref": "main"},
        "head": {"ref": production_branch(version, source_sha), "repo": {"full_name": REPOSITORY}},
        "body": render_pr_body(metadata),
    }


class PRGuardTests(unittest.TestCase):
    def test_metadata_body_and_branch_are_source_bound(self) -> None:
        pr = production_pr(1, "6.0_1.92.1.5172.314", SHA_A)
        self.assertTrue(is_production_pr(pr, repository=REPOSITORY))
        self.assertTrue(pr["head"]["ref"].startswith(PRODUCTION_BRANCH_PREFIX))
        self.assertIn("WAKFU Game Version:", pr["body"])
        self.assertIn("Source SHA-1:", pr["body"])
        self.assertIn("Base Main Commit:", pr["body"])
        self.assertIn("Status:", pr["body"])

    def test_a_same_version_and_sha_reuses_open_pr(self) -> None:
        decision = decide_open_prs(
            [production_pr(11, "1.92.1.5172.314", SHA_A)],
            game_version="1.92.1.5172.314",
            source_sha1=SHA_A,
            repository=REPOSITORY,
        )
        self.assertEqual(decision.action, "EXISTING_PR_REUSED")
        self.assertEqual(decision.reused_number, 11)

    def test_b_new_version_outdates_old_and_prepares_new_pr(self) -> None:
        old = production_pr(12, "1.92.1.5172.314", SHA_A)
        decision = decide_open_prs([old], game_version="1.93.0.1", source_sha1=SHA_B, repository=REPOSITORY)
        self.assertEqual(decision.action, "PREPARE_NEW_PR")
        self.assertEqual(decision.outdated_numbers, (12,))
        self.assertIn("SUPERSEDED BY NEWER WAKFU VERSION", superseded_comment(
            ProductionPRMetadata("1.92.1.5172.314", SHA_A, "1" * 40, "2026-09-05T00:00:00Z"),
            current_game_version="1.93.0.1",
        ))

    def test_c_same_version_different_source_sha_is_outdated(self) -> None:
        decision = decide_open_prs(
            [production_pr(13, "1.92.1.5172.314", SHA_A)],
            game_version="1.92.1.5172.314",
            source_sha1=SHA_B,
            repository=REPOSITORY,
        )
        self.assertEqual(decision.action, "PREPARE_NEW_PR")
        self.assertEqual(decision.outdated_numbers, (13,))

    def test_d_b_then_c_never_uses_old_pr_output(self) -> None:
        b = production_pr(14, "1.93.0.1", SHA_B)
        c = production_pr(15, "1.94.0.1", SHA_C)
        decision = decide_open_prs([b], game_version="1.94.0.1", source_sha1=SHA_C, repository=REPOSITORY)
        self.assertEqual(decision.outdated_numbers, (14,))
        decision = decide_open_prs([b, c], game_version="1.95.0.1", source_sha1=SHA_D, repository=REPOSITORY)
        self.assertEqual(decision.outdated_numbers, (14, 15))
        self.assertEqual(decision.action, "PREPARE_NEW_PR")
        # A source change makes an old candidate unsafe to reuse.
        self.assertEqual(candidate_conflicts({"k#1": "old"}, {"k#1": "new"}), ["k#1"])

    def test_e_only_current_candidate_can_pass_merge_gate(self) -> None:
        old = ProductionPRMetadata("1.93.0.1", SHA_B, "1" * 40, "2026-09-05T00:00:00Z")
        current = ProductionPRMetadata("1.94.0.1", SHA_C, "1" * 40, "2026-09-05T00:00:00Z")
        self.assertEqual(current_wakfu_merge_gate(old, game_version="1.94.0.1", source_sha1=SHA_C)["code"], "OUTDATED_WAKFU_PR")
        self.assertEqual(current_wakfu_merge_gate(current, game_version="1.94.0.1", source_sha1=SHA_C)["status"], "PASS")

    def test_f_manual_outdated_merge_and_release_are_blocked(self) -> None:
        old = ProductionPRMetadata("1.93.0.1", SHA_B, "1" * 40, "2026-09-05T00:00:00Z")
        self.assertEqual(current_wakfu_merge_gate(old, game_version="1.94.0.1", source_sha1=SHA_C)["code"], "OUTDATED_WAKFU_PR")
        self.assertEqual(
            release_wakfu_gate(
                approved_game_version="1.93.0.1",
                approved_source_sha1=SHA_B,
                current_game_version="1.94.0.1",
                current_source_sha1=SHA_C,
            )["code"],
            "RELEASE_BLOCKED_WAKFU_VERSION_CHANGED",
        )

    def test_g_cdn_change_during_release_fails_closed(self) -> None:
        result = release_wakfu_gate(
            approved_game_version="1.94.0.1",
            approved_source_sha1=SHA_C,
            current_game_version="1.95.0.1",
            current_source_sha1=SHA_D,
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["code"], "RELEASE_BLOCKED_WAKFU_VERSION_CHANGED")

    def test_h_age_does_not_invalidate_unchanged_candidate(self) -> None:
        old = production_pr(16, "1.92.1.5172.314", SHA_A, created_at="2026-06-07T00:00:00Z")
        decision = decide_open_prs([old], game_version="1.92.1.5172.314", source_sha1=SHA_A, repository=REPOSITORY)
        self.assertEqual(decision.action, "EXISTING_PR_REUSED")

    def test_i_fixture_pr_is_not_production(self) -> None:
        fixture = {
            "number": 17,
            "state": "open",
            "base": {"ref": "main"},
            "head": {"ref": "codex/test-wakfu-update-pipeline-20260905", "repo": {"full_name": REPOSITORY}},
            "body": "## TEST PIPELINE ONLY\nDO NOT MERGE",
        }
        self.assertFalse(is_production_pr(fixture, repository=REPOSITORY))
        decision = decide_open_prs([fixture], game_version="1.92.1.5172.314", source_sha1=SHA_A, repository=REPOSITORY)
        self.assertEqual(decision.outdated_numbers, ())

    def test_j_no_changes_never_creates_a_pr(self) -> None:
        decision = decide_open_prs([], game_version="1.93.0.1", source_sha1=SHA_B, has_changes=False)
        self.assertEqual(decision.action, "NO_CHANGES")


if __name__ == "__main__":
    unittest.main()

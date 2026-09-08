from __future__ import annotations

import unittest

from automation.external_distribution_guard import scan_text


class ExternalDistributionGuardTests(unittest.TestCase):
    def test_github_release_binary_is_allowed(self) -> None:
        self.assertEqual(
            scan_text(
                "https://github.com/Relactive55/wakfu-turkiye-yama-calismasi/releases/download/installer-6.5.11/Wakfu.Turkce.Yama.6.5.11.exe",
                source="README.md",
            ),
            [],
        )

    def test_external_binary_download_is_rejected(self) -> None:
        url = "https://downloads.example.invalid/tool/setup" + ".exe"
        violations = scan_text(url, source="README.md")
        self.assertEqual(len(violations), 1)
        self.assertIn("external binary download URL", violations[0])

    def test_shortened_url_is_rejected_even_without_extension(self) -> None:
        url = "https://" + "bit.ly" + "/wakfu-download"
        violations = scan_text(url, source="docs/install.md")
        self.assertEqual(len(violations), 1)
        self.assertIn("shortened/redirect URL", violations[0])

    def test_official_non_binary_links_are_allowed(self) -> None:
        self.assertEqual(scan_text("https://www.wakfu.com/fr/mmorpg/telecharger", source="game text"), [])


if __name__ == "__main__":
    unittest.main()

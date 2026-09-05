from __future__ import annotations

import hashlib
import os
import unittest
from pathlib import Path

from automation.argos_engine import install_locked_model
from automation.localization_pipeline import format_ok, mask_tokens, restore_tokens


FIXTURE = r"""Hello adventurer.
You have [#1] items.
[st1]Attack[/st1]
[pl]items[/pl]
Line 1\nLine 2
\<b>Damage\</b>
{[condition]?Yes:No}"""
EXPECTED_SHA256 = "2d553a00880a0c21dea5b1c375535659e6bf18c9bf2ce9847c2a2fd2ff50316a"


class ArgosRuntime(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("ARGOS_MODEL_PATH"), "ARGOS_MODEL_PATH is required for the isolated Argos runtime job")
    def test_locked_real_fixture(self) -> None:
        model = Path(os.environ["ARGOS_MODEL_PATH"])
        lock = Path(os.environ.get("ARGOS_MODEL_LOCK", Path(__file__).parents[1] / "model-lock.json"))
        self.assertEqual(hashlib.sha256(model.read_bytes()).hexdigest(), EXPECTED_SHA256)
        self.assertEqual(model.stat().st_size, 124742526)
        translate = install_locked_model(model, lock)
        masked, tokens = mask_tokens(FIXTURE)
        translated = translate(masked)
        restored = restore_tokens(translated, tokens)
        self.assertTrue(format_ok(FIXTURE, restored), restored)
        self.assertEqual([m for m in tokens], ["[#1]", "[st1]", "[/st1]", "[pl]", "[/pl]", r"\n", "<b>", "</b>", "{[condition]?Yes:No}"])
        self.assertNotIn("ZXQ", restored)


if __name__ == "__main__":
    unittest.main()

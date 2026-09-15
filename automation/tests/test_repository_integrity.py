from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RepositoryIntegrityTests(unittest.TestCase):
    def test_json_files_have_no_duplicate_keys(self) -> None:
        failures: list[str] = []

        for path in sorted(ROOT.rglob("*.json")):
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue

            duplicates: list[str] = []

            def reject_duplicates(items: list[tuple[str, object]]) -> dict[str, object]:
                result: dict[str, object] = {}
                for key, value in items:
                    if key in result:
                        duplicates.append(key)
                    result[key] = value
                return result

            try:
                json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=reject_duplicates)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                failures.append(f"{path.relative_to(ROOT)}: geçersiz JSON ({exc})")
                continue

            if duplicates:
                failures.append(
                    f"{path.relative_to(ROOT)}: yinelenen anahtarlar: {', '.join(sorted(set(duplicates)))}"
                )

        self.assertFalse(failures, "\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Produce review proposals for altered official skill or item references.

Whole-row machine translations from this tool are intentionally report-only.
They must be moved into the exact, human-reviewed repair table before they can
affect the project dictionaries.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from translate_visible_states_v44 import (
    format_tokens,
    load_json,
    protect_text,
    protected_terms,
    save_json,
    source_values,
    translate_batch,
)


# These families display locations, achievements, workstations, objects or
# titles.  A phrase can legitimately be localized there even when an unrelated
# item happens to have the same English title.
EXCLUDED_PREFIXES = (
    "content.26.", "content.34.", "content.35.", "content.54.", "content.59.",
    "content.61.", "content.62.", "content.66.", "content.77.", "content.78.",
    "content.80.", "content.82.", "content.85.", "content.89.", "content.106.",
    "content.121.", "content.124.", "content.137.", "content.155.",
    "overhead.", "desc.mru.",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Disabled safety switch retained only to reject older commands.",
    )
    args = parser.parse_args()

    if args.apply:
        parser.error(
            "--apply is disabled: review proposals and add approved rows to "
            "apply_v44_repairs.py instead"
        )

    root = args.project_root.resolve()
    data_dir = root / "Ceviri_Verileri"
    report_dir = root / "Raporlar"
    sources = source_values(root / "Oyun_Kaynaklari" / "Guncel" / "i18n_en.jar")
    project_path = data_dir / "wakfu_tr_ceviri.json"
    manual_path = data_dir / "manual_repairs_v23.json"
    project = load_json(project_path)
    manual = load_json(manual_path)

    flagged: set[str] = set()
    deep_path = report_dir / "Wakfu_Derin_Denetim.tsv"
    with deep_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if row.get("Kod") != "PROTECTED_REFERENCE_CHANGED":
                continue
            key = row.get("Anahtar", "")
            if key.startswith(EXCLUDED_PREFIXES):
                continue
            if key in sources:
                flagged.add(key)

    names = protected_terms(sources)
    mentions: dict[str, list[str]] = {
        key: [name for name in names if name in sources[key]]
        for key in flagged
    }
    targets = {key: sources[key] for key in flagged if mentions[key]}
    unique_sources = sorted(set(targets.values()))
    cache_path = report_dir / "Wakfu_Korunan_Referans_Ceviri_Onbellek_v44.json"
    cache = load_json(cache_path)
    results = dict(cache)
    pending = [source for source in unique_sources if source not in results]
    print(json.dumps({
        "flagged": len(flagged), "target_keys": len(targets),
        "unique_sources": len(unique_sources), "pending": len(pending),
    }, ensure_ascii=False), flush=True)

    batches: list[list[tuple[str, str, dict[str, str]]]] = []
    batch: list[tuple[str, str, dict[str, str]]] = []
    chars = 0
    for source in pending:
        protected, replacements = protect_text(source, names)
        if "\\n" in protected or "\n" in protected:
            if batch:
                batches.append(batch)
                batch, chars = [], 0
            batches.append([(source, protected, replacements)])
            continue
        if batch and (len(batch) >= 16 or chars + len(protected) > 1200):
            batches.append(batch)
            batch, chars = [], 0
        batch.append((source, protected, replacements))
        chars += len(protected) + 1
    if batch:
        batches.append(batch)

    for index, items in enumerate(batches, 1):
        results.update(translate_batch(items))
        if index % 10 == 0 or index == len(batches):
            snapshot = dict(cache)
            snapshot.update({source: results[source] for source in unique_sources if source in results})
            save_json(cache_path, snapshot)
            print(f"PROGRESS|{index}|{len(batches)}", flush=True)
        time.sleep(0.12)

    proposals: dict[str, str] = {}
    rejected: list[dict[str, object]] = []
    for key, source in targets.items():
        target = results.get(source, "").strip()
        missing_names = [name for name in mentions[key] if name not in target]
        if not target or format_tokens(source) != format_tokens(target) or missing_names:
            rejected.append({"key": key, "missing_names": missing_names})
            continue
        proposals[key] = target

    proposal_path = report_dir / "Wakfu_Korunan_Referans_Onarimlari_v44.json"
    save_json(proposal_path, proposals)
    print(json.dumps({
        "proposals": len(proposals), "rejected": len(rejected),
        "rejected_samples": rejected[:20], "applied": False,
        "proposal_file": str(proposal_path),
    }, ensure_ascii=False), flush=True)
    return 0 if not rejected else 2


if __name__ == "__main__":
    raise SystemExit(main())

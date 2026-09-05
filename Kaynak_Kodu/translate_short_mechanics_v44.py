#!/usr/bin/env python3
"""Translate short visible content.33 mechanic/effect labels, not code rows."""

from __future__ import annotations

import argparse
import json
import re
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


INTERNAL_WORD_RE = re.compile(
    r"(?i)^(?:test(?:\s*\d+)?|wip|ss|a|blah|flag|lol|biduule|bliblobla)$"
)

MANUAL = {
    "Excarnal Possession": "Bedensiz Ele Geçirme",
    "vulnerable": "Savunmasız",
    "Vulnerable": "Savunmasız",
    "Phase II": "Aşama II",
    "Phase III": "Aşama III",
    "Ultimate Phase": "Son Aşama",
    "Attraction": "Çekme",
    "AP Removal": "AP Kaybı",
    "MP Removal": "MP Kaybı",
    "Infinite MP": "Sınırsız MP",
    "Regeneration state": "Yenilenme Durumu",
    "Cheese": "Peynir",
    "Tomatoes": "Domates",
    "Peppers": "Biber",
    "Doubles AP": "AP'yi İkiye Katlar",
    "Doubles MP": "MP'yi İkiye Katlar",
    "Halves AP": "AP'yi Yarıya İndirir",
    "Switch": "Değiştir",
    "Burning Lava": "Yanan Lav",
    "Weapons": "Silahlar",
    "Sapphire Hunt": "Safir Avı",
    "Ruby Hunt": "Yakut Avı",
    "Emerald Hunt": "Zümrüt Avı",
    "Topaz Hunt": "Topaz Avı",
    "Pushback": "Geri İtme",
    "Lethal Stakes": "Ölümcül Bahisler",
    "Air Note": "Hava Notası",
    "Lightning Flag": "Yıldırım Bayrağı",
    "Immortal": "Ölümsüz",
    "Running on Stilts": "Tahta Bacaklarla Koşma",
    "New Moon": "Yeni Ay",
    "Tenderised": "Yumuşatılmış",
    "Healing": "İyileştirme",
    "Anti-Abuse": "Suistimal Önleme",
    "Duels state": "Düello Durumu",
    "Teleportation": "Işınlanma",
    "Unlockable": "Kilidi Açılabilir",
    "Pion Noir": "Siyah Piyon",
    "Pion Blanc": "Beyaz Piyon",
    "Equipe Bleue": "Mavi Takım",
    "Equipe Rouge": "Kırmızı Takım",
    "Crocoburio gets up": "Crocoburio Ayağa Kalkar",
    "Pastryfaction Aura": "Pastryfaction Aurası",
    "Bwork Exhilaration": "Bwork Coşkusu",
    "Bwork Madness": "Bwork Çılgınlığı",
    "Shrill Waterwhisp": "Tiz Waterwhisp",
    "Shrill Earthwhisp": "Tiz Earthwhisp",
    "Shrill Firewhisp": "Tiz Firewhisp",
    "Shrill Airwhisp": "Tiz Airwhisp",
    "Lin Kawaii Hopeful": "Lin Kawaii Adayı",
    "Shilay Lyu Hopeful": "Shilay Lyu Adayı",
    "Lin Kawaii Hero": "Lin Kawaii Kahramanı",
    "Shilay Lyu Hero": "Shilay Lyu Kahramanı",
    "Lin Kawaii Novice": "Lin Kawaii Çırağı",
    "Shilay Lyu Novice": "Shilay Lyu Çırağı",
}


def visible(value: str) -> str:
    result = value
    for token in format_tokens(value):
        result = result.replace(token, " ")
    return re.sub(r"\s+", " ", result).strip()


def is_internal(source: str) -> bool:
    shown = visible(source)
    if not re.search(r"[A-Za-z]", shown):
        return True
    if re.fullmatch(
        r"(?i)[+\-\d\s]*(?:AP|MP|WP|HP|PdV|PA|PM)(?:\s+[A-Za-z]{1,3})?",
        shown,
    ):
        return True
    if INTERNAL_WORD_RE.fullmatch(source.strip()):
        return True
    if source.startswith((
        "Clef simple Temple remove", "Clef boss Temple remove",
        "name = ", "nom : ", "PO min : ",
    )):
        return True
    if len(re.findall(r"[A-Za-z]\w*\s*=\s*\[(?:#|@)?[A-Za-z]\w*\]", source)) >= 2:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    data_dir = root / "Ceviri_Verileri"
    report_dir = root / "Raporlar"
    sources = source_values(root / "Oyun_Kaynaklari" / "Guncel" / "i18n_en.jar")
    project_path = data_dir / "wakfu_tr_ceviri.json"
    manual_path = data_dir / "manual_repairs_v23.json"
    project = load_json(project_path)
    manual = load_json(manual_path)
    cache_path = report_dir / "Wakfu_Kisa_Mekanik_Ceviri_Onbellek_v44.json"
    cache = load_json(cache_path)
    names = protected_terms(sources)
    official_names = {
        source.strip()
        for key, source in sources.items()
        if key.startswith(("content.3.", "content.15.")) and source.strip()
    }

    targets: dict[str, str] = {}
    skipped = 0
    skipped_official = 0
    for key, source in sources.items():
        if not key.startswith("content.33."):
            continue
        if project.get(key, "").strip() or manual.get(key, "").strip():
            continue
        if source.strip().rstrip("!?.") in official_names:
            skipped_official += 1
            continue
        if is_internal(source):
            skipped += 1
            continue
        targets[key] = source

    unique_sources = sorted(set(targets.values()))
    results = dict(cache)
    results.update(MANUAL)
    pending = [source for source in unique_sources if source not in results]
    print(json.dumps({
        "target_keys": len(targets), "unique_sources": len(unique_sources),
        "pending": len(pending), "skipped_internal": skipped,
        "skipped_official": skipped_official,
    }, ensure_ascii=False), flush=True)

    batches: list[list[tuple[str, str, dict[str, str]]]] = []
    batch: list[tuple[str, str, dict[str, str]]] = []
    chars = 0
    for source in pending:
        protected, replacements = protect_text(source, names)
        if batch and (len(batch) >= 20 or chars + len(protected) > 1400):
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
    generated_sources = set(cache) | set(MANUAL)
    for key, source in sources.items():
        if key.startswith("content.33.") and source in generated_sources:
            generated = MANUAL.get(source, project.get(key, results.get(source, ""))).strip()
            if generated and format_tokens(source) == format_tokens(generated):
                proposals[key] = generated
    for key, source in targets.items():
        target = results.get(source, "").strip()
        if target and format_tokens(source) == format_tokens(target):
            proposals[key] = target
    for key, source in sources.items():
        if key.startswith("content.33.") and source in MANUAL:
            proposals[key] = MANUAL[source]
    proposal_path = report_dir / "Wakfu_Kisa_Mekanik_Ceviri_Onerileri_v44.json"
    save_json(proposal_path, proposals)
    snapshot = dict(cache)
    for key, target in proposals.items():
        snapshot[sources[key]] = target
    save_json(cache_path, snapshot)
    if args.apply:
        for key, target in proposals.items():
            project[key] = target
            manual[key] = target
        save_json(project_path, project)
        save_json(manual_path, manual)
    rejected = len(targets) - sum(key in proposals for key in targets)
    print(json.dumps({
        "proposals": len(proposals), "rejected": rejected,
        "applied": bool(args.apply), "proposal_file": str(proposal_path),
    }, ensure_ascii=False), flush=True)
    return 0 if rejected == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

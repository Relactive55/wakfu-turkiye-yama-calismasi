#!/usr/bin/env python3
"""Fill previously hidden WAKFU content.6/content.8 UI state names.

Only non-protected, player-facing effect/buff/status title rows are touched.
The script is idempotent, caches remote results, preserves format tokens and
official skill/item names, and writes both translation stores atomically.
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path


FORMAT_RE = re.compile(
    r"\{\[[^\]]+\]\?(?:s|es)?:\}|\\[ntr]|\[[^\]]+\]|<(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>|%[A-Za-z_][A-Za-z0-9_.-]*%"
)
INTERNAL_RE = re.compile(
    r"(?i)(?:^\[Dead\]|\bListening$|^Listen\b|\(listening\)$|\bflag$|"
    r"^[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+$|^test(?:\s*\d+)?$|^gameplay$|"
    r"^basic container$|^removal$)"
)

# These effect/status rows are real official names tied to skills or game
# entities and are intentionally kept in English by the main policy.
PROTECTED_KEYS = {
    "content.6.789", "content.6.1851", "content.6.1852", "content.6.1853",
    "content.6.1854", "content.6.2135", "content.8.923", "content.8.1555",
    "content.8.1964", "content.8.1965", "content.8.3425", "content.8.3430",
    "content.8.3431", "content.8.3442", "content.8.4092", "content.8.5449",
    "content.8.7526", "content.8.7757", "content.8.7792", "content.8.8306",
    "content.8.8743", "content.8.9048",
}

MANUAL = {
    "Blindness": "Körlük",
    "Confusion": "Kafa Karışıklığı",
    "Living-Dead": "Yaşayan Ölü",
    "Freezing": "Donma",
    "Stunned": "Sersemlemiş",
    "Lead Legs": "Ağırlaşmış Bacaklar",
    "Divine Silence": "İlahi Sessizlik",
    "Blood Loss": "Kan Kaybı",
    "Motherly Love": "Anne Sevgisi",
    "Water Aura": "Su Aurası",
    "Air Aura": "Hava Aurası",
    "Fire Aura": "Ateş Aurası",
    "Earth Aura": "Toprak Aurası",
    "Maternal Fury": "Anaç Öfke",
    "Poisoning": "Zehirlenme",
    "Unearthed": "Gün Yüzüne Çıkarılmış",
    "Escaped": "Kaçmış",
    "Prisoner": "Tutsak",
    "Immortal": "Ölümsüz",
    "Banished": "Sürgün Edilmiş",
    "Wounded": "Yaralı",
    "Air Circle": "Hava Çemberi",
    "Application of Gely Drop": "Gely Damlası Uygulaması",
    "Invulnerability": "Dokunulmazlık",
    "Void": "Boşluk",
    "Prospecting": "Ganimet Bulma",
    "Boss Phase": "Boss Aşaması",
    "Pizz'larve Order": "Pizz'larva Siparişi",
    "Major Shushu I": "Büyük Shushu I",
    "Major Shushu II": "Büyük Shushu II",
    "Major Shushu III": "Büyük Shushu III",
    "Major Shushu IV": "Büyük Shushu IV",
    "Stabilized": "Sabitlenmiş",
    "Even Turn": "Çift Tur",
    "Odd Turn": "Tek Tur",
    "MP Venom": "MP Zehri",
    "Elemental Weakness": "Element Zayıflığı",
    "Ultimate Boss": "Nihai Boss",
    "Intelligence": "Zekâ",
    "Critical Failures": "Kritik Başarısızlıklar",
    "Priceless Item": "Paha Biçilmez Eşya",
    "Position": "Konum",
    "Loot": "Ganimet",
    "Heal": "İyileştirme",
    "Wild Dragoturkey": "Vahşi Dragoturkey",
    "Draw": "Beraberlik",
    "Poison": "Zehir",
    "Area": "Alan",
    "Blue Start": "Mavi Başlangıç",
    "Mental Spike": "Zihinsel Diken",
    "Bonus Application": "Bonus Uygulaması",
    "Grace Bonus": "Zarafet Bonusu",
    "Kokorror": "Kokorror",
    "Firm Foot": "Sağlam Basış",
    "Chance": "Şans",
    "Disturbed": "Rahatsız",
    "Bothered": "Rahatsız",
    "Incompressible": "Sıkıştırılamaz",
    "Inactive": "Etkin Değil",
    "Void Omen": "Boşluk Alameti",
    "Krosmoprotection": "Krosmo Koruması",
    "Amybian Poison": "Amybian Zehri",
    "Unliving Fury": "Ölümsüz Öfke",
    "Timew": "Timew",
    "Leekult": "Leekult",
    "Backwash": "Geri Tepme",
    "Aquatic Regeneration": "Su Yenilenmesi",
    "Movement Points": "Hareket Puanları",
    "Transpo Flag": "Işınlanma Bayrağı",
}


def load_json(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON nesnesi bekleniyordu: {path}")
    return {str(key): str(item) for key, item in value.items()}


def save_json(path: Path, value: dict[str, str]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def source_values(jar_path: Path) -> dict[str, str]:
    with zipfile.ZipFile(jar_path, "r") as archive:
        name = "texts_en.properties"
        if name not in archive.namelist():
            name = "texts_en_cleaned.properties"
        result: dict[str, str] = {}
        with archive.open(name) as raw:
            for binary_line in raw:
                line = binary_line.decode("utf-8-sig").rstrip("\r\n")
                if not line or line.startswith(("#", "!")) or "=" not in line:
                    continue
                key, source = line.split("=", 1)
                result[key] = source
        return result


def format_tokens(value: str) -> list[str]:
    return FORMAT_RE.findall(value)


def protected_terms(sources: dict[str, str]) -> list[str]:
    values = {
        source.strip()
        for key, source in sources.items()
        if key.startswith(("content.3.", "content.15."))
        and len(source.strip()) >= 4
        and 2 <= len(source.split()) <= 8
    }
    # Longest first prevents a short name from splitting a longer official one.
    return sorted(values, key=lambda item: (-len(item), item))


def protect_text(value: str, names: list[str]) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}
    protected = value
    marker_index = 0
    for name in names:
        if name not in protected:
            continue
        marker = f"ZXQ{marker_index}WAKFUZ"
        protected = protected.replace(name, marker)
        replacements[marker] = name
        marker_index += 1
    token_index = 0
    for token in format_tokens(protected):
        marker = f"ZXQFMT{token_index}WAKFUZ"
        protected = protected.replace(token, marker, 1)
        replacements[marker] = token
        token_index += 1
    return protected, replacements


def restore_text(value: str, replacements: dict[str, str]) -> str:
    restored = value
    for marker, original in replacements.items():
        restored = restored.replace(marker, original)
    return restored.strip()


def request_translation(text: str) -> str:
    query = urllib.parse.urlencode({
        "client": "dict-chrome-ex", "sl": "en", "tl": "tr", "q": text,
    })
    url = "https://clients5.google.com/translate_a/t?" + query
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, list) and payload and isinstance(payload[0], str):
                return payload[0]
            raise RuntimeError("Beklenmeyen çeviri yanıtı")
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            last_error = exc
            time.sleep(min(8.0, 0.6 * (2**attempt)))
    raise RuntimeError(f"Çeviri servisi yanıt vermedi: {last_error}")


def translate_batch(items: list[tuple[str, str, dict[str, str]]]) -> dict[str, str]:
    """Translate a newline batch, recursively splitting if line count changes."""
    if not items:
        return {}
    joined = "\n".join(item[1] for item in items)
    translated = request_translation(joined)
    lines = translated.splitlines()
    if len(lines) != len(items):
        if len(items) == 1:
            lines = [translated]
        else:
            middle = len(items) // 2
            result = translate_batch(items[:middle])
            result.update(translate_batch(items[middle:]))
            return result
    result: dict[str, str] = {}
    for (source, _, replacements), line in zip(items, lines):
        result[source] = restore_text(line, replacements)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    root = args.project_root.resolve()
    data_dir = root / "Ceviri_Verileri"
    report_dir = root / "Raporlar"
    source_jar = root / "Oyun_Kaynaklari" / "Guncel" / "i18n_en.jar"
    project_path = data_dir / "wakfu_tr_ceviri.json"
    manual_path = data_dir / "manual_repairs_v23.json"
    cache_path = report_dir / "Wakfu_Buff_Ceviri_Onbellek_v44.json"

    sources = source_values(source_jar)
    project = load_json(project_path)
    manual = load_json(manual_path)
    cache = load_json(cache_path)
    if args.refresh:
        previous_proposals = load_json(report_dir / "Wakfu_Buff_Durum_Ceviri_Onerileri_v44.json")
        for key in previous_proposals:
            project.pop(key, None)
            manual.pop(key, None)
        cache = {}
    names = protected_terms(sources)
    official_names = {
        source.strip()
        for key, source in sources.items()
        if key.startswith(("content.3.", "content.15.")) and source.strip()
    }
    for key, source in sources.items():
        if key.startswith(("content.6.", "content.8.")) and source.strip() in official_names:
            project.pop(key, None)
            manual.pop(key, None)

    targets: dict[str, str] = {}
    skipped_internal = 0
    skipped_protected = 0
    for key, source in sources.items():
        if not key.startswith(("content.6.", "content.8.")):
            continue
        if project.get(key, "").strip() or manual.get(key, "").strip():
            continue
        if key in PROTECTED_KEYS or source.strip() in official_names:
            skipped_protected += 1
            continue
        if INTERNAL_RE.search(source.strip()) or not re.search(r"[A-Za-z]", source):
            skipped_internal += 1
            continue
        targets[key] = source

    unique_sources = sorted(set(targets.values()))
    results = dict(cache)
    results.update(MANUAL)
    pending = [source for source in unique_sources if source not in results]
    print(json.dumps({
        "target_keys": len(targets), "unique_sources": len(unique_sources),
        "cached_or_manual": len(unique_sources) - len(pending),
        "pending": len(pending), "skipped_internal": skipped_internal,
        "skipped_protected": skipped_protected,
    }, ensure_ascii=False), flush=True)

    batches: list[list[tuple[str, str, dict[str, str]]]] = []
    batch: list[tuple[str, str, dict[str, str]]] = []
    batch_chars = 0
    for source in pending:
        protected, replacements = protect_text(source, names)
        if "\\n" in protected or "\n" in protected:
            if batch:
                batches.append(batch)
                batch, batch_chars = [], 0
            batches.append([(source, protected, replacements)])
            continue
        if batch and (len(batch) >= 20 or batch_chars + len(protected) > 1400):
            batches.append(batch)
            batch, batch_chars = [], 0
        batch.append((source, protected, replacements))
        batch_chars += len(protected) + 1
    if batch:
        batches.append(batch)

    for index, items in enumerate(batches, 1):
        results.update(translate_batch(items))
        if index % 10 == 0 or index == len(batches):
            usable_cache = {source: results[source] for source in unique_sources if source in results}
            save_json(cache_path, usable_cache)
            print(f"PROGRESS|{index}|{len(batches)}|{len(usable_cache)}", flush=True)
        time.sleep(0.12)

    proposals: dict[str, str] = {}
    generated_sources = set(cache) | set(MANUAL)
    for key, source in sources.items():
        if (
            key.startswith(("content.6.", "content.8."))
            and source in generated_sources
            and key not in PROTECTED_KEYS
            and source.strip() not in official_names
            and not INTERNAL_RE.search(source.strip())
        ):
            generated = MANUAL.get(source, project.get(key, results.get(source, ""))).strip()
            if generated and format_tokens(source) == format_tokens(generated):
                proposals[key] = generated
    rejected = 0
    for key, source in targets.items():
        target = results.get(source, "").strip()
        if not target or format_tokens(source) != format_tokens(target):
            rejected += 1
            continue
        proposals[key] = target

    # Human-reviewed context overrides also repair an earlier generated value
    # when the script is rerun without deleting the complete proposal set.
    for key, source in sources.items():
        if key.startswith(("content.6.", "content.8.")) and source in MANUAL:
            proposals[key] = MANUAL[source]

    proposal_path = report_dir / "Wakfu_Buff_Durum_Ceviri_Onerileri_v44.json"
    save_json(proposal_path, proposals)
    if args.apply:
        for key, target in proposals.items():
            project[key] = target
            manual[key] = target
        save_json(project_path, project)
        save_json(manual_path, manual)

    print(json.dumps({
        "proposals": len(proposals), "rejected": rejected,
        "applied": bool(args.apply), "proposal_file": str(proposal_path),
    }, ensure_ascii=False), flush=True)
    return 0 if rejected == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())

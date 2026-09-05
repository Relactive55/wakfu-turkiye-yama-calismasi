#!/usr/bin/env python3
"""Independent, conservative quality audit for the WAKFU Turkish corpus.

This deliberately does not import ``wakfu_audit.py``.  Its purpose is to
cross-check the generated status report with a second implementation and to
surface review candidates without modifying any translation.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path


PROTECTED_STATUSES = {"KORUNAN_AD", "TEKNIK_KORUNAN"}
TRANSLATED_STATUS = "CEVRILDI"

FORMAT_RE = re.compile(
    r"\\[ntr]|<(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>|%[A-Za-z_][A-Za-z0-9_.-]*%|"
    r"\{\[[^\]]+\]\?|"
    r"\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]"
)
WORD_RE = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*", re.UNICODE)
MOJIBAKE_RE = re.compile(r"Ã|Ä|Å|â€|ðŸ|ï¿½|\uFFFD")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
UNEXPECTED_SCRIPT_RE = re.compile(r"[\u0400-\u052f\u2e80-\u9fff\uac00-\ud7af]")
MODEL_ARTIFACT_RE = re.compile(r"ZXQ[A-Z0-9]*XZ|__WAKFU_|(?:p>){4,}|[əƏ]")

ENGLISH_FUNCTION_WORDS = {
    # Ambiguous Turkish words/abbreviations (a, an, at, as, can, her, in, it,
    # on, no...) are intentionally absent.
    "and", "are", "been", "being", "but", "by", "cannot", "could",
    "did", "does", "for", "from", "had", "has", "have", "here",
    "hers", "him", "how", "if", "into", "is", "its", "may", "must",
    "or", "our", "ours", "she", "should", "that",
    "the", "their", "theirs", "them", "there", "these", "they", "this",
    "those", "to", "was", "we", "were", "what", "when", "where", "which",
    "who", "why", "will", "with", "would", "you", "your", "yours",
}

ENGLISH_ACTION_WORDS = {
    "accept", "activate", "add", "attack", "buy", "cancel", "choose", "click",
    "close", "collect", "complete", "confirm", "continue", "craft", "defeat",
    "delete", "destroy", "disable", "drop", "enable", "equip", "find", "finish",
    "gain", "give", "go", "harvest", "heal", "join", "kill", "leave", "move",
    "open", "place", "press", "purchase", "receive", "remove", "repair", "return",
    "save", "search", "select", "sell", "speak", "start", "stop", "take", "talk",
    "trade", "travel", "unlock", "use", "wait", "win",
}

COPIED_GENERIC_ENGLISH = ENGLISH_FUNCTION_WORDS | ENGLISH_ACTION_WORDS | {
    "achievement", "achievements", "active", "air", "allies", "ally", "armor",
    "back", "battle", "caster", "challenge", "character", "click",
    "close", "current", "damage", "description", "earth", "effect", "effects",
    "equipment", "fight", "fire", "healing", "health", "immune", "invulnerable",
    "item", "items", "level", "levels", "mastery", "note", "objective", "open",
    "place", "quest", "quests", "range", "recipe", "resistance", "reward",
    "round", "search", "select", "spell", "spells", "state", "support", "target",
    "travel", "turn", "turns", "water",
}

# Common tokens that are valid unchanged in Turkish UI/mechanics.  This list is
# intentionally small: uncertain cases are reported as review, never auto-fixed.
ACCEPTED_UNCHANGED = {
    "ap", "fps", "gpu", "hp", "html", "id", "ip", "mp", "npc", "ping", "pvp",
    "stasis", "wakfu", "zaap",
}

# Bu satırlardaki ortak İngilizce sözcükler cümle kalıntısı değil, oyun içi
# özel karakter/mekanik adıdır. Yalnız bağımsız denetimin yanlış pozitiflerini
# bastırmak için anahtar bazında tutulur.
REVIEWED_RESIDUE_KEYS = {
    "companionBackgroundText.3575",  # Drop, beş Dark Knight'tan birinin adı
    "companionBackgroundText.3577",
    "companionBackgroundText.3578",
    "content.33.242751",             # Go, koşulda anılan mekanik ad
}

# Sayısal değer gerçekten korunmuştur ancak iki metin farklı bir ölçü/yazım
# sistemi kullanır. Ters yazılmış kaynak sayfası ve feet->metre dönüşümü genel
# sayı karşılaştırmasıyla güvenilir biçimde değerlendirilemez.
REVIEWED_NUMBER_KEYS = {
    "content.67.661",
    "content.92.203",
}

# Display/title families can legitimately localize a phrase that happens to
# share its English spelling with an unrelated item. They are not prose-level
# references to that item or skill.
PROTECTED_REFERENCE_EXCLUDED_PREFIXES = (
    "content.26.", "content.34.", "content.35.", "content.54.",
    "content.59.", "content.61.", "content.62.", "content.66.",
    "content.77.", "content.78.", "content.80.", "content.82.",
    "content.85.", "content.89.", "content.106.", "content.107.",
    "content.121.", "content.124.", "content.132.", "content.135.",
    "content.137.", "content.138.", "content.155.", "overhead.",
    "desc.mru.",
)

# A content.3/content.15 title can share its spelling with an unrelated
# achievement, NPC, monster, dungeon, action, or workstation.  Keep these
# exclusions key-scoped so a genuine item/spell mention elsewhere is still
# caught by the independent audit.
PROTECTED_REFERENCE_EXCLUDED_KEYS = {
    "content.64.11007",                         # achievement: It's All In The Wrist
    "content.64.4242", "content.64.4243", "content.64.4244", "content.64.4245",
    "content.64.5601", "content.64.5621", "content.64.5630",  # ordinary action
    "content.63.1721", "content.63.1726", "content.64.11516", "content.75.2476",
    "content.75.2866", "quest.sadida.05.13",   # nation guards, not insignia items
    "content.67.517",                           # Captain Amakna character
    "content.4.4824",                           # Cloud Knight companion
    "content.64.10830", "content.64.11392", "content.64.2919",
    "content.64.5817", "content.64.8688",      # Culinary Grand Master Zomkin boss
    "content.64.2082",                          # achievement: Ice Fury II
    "osamosa.stasis.41.tundrazor",              # monster names
    "LIFE_STOLEN_BONUS",                        # localized buff/mechanic label
    "content.75.2276",                          # Huge Cawwot landmark
    "content.63.5272", "content.64.10586", "content.64.10587",
    "content.64.10588", "content.64.10589", "content.64.10592",
    "content.64.10593", "content.64.10594", "content.64.369",
    "content.64.4663", "content.64.6522", "content.64.6658",
    "content.64.7102", "content.64.7103", "content.64.7104",
    "content.64.8561", "content.64.8639", "protector.specialevent.17",
    "quest.amakna.missmoches.03.30",            # Miss Ugly Tower dungeon/location
    "moon.collector.croco.start",                # Otomai's Disciples organization
    "content.64.7921", "content.64.7924", "content.64.7927", "content.64.7930",
    "content.75.3759",                          # 'The One Eye', not The One item
    "content.64.10832", "content.64.5831", "content.64.6713",
    "content.64.8276", "content.64.8697", "content.76.7650",  # Vertox boss
    "content.86.121", "content.86.122", "content.86.123", "content.86.124",
    "craft.table.forestry",                     # reconstruction/workstation labels
}

# These strings are also ordinary characteristic/mechanic labels. Their
# appearance in prose does not by itself refer to the same-named title row.
GENERIC_PROTECTED_REFERENCE_NAMES = {
    "Ancient Weapons Forge", "Fighter Gemlin", "Gone with the wind",
    "Ogrest's Cult", "Royal Grawfish", "Sadida Guard",
    "Three Pistes' Cave",
    "Air Damage", "Area Mastery", "Critical Hit", "Critical Mastery",
    "Distance Mastery", "Earth Damage", "Elemental Mastery", "Fire Damage",
    "Healing Mastery", "Melee Mastery", "Rear Mastery",
    "Single-Target Mastery", "The Dial", "The Ecosystem", "The Portal",
    "Water Damage",
}

BROKEN_TURKISH_PATTERNS = (
    (re.compile(r"(?iu)\b(?:bir|bu|şu|o)\s+(?:bir)\b"), "yinelenen belirteç"),
    (re.compile(r"(?iu)\b[A-Za-zÇĞİÖŞÜçğıöşü]+(?:y?[ıiuü])\s+sahip\b"), "hatalı hâl eki"),
    (re.compile(r"(?iu)\b(?:yapmak|etmek|olmak)\s+için\s+(?:için)\b"), "yinelenen 'için'"),
    (re.compile(r"(?iu)\b(ve|veya|ile)\s+\1\b"), "yinelenen bağlaç"),
    (re.compile(r"(?iu)\b(?:the|your|you|this|that|these|those|with|from|into)\b"), "İngilizce işlev sözcüğü"),
)


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    key: str
    category: str
    source: str
    target: str
    detail: str


def visible_text(value: str) -> str:
    return FORMAT_RE.sub(" ", value)


def words(value: str) -> list[str]:
    return [match.group(0).casefold() for match in WORD_RE.finditer(visible_text(value))]


def strip_protected_names(value: str, protected_names: set[str]) -> str:
    """Blank exact 1-8 word protected names, including Turkish suffixes."""
    matches = list(WORD_RE.finditer(value))
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(matches):
        found = None
        for end_index in range(min(len(matches) - 1, index + 7), index - 1, -1):
            start, end = matches[index].start(), matches[end_index].end()
            candidate = re.sub(r"\s+", " ", value[start:end].strip().rstrip(".,;:!?"))
            folded = candidate.casefold()
            unsuffixed = re.sub(r"['’][a-zçğıöşü]{1,7}$", "", folded)
            if folded in protected_names or unsuffixed in protected_names:
                found = (start, end)
                index = end_index + 1
                break
        if found:
            spans.append(found)
        else:
            index += 1
    chars = list(value)
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def protected_mentions(value: str, protected_names: set[str]) -> set[str]:
    """Return multi-word protected names visibly mentioned in a source."""
    matches = list(WORD_RE.finditer(visible_text(value)))
    result: set[str] = set()
    index = 0
    while index < len(matches):
        found = None
        for end_index in range(min(len(matches) - 1, index + 7), index, -1):
            start, end = matches[index].start(), matches[end_index].end()
            candidate = re.sub(r"\s+", " ", value[start:end].strip().rstrip(".,;:!?"))
            if candidate.casefold() in protected_names:
                found = candidate
                index = end_index + 1
                break
        if found:
            result.add(found)
        else:
            index += 1
    return result


def format_signature(value: str) -> tuple[str, ...]:
    return tuple(FORMAT_RE.findall(value))


def numeric_signature(value: str) -> tuple[str, ...]:
    cleaned = visible_text(value)
    time_tokens: list[str] = []

    def replace_colon_time(match: re.Match[str]) -> str:
        hour, minute = int(match.group(1)), int(match.group(2))
        time_tokens.append(f"time:{hour:02d}:{minute:02d}")
        return " "

    def replace_turkish_time(match: re.Match[str]) -> str:
        hour, minute = int(match.group(2)), int(match.group(3))
        time_tokens.append(f"time:{hour:02d}:{minute:02d}")
        return match.group(1)

    # 8:00 a.m. ile Türkçedeki "saat 08.00" aynı saattir. Ondalık
    # değerleri saat sanmamak için noktalı biçimi yalnız "saat"ten sonra al.
    cleaned = re.sub(r"(?<!\d)(\d{1,2}):([0-5]\d)(?!\d)", replace_colon_time, cleaned)
    cleaned = re.sub(
        r"(?iu)(\bsaat\s+)(\d{1,2})\.([0-5]\d)(?!\d)",
        replace_turkish_time,
        cleaned,
    )

    # Türkçe kısaltılmış binlik yazımı: 10 bin == 10,000.
    def expand_thousand(match: re.Match[str]) -> str:
        raw = match.group(1).replace(",", ".")
        value = float(raw) * 1000
        return f" {int(value) if value.is_integer() else value} "

    cleaned = re.sub(r"(?iu)(?<![\w])([0-9]+(?:[.,][0-9]+)?)\s+bin\b", expand_thousand, cleaned)
    # Kaynakta 1x, Türkçede x1 görülebilir; yön sıralamayı değiştirmez.
    cleaned = re.sub(r"(?i)(?<!\w)x(?=\d)", "", cleaned)
    # Keep signed integers/decimals and percentages. Thousands separators are
    # normalized so 1,000 and 1.000 do not become a false mismatch. A leading
    # percent sign is valid Turkish typography ("%50") even when it directly
    # follows a word, so it must not inherit the word-boundary restriction
    # used for ordinary numbers.
    result = list(time_tokens)
    pattern = (
        r"(?:[+-]?%\s*\d+(?:[.,]\d+)*|"
        r"(?<![\w%])[+-]?\d+(?:[.,]\d+)*(?:\s*%)?)"
    )
    for raw in re.findall(pattern, cleaned):
        token = re.sub(r"\s+", "", raw)
        prefix_percent = re.fullmatch(r"([+-]?)%(\d+(?:[.,]\d+)*)", token)
        if prefix_percent:
            token = prefix_percent.group(1) + prefix_percent.group(2) + "%"
        # Percentages such as 74.999% are decimals in the source corpus, not
        # thousands-grouped integers.
        if "%" not in token and re.fullmatch(r"[+-]?\d{1,3}(?:[.,]\d{3})+", token):
            token = re.sub(r"[.,]", "", token)
        else:
            token = token.replace(",", ".")
        # Artı işareti pozitif değerin isteğe bağlı gösterimidir; eksi işareti
        # ise semantik olduğundan korunur.
        token = token.removeprefix("+")
        suffix = "%" if token.endswith("%") else ""
        number = token[:-1] if suffix else token
        sign = "-" if number.startswith("-") else ""
        unsigned = number.removeprefix("-")
        if re.fullmatch(r"\d+(?:\.\d+)?", unsigned):
            if "." in unsigned:
                integer, fraction = unsigned.split(".", 1)
                unsigned = f"{int(integer)}.{fraction}"
            else:
                unsigned = str(int(unsigned))
            token = sign + unsigned + suffix
        result.append(token)
    return tuple(sorted(result))


ENGLISH_NUMBER_WORDS = {
    "1": r"\b(?:one|first|single|(?:a|an)\s+(?:level|turn|MP|AP|WP))\b",
    "2": r"\b(?:two|second)\b",
    "3": r"\b(?:three|third)\b", "4": r"\b(?:four|fourth)\b",
    "5": r"\b(?:five|fifth)\b", "6": r"\b(?:six|sixth)\b",
    "7": r"\b(?:seven|seventh)\b", "8": r"\b(?:eight|eighth)\b",
    "9": r"\b(?:nine|ninth)\b", "10": r"\b(?:ten|tenth)\b",
    "11": r"\beleven\b", "12": r"\b(?:twelve|twelvians?)\b",
    "20": r"\btwenty\b", "24": r"\btwenty[- ]four\b", "25": r"\btwenty[- ]five\b",
    "30": r"\bthirty\b", "40": r"\bforty\b", "42": r"\bforty[- ]two\b",
    "50": r"\bfifty\b", "60": r"\bsixty\b", "70": r"\bseventy\b",
    "100": r"\b(?:one )?hundred\b", "120": r"\bone hundred(?: and)? twenty\b",
    "200": r"\btwo hundred\b", "300": r"\bthree hundred\b",
    "500": r"\bfive hundred\b", "1000": r"\b(?:one )?thousand\b",
    "12.5": r"\btwelve and a half\b",
}
TURKISH_NUMBER_WORDS = {
    "1": r"\b(?:bir(?:dir)?|ilk|birinci|tek)\b", "2": r"\b(?:iki|ikinci)\b",
    "3": r"\b(?:üç|üçüncü)\b", "4": r"\b(?:dört|dördüncü)\b",
    "5": r"\b(?:beş|beşinci)\b", "6": r"\b(?:altı|altıncı)\b",
    "7": r"\b(?:yedi|yedinci)\b", "8": r"\b(?:sekiz|sekizinci)\b",
    "9": r"\b(?:dokuz|dokuzuncu)\b", "10": r"\b(?:on|onuncu)\b",
    "11": r"\bon bir(?:ler)?\b", "12": r"\bon iki(?:ler)?\b",
    "20": r"\byirmi\b", "25": r"\byirmi beş\b", "30": r"\botuz\b",
    "40": r"\bkırk\b", "42": r"\bkırk iki\b", "50": r"\belli\b",
    "60": r"\baltmış\b", "70": r"\byetmiş\b",
    "100": r"\b(?:yüz|yüzde bir(?:dir)?)\b", "120": r"\byüz yirmi\b",
    "200": r"\biki yüz\b", "300": r"\büç yüz\b", "500": r"\bbeş yüz\b",
    "1000": r"\bbin\b", "3000": r"\büç bin\b", "10000": r"\bon bin\b",
    "50000": r"\belli bin\b", "100000": r"\byüz bin\b",
}


def numeric_words_explain_difference(
    source: str, target: str, source_numbers: tuple[str, ...], target_numbers: tuple[str, ...]
) -> bool:
    """Accept digit/word spelling changes while retaining real value checks."""
    missing = collections.Counter(source_numbers) - collections.Counter(target_numbers)
    extra = collections.Counter(target_numbers) - collections.Counter(source_numbers)
    visible_source = visible_text(source)
    visible_target = visible_text(target)

    # Türkçe, işaret yerine çoğu zaman "azalır/kaybı/kaldırır" gibi bir
    # fiille negatifliği açıklar. Aynı mutlak değer varsa bu semantik biçimi
    # eşdeğer say; işareti sessizce düşüren nötr metinler yine uyarı üretir.
    negative_cue = re.search(
        r"(?iu)\b(?:azal\w*|kayb\w*|kaybet\w*|düş\w*|kaldır\w*|indir\w*|eksi|negatif)\b",
        visible_target,
    )
    if negative_cue:
        for token in list(missing):
            if not token.startswith("-"):
                continue
            unsigned = token[1:]
            covered = min(missing[token], extra.get(unsigned, 0))
            if covered:
                missing[token] -= covered
                extra[unsigned] -= covered
                if missing[token] <= 0:
                    del missing[token]
                if extra[unsigned] <= 0:
                    del extra[unsigned]

    # İngilizcede "per % / each %" oranı %1 başına demektir; Türkçede bu 1
    # çoğu kez açıkça yazılır.
    if re.search(r"(?iu)\b(?:per|each|for each)\s+%", visible_source):
        for token in ("1%", "1"):
            if extra.get(token):
                extra[token] -= 1
                if extra[token] <= 0:
                    del extra[token]
                break

    # Aynı cümlede yüzde bağlamı varken kaynak bazen ikinci değerde % işaretini
    # yinelemez ("10% instead of 20" veya "% HP <= 20").
    if "%" in visible_source and "%" in visible_target:
        for token in list(missing):
            if token.startswith(("+", "-")) or token.endswith("%"):
                continue
            percent = token + "%"
            covered = min(missing[token], extra.get(percent, 0))
            if covered:
                missing[token] -= covered
                extra[percent] -= covered
                if missing[token] <= 0:
                    del missing[token]
                if extra[percent] <= 0:
                    del extra[percent]

    for token in list(missing):
        if token.startswith(("+", "-")) or token.endswith("%"):
            continue
        pattern = TURKISH_NUMBER_WORDS.get(token)
        if not pattern:
            continue
        covered = len(re.findall(pattern, visible_target, flags=re.IGNORECASE))
        if covered:
            missing[token] -= min(missing[token], covered)
            if missing[token] <= 0:
                del missing[token]

    for token in list(extra):
        if token.startswith(("+", "-")) or token.endswith("%"):
            continue
        pattern = ENGLISH_NUMBER_WORDS.get(token)
        if not pattern:
            continue
        covered = len(re.findall(pattern, visible_source, flags=re.IGNORECASE))
        if covered:
            extra[token] -= min(extra[token], covered)
            if extra[token] <= 0:
                del extra[token]
    return not missing and not extra


def load_status(path: Path) -> list[dict[str, str]]:
    # The primary audit writes escaped tabs/newlines but deliberately does not
    # CSV-quote literal quotation marks.  Splitting exact physical lines is
    # therefore the correct inverse; csv.DictReader would mistake dialogue
    # quotes for field delimiters and merge unrelated records.
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        header = handle.readline().rstrip("\r\n").split("\t")
        rows = []
        for line_number, line in enumerate(handle, 2):
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) != len(header):
                raise ValueError(
                    f"Geçersiz durum raporu satırı {line_number}: "
                    f"{len(fields)} alan, beklenen {len(header)}"
                )
            row = dict(zip(header, fields))
            for field_name in ("Ingilizce", "Turkce", "Neden"):
                row[field_name] = unescape_status_field(row.get(field_name, ""))
            rows.append(row)
        return rows


def unescape_status_field(value: str) -> str:
    """Reverse wakfu_audit.tsv without conflating ``\\n`` and newlines."""
    result: list[str] = []
    index = 0
    while index < len(value):
        if value[index] != "\\" or index + 1 >= len(value):
            result.append(value[index])
            index += 1
            continue
        marker = value[index + 1]
        if marker == "\\":
            result.append("\\")
        elif marker == "t":
            result.append("\t")
        elif marker == "r":
            result.append("\r")
        elif marker == "n":
            result.append("\n")
        else:
            result.extend(("\\", marker))
        index += 2
    return "".join(result)


def load_json_object(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON kökü nesne değil: {path}")
    return value


def read_source_keys(jar_path: Path) -> set[str]:
    with zipfile.ZipFile(jar_path, "r") as archive:
        name = "texts_en.properties"
        if name not in archive.namelist():
            name = "texts_en_cleaned.properties"
        with archive.open(name) as raw:
            keys = set()
            for binary_line in raw:
                line = binary_line.decode("utf-8-sig").rstrip("\r\n")
                if line and not line.startswith(("#", "!")) and "=" in line:
                    keys.add(line.split("=", 1)[0])
            return keys


def analyze_row(
    row: dict[str, str],
    protected_names: set[str],
    protected_reference_names: set[str],
    protected_reference_names_exact: set[str],
) -> list[Finding]:
    key = row.get("Anahtar", "")
    category = row.get("Kategori", "")
    status = row.get("Durum", "")
    source = row.get("Ingilizce", "")
    target = row.get("Turkce", "")
    findings: list[Finding] = []

    def add(severity: str, code: str, detail: str) -> None:
        findings.append(Finding(severity, code, key, category, source, target, detail))

    # The primary pipeline records an empty target for protected/technical
    # rows because the JAR builder deliberately falls back to the English
    # source.  This is not a missing translation.
    if not target.strip() and status not in PROTECTED_STATUSES:
        add("critical", "EMPTY_TARGET", "Hedef metin boş")
        return findings
    if not target.strip():
        return findings

    if status == "KORUNAN_AD" and target != source:
        add("critical", "PROTECTED_NAME_CHANGED", "Korunan özgün ad değiştirilmiş")

    if format_signature(source) != format_signature(target):
        add("critical", "FORMAT_MISMATCH", "Yer tutucu/etiket dizisi kaynakla aynı değil")

    if CONTROL_RE.search(target):
        add("critical", "CONTROL_CHARACTER", "Görünmez denetim karakteri bulundu")
    if MOJIBAKE_RE.search(target):
        add("critical", "MOJIBAKE", "Bozuk kodlama karakter dizisi bulundu")
    if MODEL_ARTIFACT_RE.search(target):
        add("critical", "MODEL_ARTIFACT", "Model artığı/bozuk koruma belirteci bulundu")
    unexpected = UNEXPECTED_SCRIPT_RE.search(target)
    if unexpected and unexpected.group(0) not in source:
        add("critical", "UNEXPECTED_SCRIPT", f"Kaynakta olmayan yazı sistemi karakteri: {unexpected.group(0)}")

    if status not in PROTECTED_STATUSES:
        source_words = words(source)
        target_without_names = strip_protected_names(visible_text(target), protected_names)
        target_words = words(target_without_names)
        source_english = [word for word in source_words if word in COPIED_GENERIC_ENGLISH]
        source_english_set = set(source_english)
        target_english = [
            word for word in target_words
            if word in COPIED_GENERIC_ENGLISH and word in source_english_set
        ]

        if source.strip() == target.strip() and len(source_words) >= 2 and source_english:
            add("critical", "UNTRANSLATED_COPY", "Çevrilebilir cümle kaynak İngilizceyle aynı")
        elif target_english and key not in REVIEWED_RESIDUE_KEYS:
            # A single "the" is common inside an official proper name. Other
            # function/action words are high-confidence residue candidates.
            non_title_hits = [word for word in target_english if word != "the"]
            if non_title_hits or target_english.count("the") >= 2:
                add("high", "ENGLISH_RESIDUE", "İngilizce kalıntı: " + ", ".join(sorted(set(target_english))))

        changed_names = []
        if (
            key not in PROTECTED_REFERENCE_EXCLUDED_KEYS
            and not key.startswith(PROTECTED_REFERENCE_EXCLUDED_PREFIXES)
        ):
            changed_names = [
                name for name in protected_mentions(source, protected_reference_names)
                if name in protected_reference_names_exact
                and name not in GENERIC_PROTECTED_REFERENCE_NAMES
                and source.strip().rstrip(".,;:!?") != name
                and name.casefold() not in visible_text(target).casefold()
            ]
        if changed_names:
            quoted = any(re.search(
                r"[\"“”']" + re.escape(name) + r"[\"“”']",
                source,
            ) for name in changed_names)
            add(
                "high" if quoted else "review", "PROTECTED_REFERENCE_CHANGED",
                "Metin içindeki özgün ad değiştirilmiş/yarım çevrilmiş: " + ", ".join(sorted(changed_names)[:4]),
            )

        if "{[" not in target:
            for pattern, description in BROKEN_TURKISH_PATTERNS[1:-1]:
                match = pattern.search(target)
                if match:
                    add("high", "TURKISH_GRAMMAR", f"{description}: {match.group(0)}")
                    break

        src_numbers = numeric_signature(source)
        dst_numbers = numeric_signature(target)
        if (
            key not in REVIEWED_NUMBER_KEYS
            and src_numbers != dst_numbers
            and not numeric_words_explain_difference(
            source, target, src_numbers, dst_numbers
            )
        ):
            add("review", "NUMBER_MISMATCH", f"Sayılar farklı: {src_numbers!r} -> {dst_numbers!r}")

    if re.search(r"(?<!\\) {2,}", target) and not re.search(r"(?<!\\) {2,}", source):
        add("review", "EXTRA_SPACES", "Kaynakta olmayan ardışık boşluk bulundu")
    if re.search(r"\s+[,.!?;:]", target) and not re.search(r"\s+[,.!?;:]", source):
        add("review", "SPACE_BEFORE_PUNCTUATION", "Noktalama öncesinde fazladan boşluk var")
    # Three dots are a standard ellipsis and may legitimately be introduced
    # by Turkish sentence rhythm. Four or more repeated marks are the actual
    # corruption signal here.
    if re.search(r"([!?.,;:])\1{3,}", target) and not re.search(r"([!?.,;:])\1{3,}", source):
        add("review", "REPEATED_PUNCTUATION", "Kaynakta olmayan aşırı noktalama tekrarı var")
    return findings


def add_consistency_findings(rows: list[dict[str, str]], findings: list[Finding]) -> None:
    groups: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
    for row in rows:
        if row.get("Durum") not in PROTECTED_STATUSES and row.get("Ingilizce", "").strip():
            groups[row["Ingilizce"].strip()].append(row)

    for source, members in groups.items():
        if len(members) < 2:
            continue
        targets: dict[str, list[dict[str, str]]] = collections.defaultdict(list)
        for member in members:
            targets[member.get("Turkce", "").strip()].append(member)
        nonempty_targets = {target: items for target, items in targets.items() if target}
        if len(nonempty_targets) <= 1:
            continue
        # The same short source can have different meanings in different UI
        # contexts (for example Play/Oyna versus Play/Oynat). Report every
        # variant for editorial review without treating context as an error.
        severity = "review"
        variants = " | ".join(
            f"{target!r} ({len(items)})" for target, items in sorted(nonempty_targets.items())
        )
        first = members[0]
        findings.append(Finding(
            severity, "INCONSISTENT_EXACT_SOURCE", first.get("Anahtar", ""),
            first.get("Kategori", ""), source, first.get("Turkce", ""),
            f"Aynı kaynak için {len(nonempty_targets)} karşılık: {variants}",
        ))


def write_outputs(output_dir: Path, rows: list[dict[str, str]], findings: list[Finding], metadata: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    findings.sort(key=lambda item: (
        {"critical": 0, "high": 1, "review": 2}.get(item.severity, 9),
        item.code, item.key,
    ))
    counts = collections.Counter(item.severity for item in findings)
    codes = collections.Counter(item.code for item in findings)
    payload = {
        "metadata": metadata,
        "summary": {"rows": len(rows), "findings": len(findings), "by_severity": dict(counts), "by_code": dict(codes)},
        "findings": [asdict(item) for item in findings],
    }
    json_path = output_dir / "Wakfu_Derin_Denetim.json"
    tsv_path = output_dir / "Wakfu_Derin_Denetim.tsv"
    summary_path = output_dir / "Wakfu_Derin_Denetim_Ozet.txt"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with tsv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(("Onem", "Kod", "Anahtar", "Kategori", "Ingilizce", "Turkce", "Aciklama"))
        for item in findings:
            writer.writerow((item.severity, item.code, item.key, item.category, item.source, item.target, item.detail))
    lines = [
        "WAKFU BAĞIMSIZ DERİN DENETİM",
        f"Toplam satır: {len(rows)}",
        f"Toplam bulgu: {len(findings)}",
        f"Kritik: {counts['critical']}",
        f"Yüksek: {counts['high']}",
        f"İnceleme: {counts['review']}",
        "",
        "Bulgu türleri:",
    ]
    lines.extend(f"{code}: {count}" for code, count in sorted(codes.items()))
    lines.extend(("", f"Ayrıntı: {tsv_path}", f"Makine raporu: {json_path}"))
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True, type=Path)
    args = parser.parse_args()
    root = args.project_root.resolve()
    status_path = root / "Raporlar" / "Wakfu_Ceviri_Durum.tsv"
    source_jar = root / "Oyun_Kaynaklari" / "Guncel" / "i18n_en.jar"
    translation_path = root / "Ceviri_Verileri" / "wakfu_tr_ceviri.json"
    manual_path = root / "Ceviri_Verileri" / "manual_repairs_v23.json"
    terminology_path = root / "Ceviri_Verileri" / "terim_duzeltmeleri.json"

    rows = load_status(status_path)
    terminology = load_json_object(terminology_path)
    findings: list[Finding] = []
    protected_names = {
        row.get("Ingilizce", "").strip().casefold()
        for row in rows
        if row.get("Durum") == "KORUNAN_AD" and row.get("Ingilizce", "").strip()
    }
    terminology_sources = {
        str(value).strip().casefold()
        for section in ("values", "phrases")
        for value in terminology.get(section, {})
        if str(value).strip()
    }
    protected_reference_names_exact = {
        row.get("Ingilizce", "").strip()
        for row in rows
        if row.get("Durum") == "KORUNAN_AD"
        and row.get("Kategori") in {"YETENEK_ADI", "ESYA_KAYNAK_ADI"}
        and len(words(row.get("Ingilizce", ""))) >= 2
        and row.get("Ingilizce", "").strip().casefold() not in terminology_sources
    }
    protected_reference_names = {
        name.casefold() for name in protected_reference_names_exact
    }
    for row in rows:
        findings.extend(analyze_row(
            row, protected_names, protected_reference_names,
            protected_reference_names_exact,
        ))
    add_consistency_findings(rows, findings)

    source_keys = read_source_keys(source_jar)
    translations = load_json_object(translation_path)
    manual = load_json_object(manual_path)
    report_keys = {row.get("Anahtar", "") for row in rows}
    metadata: dict[str, object] = {
        "source_keys": len(source_keys),
        "report_keys": len(report_keys),
        "translation_keys": len(translations),
        "manual_repair_keys": len(manual),
        "source_missing_from_report": sorted(source_keys - report_keys),
        "report_missing_from_source": sorted(report_keys - source_keys),
        "translation_orphans": sorted(set(translations) - source_keys),
        "manual_repair_orphans": sorted(set(manual) - source_keys),
        "terminology_sections": sorted(terminology),
    }
    for key in metadata["source_missing_from_report"]:
        findings.append(Finding("critical", "SOURCE_NOT_REPORTED", str(key), "", "", "", "Kaynak anahtarı raporda yok"))
    for key in metadata["report_missing_from_source"]:
        findings.append(Finding("critical", "REPORT_KEY_NOT_IN_SOURCE", str(key), "", "", "", "Rapor anahtarı güncel kaynakta yok"))
    for key in metadata["translation_orphans"]:
        findings.append(Finding("review", "ORPHAN_TRANSLATION", str(key), "", "", str(translations[key]), "Çeviri anahtarı güncel kaynakta yok"))
    for key in metadata["manual_repair_orphans"]:
        findings.append(Finding("review", "ORPHAN_MANUAL_REPAIR", str(key), "", "", str(manual[key]), "Elle düzeltme anahtarı güncel kaynakta yok"))

    write_outputs(root / "Raporlar", rows, findings, metadata)
    print(json.dumps({
        "rows": len(rows),
        "findings": len(findings),
        "critical": sum(item.severity == "critical" for item in findings),
        "high": sum(item.severity == "high" for item in findings),
        "review": sum(item.severity == "review" for item in findings),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

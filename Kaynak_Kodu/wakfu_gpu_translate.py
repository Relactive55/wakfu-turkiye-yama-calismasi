import argparse
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# WAKFU's property language contains placeholders, conditional blocks, escaped
# line endings and markup. Structural tokens never go through the language model.
TOKEN_RE = re.compile(
    r"(\{\[[^\]]+\]\?(?:s|es)?:\}|\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]"
    r"|<(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>|%[A-Za-z_][A-Za-z0-9_.-]*%|\\[ntr])"
)
ZXQ_PLACEHOLDER_RE = re.compile(r"(?:ZXQ|XQ)\d{4}QXZ")
WORD_RE = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*", re.UNICODE)
ENGLISH_LEFTOVER_RE = re.compile(
    r"(?i)\b(the|and|you|your|with|from|into|must|cannot|available|unavailable|"
    r"a|an|of|to|for|on|at|as|it|its|be|been|being|by|this|that|these|those|"
    r"which|who|whom|what|when|where|why|how|not|can|could|would|should|may|"
    r"all|any|each|every|some|more|less|than|then|only|also|just|now|new|"
    r"make|makes|made|reduce|reduced|received|given|use|used|using|"
    r"default|damage|mastery|characteristics|recommended|rarity|pockets|page|"
    r"click|level|choose|select|inventory|market|reward|quest|search|current|"
    r"challenge|item|items|build|resistance|earth|water|fire|air|exact|ones|"
    r"following|remove|purchase|sale|window|offer|remaining|team|are|is|was|were|has|have|"
    r"hidden|color|spell|spells|active|open|chest|ranking|rank|close|cancel|confirm|"
    r"yes|no|name|description|price|quantity|equipment|achievement|achievements|"
    r"fight|turn|round|target|range|cost|health|armor|critical|penalty|locked|"
    r"unlocked|copy|paste|delete|edit|save|load|next|previous|back)\b"
)
SUSPICIOUS_TURKISH_RE = re.compile(
    r"(?iu)\b(?:kullanıcı adınız|yeterince iyileştim|satın alma fırsatı|"
    r"sıfırsa sahip|zerosa sahip|görüşüm açıldı|pencerem ekleyemezsiniz|"
    r"pencerem kayıt|kilitedeki|onaylıyormusunuz|dağıttiniz|güvenlikler|"
    r"emin misiniz ki|pazar yeri['’]de|savaş alanı katıl|satırsınız|yapı et)\b"
)

DIALECT_WORDS = {
    "gualds": "guards", "guawds": "guards", "heald": "heard",
    "letuned": "returned", "letun": "return", "impwove": "improve",
    "youl": "your", "youw": "your", "pwoblem": "problem",
    "fwank": "frank", "twusted": "trusted", "twust": "trust",
    "weally": "really", "second-wate": "second-rate", "kween": "queen",
    "evewy": "every", "stwangew": "stranger", "pwotect": "protect",
    "fwom": "from", "thweats": "threats", "dwive": "drive",
    "wight": "right", "wong": "wrong", "wabbit": "Wabbit",
    "wabbits": "Wabbits", "sandyoptewa": "Sandyoptera",
    # Wabbit speech: English r/l sounds are intentionally written as w. The
    # phonetic joke does not map cleanly to Turkish, so normalize the source
    # before translation and keep actual WAKFU names protected separately.
    "adventuwew": "adventurer", "adventulel": "adventurer",
    "aftew": "after", "awe": "are", "bwave": "brave",
    "bwight": "bright", "bwings": "brings", "cwossed": "crossed",
    "faw": "far", "fow": "for", "fowgive": "forgive",
    "futuwe": "future", "gweat": "great", "hewe": "here",
    "labowatowy": "laboratory", "leadews": "leaders",
    "mewely": "merely", "ovewcame": "overcame", "pwemium": "premium",
    "puwpose": "purpose", "sewve": "serve", "thwone": "throne",
    "undewstand": "understand", "undewstanding": "understanding",
    "unfaiwly": "unfairly", "wawe": "rare", "wevolt": "revolt",
    "wegain": "regain", "wesolved": "resolved", "wewe": "were",
    "whewe": "where", "whoevew": "whoever", "wightful": "rightful",
    "woom": "room", "you'we": "you're", "expwess": "express",
    # Lenald speech: the same idea is written with r/l substitutions.
    "ale": "are", "answels": "answers", "boln": "born",
    "cilcumstances": "circumstances", "cleal": "clear",
    "consideling": "considering", "fathel": "father", "fewel": "fewer",
    "filmly": "firmly", "flom": "from", "fol": "for",
    "folbids": "forbids", "folmal": "formal", "glatitude": "gratitude",
    "gualdian": "guardian", "hindeled": "hindered", "inhelited": "inherited",
    "intelacting": "interacting", "late": "rate", "leally": "really",
    "leselves": "reserves", "lespect": "respect", "lesponsible": "responsible",
    "lole": "role", "nevel": "never", "oul": "our", "outsidels": "outsiders",
    "plinciples": "principles", "ploof": "proof", "stlangel": "stranger",
    "stlangels": "strangers", "stlaight": "straight", "suppolt": "support",
    "theil": "their", "tellitoly": "territory", "tlue": "true",
    "tlust": "trust", "undelstand": "understand", "unfoltunately": "unfortunately",
    "vely": "very", "whele": "where", "yeals": "years",
    "awchitects": "architects", "coulse": "course", "detelmined": "determined",
    "fowbidden": "forbidden", "hele": "here", "honol": "honor",
    "honow": "honor", "joulney": "journey", "leason": "reason",
    "othew": "other", "owdews": "orders", "pewfect": "perfect",
    "plevailed": "prevailed", "suwpwise": "surprise", "stwongew": "stronger",
    "tladitions": "traditions", "tloops": "troops", "victoly": "victory",
}


def emit(message):
    print(message, flush=True)


def start_loading_heartbeat(label):
    """Keep the GUI watchdog alive during long first-time model downloads."""
    stop = threading.Event()

    def pulse():
        while not stop.wait(10):
            emit(f"HEARTBEAT|{label}")

    threading.Thread(target=pulse, name="wakfu-model-heartbeat", daemon=True).start()
    return stop


def normalize_game_english(text):
    def replace(match):
        original = match.group(0)
        fixed = DIALECT_WORDS.get(original.lower(), original)
        if original.isupper():
            return fixed.upper()
        if original[:1].isupper():
            return fixed[:1].upper() + fixed[1:]
        return fixed

    keys = "|".join(re.escape(k) for k in sorted(DIALECT_WORDS, key=len, reverse=True))
    text = re.sub(r"(?i)\b(?:" + keys + r")\b", replace, text)
    return re.sub(r"(?i)\byou'we\b", "you're", text)


def normalized_name(text):
    # Case is intentionally retained. This prevents a generic lower-case word in
    # an explanation (for example "powder") from being mistaken for the item
    # name "Powder", while the actual capitalized WAKFU name remains locked.
    return re.sub(r"\s+", " ", text.strip().rstrip(".,;:!?"))


def turkish_genitive_suffix(name):
    vowels = [ch.casefold() for ch in name if ch.casefold() in "aeıioöuü"]
    vowel = vowels[-1] if vowels else "a"
    if vowel in "ei":
        sound = "i"
    elif vowel in "öü":
        sound = "ü"
    elif vowel in "ou":
        sound = "u"
    else:
        sound = "ı"
    bridge = "n" if name[-1:].casefold() in "aeıioöuü" else ""
    return "'" + bridge + sound + "n"


def find_protected_name_spans(text, protected_names):
    words = list(WORD_RE.finditer(text))
    spans = []
    i = 0
    while i < len(words):
        best = None
        for j in range(min(len(words) - 1, i + 7), i - 1, -1):
            candidate = text[words[i].start():words[j].end()]
            candidate_key = normalized_name(candidate)
            end = words[j].end()
            if candidate_key in protected_names:
                while end < len(text) and text[end] in ".,;!?":
                    end += 1
                best = (words[i].start(), end)
                i = j + 1
                break
            if candidate_key.endswith(("'s", "’s")) and candidate_key[:-2] in protected_names:
                best = (words[i].start(), end - 2)
                i = j + 1
                break
        if best:
            spans.append(best)
        else:
            i += 1
    return spans


def split_structural_tokens(text):
    """Split syntax atoms while keeping conditional branch text translatable."""
    parts = []

    def add(is_token, value):
        if not value:
            return
        if parts and parts[-1][0] == is_token:
            parts[-1] = (is_token, parts[-1][1] + value)
        else:
            parts.append((is_token, value))

    def walk(start, stop):
        plain = start
        index = start
        while index < stop:
            if text.startswith("{[", index):
                condition_end = text.find("]?", index + 2, stop)
                if condition_end >= 0:
                    body_start = condition_end + 2
                    depth = 0
                    separator = None
                    cursor = body_start
                    close = None
                    while cursor < stop:
                        if text.startswith("{[", cursor):
                            depth += 1; cursor += 2; continue
                        if text[cursor] == "}":
                            if depth:
                                depth -= 1; cursor += 1; continue
                            close = cursor; break
                        if (
                            text[cursor] == ":"
                            and depth == 0
                            and (cursor == 0 or text[cursor - 1] != "\\")
                            and separator is None
                        ):
                            separator = cursor
                        cursor += 1
                    if close is not None and separator is not None:
                        add(False, text[plain:index])
                        add(True, text[index:body_start])
                        walk(body_start, separator)
                        add(True, ":")
                        walk(separator + 1, close)
                        add(True, "}")
                        index = close + 1
                        plain = index
                        continue

            end = None
            if text.startswith(("\\n", "\\r", "\\t"), index):
                end = index + 2
            elif text[index] == "<":
                close = text.find(">", index + 1, stop)
                if close >= 0: end = close + 1
            elif text[index] == "%":
                close = text.find("%", index + 1, stop)
                if close > index + 1: end = close + 1
            elif text[index] == "[":
                close = text.find("]", index + 1, stop)
                if close >= 0: end = close + 1
            if end is not None:
                add(False, text[plain:index])
                add(True, text[index:end])
                index = end
                plain = end
            else:
                index += 1
        add(False, text[plain:stop])

    walk(0, len(text))
    return parts


def split_protected(text, protected_names):
    slots = []
    translatable = []
    for is_token, part in split_structural_tokens(text):
        if not part:
            continue
        if is_token:
            slots.append(("token", part))
            continue
        if not part.strip():
            slots.append(("token", part))
            continue

        leading = part[: len(part) - len(part.lstrip())]
        trailing = part[len(part.rstrip()):]
        core = part.strip()
        if leading:
            slots.append(("token", leading))

        spans = find_protected_name_spans(core, protected_names)
        cursor = 0
        for start, end in spans:
            before = core[cursor:start]
            if before:
                if re.search(r"[^\W\d_]", before, flags=re.UNICODE):
                    slots.append(("text", len(translatable)))
                    translatable.append(before)
                else:
                    slots.append(("token", before))
            slots.append(("token", core[start:end]))
            if core[end:end + 2].casefold() in ("'s", "’s"):
                slots.append(("token", turkish_genitive_suffix(core[start:end])))
                cursor = end + 2
            else:
                cursor = end
        after = core[cursor:]
        if after:
            if re.search(r"[^\W\d_]", after, flags=re.UNICODE):
                slots.append(("text", len(translatable)))
                translatable.append(after)
            else:
                slots.append(("token", after))
        if trailing:
            slots.append(("token", trailing))
    return slots, translatable


def rebuild(slots, translated):
    return "".join(value if kind == "token" else translated[value] for kind, value in slots)


def find_format_spans(text):
    """Biçim atomlarını ve iç içe koşulların yalnız yapısal işaretlerini bul."""
    spans = [(m.start(), m.end(), m.group(0)) for m in TOKEN_RE.finditer(text)]
    covered = [False] * len(text)
    for start, end, _ in spans:
        for index in range(start, end):
            covered[index] = True
    depth = 0
    for index, char in enumerate(text):
        if covered[index]:
            continue
        if char == "{":
            spans.append((index, index + 1, char))
            depth += 1
        elif char == "}":
            spans.append((index, index + 1, char))
            depth = max(0, depth - 1)
        elif depth and char in "?:":
            spans.append((index, index + 1, char))
    return sorted(spans, key=lambda item: (item[0], item[1]))


def protect_for_model(text, protected_names):
    replacements = []
    occupied = [(start, end, value, "TOKEN") for start, end, value in find_format_spans(text)]

    cursor = 0
    for start, end, _, _ in list(occupied) + [(len(text), len(text), "", "END")]:
        if cursor < start:
            gap = text[cursor:start]
            for name_start, name_end in find_protected_name_spans(gap, protected_names):
                absolute_start = cursor + name_start
                absolute_end = cursor + name_end
                occupied.append((absolute_start, absolute_end, text[absolute_start:absolute_end], "NAME"))
        cursor = max(cursor, end)

    occupied.sort(key=lambda item: (item[0], item[1]))
    output = []
    cursor = 0
    for start, end, original, kind in occupied:
        if start < cursor:
            continue
        output.append(text[cursor:start])
        # Marian and Qwen both copy this uncommon ASCII marker reliably.
        placeholder = f"ZXQ{len(replacements):04d}QXZ"
        output.append(placeholder)
        replacements.append((placeholder, original))
        cursor = end
    output.append(text[cursor:])
    return "".join(output), replacements


def restore_protected(text, replacements):
    missing = [placeholder for placeholder, _ in replacements if text.count(placeholder) != 1]
    if missing:
        return text, "protected WAKFU placeholder was changed or lost"
    placeholder_values = [placeholder for placeholder, _ in replacements]
    adjacent_left = {}
    adjacent_right = {}
    for placeholder in placeholder_values:
        position = text.find(placeholder)
        before = text[:position]
        after = text[position + len(placeholder):]
        adjacent_left[placeholder] = any(before.endswith(other) for other in placeholder_values)
        adjacent_right[placeholder] = any(after.startswith(other) for other in placeholder_values)
    for placeholder, original in replacements:
        # The model may concatenate a protected proper name with the preceding
        # or following translated word (for example ``WodentYeniden``).  Keep
        # markup/format tokens untouched, but restore normal word boundaries
        # around protected WAKFU names.  Apostrophe suffixes remain attached.
        original_is_format = bool(TOKEN_RE.fullmatch(original)) or original in {"{", "}", "?", ":"}
        if not original_is_format:
            position = text.find(placeholder)
            before = text[:position]
            after = text[position + len(placeholder):]
            left_space = (
                " "
                if not adjacent_left[placeholder]
                and re.search(r"[A-Za-zÇĞİÖŞÜçğıöşü]$", before)
                else ""
            )
            right_space = (
                " "
                if not adjacent_right[placeholder]
                and re.match(r"[A-Za-zÇĞİÖŞÜçğıöşü]", after)
                else ""
            )
            text = before + left_space + original + right_space + after
        else:
            text = text.replace(placeholder, original)
    if ZXQ_PLACEHOLDER_RE.search(text):
        return text, "protected WAKFU placeholder leaked into the final output"
    return text, ""


def clean_generated_segment(text):
    # Qwen3 may still emit a hidden reasoning block. It must never reach the game.
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    text = re.sub(r"(?i)^\s*(?:türkçe(?:\s+çeviri)?|çeviri|translation|turkish)\s*:\s*", "", text)
    return text.strip()


def quality_problem(source, translation):
    if re.search(r"(?iu)\b(?:heceler?|yazılımlar?)\b", translation) and re.search(r"(?i)\bspells?\b", source):
        return "spell was mistranslated as syllable/software"
    if re.search(r"(?iu)\b(?:monstrolar?|monstre|monsta)\b", translation):
        return "broken monster terminology"
    if re.search(r"(?iu)\bdönüş\s+(?:başına|sonunda|başlangıcında)\b", translation) and re.search(r"(?i)\bturn\b", source):
        return "turn was mistranslated as rotation/return"
    if not translation.strip():
        return "empty output"
    if "%%" in translation:
        return "percentage sign was duplicated"
    def percentage_values(text):
        values = []
        pattern = r"(?<![\w#])(?:%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%)"
        for match in re.finditer(pattern, text):
            values.append((match.group(1) or match.group(2)).replace(",", "."))
        return values
    source_percentages = percentage_values(source)
    target_percentages = percentage_values(translation)
    if sorted(source_percentages) != sorted(target_percentages):
        return "percentage values were changed or lost"
    if translation.strip() == source.strip() and re.search(r"[A-Za-z]{3}", source):
        return "unchanged English"
    if re.match(r"(?i)^\s*(translation|turkish|türkçe|çeviri|here is|işte)\s*:", translation):
        return "meta commentary"
    source_words = len(re.findall(r"[A-Za-zÀ-ž']+", source))
    target_words = len(re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşüÀ-ž']+", translation))
    if source_words >= 8 and target_words < max(2, int(source_words * 0.35)):
        return "missing sentence or severely shortened output"
    if len(source) >= 45 and len(translation) < int(len(source) * 0.30):
        return "severely shortened output"
    if re.search(r"ÃƒÆ’|Ãƒâ€|Ãƒâ€¦|Ã¢â‚¬|ï¿½", translation):
        return "broken text encoding"
    if ZXQ_PLACEHOLDER_RE.search(translation) or "ZXQ" in translation or "XQ" in translation or "QXZ" in translation:
        return "protected WAKFU placeholder leaked into the output"
    if re.search(r"(?iu)\b[A-Za-zÇĞİÖŞÜçğıöşü]+(?:y?[ıiuü])\s+sahip\b", translation):
        return "incorrect Turkish case suffix before 'sahip'"
    if SUSPICIOUS_TURKISH_RE.search(translation):
        return "known machine-translation grammar or meaning error"
    if len(ENGLISH_LEFTOVER_RE.findall(translation)) >= 1:
        return "English words remain in the Turkish output"
    return ""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--live-log")
    parser.add_argument("--batch", type=int, default=2)
    parser.add_argument("--force-qwen", action="store_true")
    parser.add_argument("--no-qwen-fallback", action="store_true")
    parser.add_argument(
        "--qwen-model",
        choices=("8b-q4", "4b-q6"),
        default="8b-q4",
        help="Quality model variant. The application keeps 8B Q4 as its default.",
    )
    args = parser.parse_args()

    with open(args.context, "r", encoding="utf-8-sig") as context_file:
        localization_context = json.load(context_file)
    protected_names = {
        normalized_name(name) for name in localization_context.get("protected_names", []) if name.strip()
    }
    # Bazı kısa İngilizce sözcükler hem bir beceri/durum adı hem de normal bir
    # cümlenin fiili veya arayüz terimi olabilir (ör. "Defeat", "Damage",
    # "Characteristics"). Kendi ad satırları zaten çeviri girdisine alınmaz;
    # başka cümlelerdeyse bu sözcükleri kilitlemek "Defeat 1 Gobball" gibi
    # görevleri tamamen İngilizce bırakıyordu.
    generic_name_conflicts = {
        "action", "activate", "age", "all", "any", "armor", "attack",
        "available", "battlefield", "battlefields", "block", "build", "challenge", "change", "characteristic",
        "characteristics", "choose", "close", "color", "control", "critical",
        "current", "damage", "default", "defeat", "distance", "dust", "earth",
        "farmer", "filter", "fire", "following", "handyman", "heal", "heals",
        "health", "inventory", "item", "items", "level", "mastery", "max",
        "melee", "miller", "min", "mines", "mobility", "name", "none", "normal",
        "open", "page", "point", "points", "positioning", "protection", "quest",
        "range", "rarity", "rear", "recommended", "remove", "reset", "resistance",
        "ranking", "reward", "round", "search", "select", "spell", "spells", "support", "tab", "transfer", "turn", "unavailable",
        "video", "water", "year",
        "rear mastery", "elemental mastery", "melee mastery", "distance mastery",
        "critical mastery", "healing mastery", "berserk mastery", "elemental resistance",
        "characteristics page", "default build", "action points", "movement points",
    }
    sentence_protected_names = {
        name for name in protected_names if name.casefold() not in generic_name_conflicts
    }
    # Kısa ve genel eşya adları (ör. "Tab" veya "Color") arayüzde normal
    # sözcük olarak da geçebilir. Arayüz cümlelerinde yalnız ayırt edici uzun
    # ya da çok sözcüklü özel adları kilitle.
    ui_protected_names = {
        name for name in sentence_protected_names if len(WORD_RE.findall(name)) >= 2 or len(name) >= 10
    }

    def names_for_category(category):
        # Diyalog/görev/açıklamalarda kısa özel adlar da önemlidir. Genel arayüz
        # ve mekanik başlıklarında ise "Air", "Bonus", "Color" gibi kısa eşya
        # adları normal sözcükleri yanlışlıkla kilitlememelidir.
        if category in {"DIYALOG_HIKAYE", "GOREV_HEDEF", "REHBER_EGITIM", "ESYA_ACIKLAMA", "PAZAR_TICARET"}:
            return sentence_protected_names
        if category == "GENEL_OYUN_METNI":
            # Gerçek özel adları cümlenin içinde koru. "Damage", "Block",
            # "Battlefields" gibi normal oyun terimleri generic_name_conflicts
            # listesinden çıkarıldığı için artık yanlışlıkla kilitlenmez.
            return sentence_protected_names
        if category == "MEKANIK_BUFF_ACIKLAMA":
            return sentence_protected_names
        return ui_protected_names
    glossary = localization_context.get("glossary", {})
    forced_glossary = {
        "item": "eşya",
        "items": "eşyalar",
        "Guards": "Muhafızlar",
        "Marketplace": "Pazar Yeri",
        "participation grade": "katılım notu",
        "Spells": "Büyüler",
        "spell": "büyü",
        "spells": "büyüler",
        "Active Spells": "Aktif Büyüler",
        "Current ranking:": "Mevcut sıralama:",
        "Color": "Renk",
        "Open the chest": "Sandığı aç.",
        "Battlefield": "Savaş Alanı",
        "Battlefields": "Savaş Alanları",
        "Take part in 5 Battlefields": "5 Savaş Alanına katıl",
        "Each Block point makes you 1% more likely to reduce damage received by 20%.": "Her Blok puanı, alınan hasarı %20 azaltma ihtimalini %1 artırır.",
        "Are you sure you want to reset <b>all</b> your characteristics pages?": "<b>Tüm</b> özellik sayfalarınızı sıfırlamak istediğinizden emin misiniz?",
        "Are you sure you want to unlock [#1] item{[>1]?s:}? Items with a quantity of zero will be removed.": "[#1] eşyanın kilidini açmak istediğinizden emin misiniz? Miktarı sıfır olan eşyalar kaldırılacaktır.",
        "Hidden": "Gizli",
        "Penalty": "Ceza",
        "Armor": "Zırh",
        "Range": "Menzil",
        "Turn": "Tur",
        "Level": "Seviye",
        "Experience": "Deneyim",
        "Wisdom": "Bilgelik",
        "Willpower": "İrade",
        "Prospecting": "Ganimet Bulma",
    }
    forced_keys = {key.casefold() for key in forced_glossary}
    for old_key in list(glossary):
        if str(old_key).casefold() in forced_keys:
            del glossary[old_key]
    for english, turkish in forced_glossary.items():
        # Eski terim belleğinde item/items için "öğe" kalmış olabilir. Wakfu
        # kullanıcı tercihi "eşya" olduğundan bunlar zorunlu güncellenir.
        glossary[english] = turkish
    glossary_casefold = {str(key).casefold(): str(value) for key, value in glossary.items() if key and value}

    def quality_problem_ignoring_names(source, translation, names):
        problem = quality_problem(source, translation)
        if problem and problem != "English words remain in the Turkish output":
            return problem
        cleaned = translation
        for name in sorted(names, key=len, reverse=True):
            if len(name) >= 3 and name in cleaned:
                cleaned = cleaned.replace(name, " ")
        if ENGLISH_LEFTOVER_RE.search(cleaned):
            return "English words remain in the Turkish output"

        # A fixed English dictionary can never cover the complete WAKFU corpus.
        # Detect source words copied verbatim into the Turkish result as well.
        # Proper names have already been removed above; a small list of genuine
        # Turkish/industry cognates is intentionally allowed.
        allowed_identical = {
            "bonus", "normal", "portal", "festival", "video", "internet",
            "arena", "robot", "radar", "test", "risk", "plan", "mode",
            "pixel", "server", "forum", "menu", "status", "premium",
            "wakfu", "dofus", "kama", "kamas",
        }
        target_words = {
            word.casefold() for word in re.findall(r"[A-Za-z]+", cleaned)
        }
        for word in re.findall(r"[A-Za-z]+", source):
            folded = word.casefold()
            if len(folded) >= 4 and folded not in allowed_identical and folded in target_words:
                return f"English source word remains in output: {word}"
        return ""

    def apply_glossary(source, translated):
        """Kaynakta geçen zorunlu Wakfu terimlerini model çıktısında uygula."""
        source_folded = source.casefold()
        for english, turkish in sorted(glossary.items(), key=lambda pair: len(pair[0]), reverse=True):
            if not english or not turkish or english.casefold() not in source_folded:
                continue
            pattern = r"(?i)(?<!\w)" + re.escape(english) + r"(?!\w)"
            translated = re.sub(pattern, lambda _, replacement=turkish: replacement, translated)
        return translated

    def normalize_target_terms(source, translated):
        """Accept fluent MT synonyms, then normalize them to the Wakfu glossary."""
        source_folded = source.casefold()
        if re.search(r"(?iu)(?<!\w)items?(?!\w)", source):
            replacements = {
                # OPUS/NLLB generic "item" karşılığı olarak öğe, madde, ürün
                # ve nesne kullanabiliyor. WAKFU arayüzünde bunların tamamı
                # kullanıcı tercihine göre tutarlı biçimde "eşya" olmalı.
                "öğelerinizden": "eşyalarınızdan", "öğelerinizin": "eşyalarınızın",
                "öğelerinizi": "eşyalarınızı", "öğeleriniz": "eşyalarınız",
                "öğelerinden": "eşyalarından", "öğelerinin": "eşyalarının",
                "öğelerini": "eşyalarını", "öğelerine": "eşyalarına",
                "öğelerinde": "eşyalarında", "öğelerden": "eşyalardan",
                "öğelerin": "eşyaların", "öğelere": "eşyalara", "öğelerde": "eşyalarda",
                "öğeyi": "eşyayı", "öğenin": "eşyanın", "öğeye": "eşyaya",
                "öğede": "eşyada", "öğeden": "eşyadan",
                "öğeleri": "eşyaları", "öğesi": "eşyası", "öğe": "eşya",
                "ögelerinizden": "eşyalarınızdan", "ögelerinizin": "eşyalarınızın",
                "ögelerinizi": "eşyalarınızı", "ögeleriniz": "eşyalarınız",
                "ögelerinden": "eşyalarından", "ögelerinin": "eşyalarının",
                "ögelerini": "eşyalarını", "ögelerine": "eşyalarına",
                "ögelerinde": "eşyalarında", "ögelerden": "eşyalardan",
                "ögelerin": "eşyaların", "ögelere": "eşyalara", "ögelerde": "eşyalarda",
                "ögeler": "eşyalar", "ögeyi": "eşyayı", "ögenin": "eşyanın",
                "ögeye": "eşyaya", "ögede": "eşyada", "ögeden": "eşyadan",
                "ögesini": "eşyasını", "ögeleri": "eşyaları", "ögesi": "eşyası",
                "öge": "eşya",
                "maddelerinizden": "eşyalarınızdan", "maddelerinizin": "eşyalarınızın",
                "maddelerinizi": "eşyalarınızı", "maddeleriniz": "eşyalarınız",
                "maddelerinden": "eşyalarından", "maddelerinin": "eşyalarının",
                "maddelerini": "eşyalarını", "maddelerine": "eşyalarına",
                "maddelerinde": "eşyalarında", "maddelerden": "eşyalardan",
                "maddelerin": "eşyaların", "maddelere": "eşyalara", "maddelerde": "eşyalarda",
                "maddeler": "eşyalar", "maddeyi": "eşyayı", "maddenin": "eşyanın",
                "maddeye": "eşyaya", "maddede": "eşyada", "maddeden": "eşyadan",
                "maddeyle": "eşyayla", "maddesini": "eşyasını", "maddeleri": "eşyaları",
                "maddesi": "eşyası", "maddedir": "eşyadır", "madde": "eşya",
                "ürünlerinizden": "eşyalarınızdan", "ürünlerinizin": "eşyalarınızın",
                "ürünlerinizi": "eşyalarınızı", "ürünleriniz": "eşyalarınız",
                "ürünlerinden": "eşyalarından", "ürünlerinin": "eşyalarının",
                "ürünlerini": "eşyalarını", "ürünlerine": "eşyalarına",
                "ürünlerinde": "eşyalarında", "ürünlerden": "eşyalardan",
                "ürünlerin": "eşyaların", "ürünlere": "eşyalara", "ürünlerde": "eşyalarda",
                "ürünler": "eşyalar", "ürünü": "eşyayı", "ürünün": "eşyanın",
                "ürüne": "eşyaya", "üründe": "eşyada", "üründen": "eşyadan",
                "ürünle": "eşyayla", "ürünleri": "eşyaları", "ürünüyle": "eşyasıyla",
                "ürün": "eşya",
                "nesnelerini": "eşyalarını", "nesnesini": "eşyasını",
                "nesneleriniz": "eşyalarınız", "nesnelerinden": "eşyalarından",
                "nesnelerinin": "eşyalarının", "nesnelerine": "eşyalarına",
                "nesnelerden": "eşyalardan", "nesnelerin": "eşyaların",
                "nesneler": "eşyalar", "nesneyi": "eşyayı", "nesnenin": "eşyanın",
                "nesneye": "eşyaya", "nesnede": "eşyada", "nesneden": "eşyadan",
                "nesneleri": "eşyaları", "nesnesi": "eşyası", "nesne": "eşya",
            }
            for old, new in sorted(replacements.items(), key=lambda pair: len(pair[0]), reverse=True):
                def item_replacement(match, value=new):
                    return value[:1].upper() + value[1:] if match.group(0)[:1].isupper() else value
                translated = re.sub(r"(?iu)(?<!\w)" + re.escape(old) + r"(?!\w)", item_replacement, translated)
        if re.search(r"(?iu)(?<!\w)damage(?!\w)", source):
            translated = re.sub(r"(?iu)(?<!\w)zarar", "hasar", translated)
        if re.search(r"(?iu)(?<!\w)dagger(?!\w)", source):
            translated = re.sub(r"(?iu)(?<!\w)kılıç", "hançer", translated)
        if re.search(r"(?iu)(?<!\w)behind(?!\w)", source):
            translated = re.sub(r"(?iu)(?<!\w)geriye(?!\w)", "arkadan", translated)
        if "elemental resistance" in source_folded or "elemental resistances" in source_folded:
            translated = re.sub(
                r"(?iu)(?<!\w)(?:elementel|temel)\s+direnç(?:ler)?(?:i|leri|lerini|lerinin)?(?!\w)",
                "Element Direnci", translated,
            )
        if re.search(r"(?iu)(?<!\w)builds?(?!\w)", source):
            translated = re.sub(r"(?iu)\binşa(?:at)?\b", "yapı", translated)
            translated = re.sub(r"(?iu)\bderleme\b", "yapı", translated)
            translated = re.sub(r"(?iu)\bYapı\s+(?:et|yap)\b", "Yapı", translated)
        mastery_replacements = {
            "distance mastery": ((r"(?iu)\b(?:mesafe|uzaktan)\s+ustalığı\b", "Menzil Ustalığı"),),
            "rear mastery": ((r"(?iu)\barka\s+ustalık(?:lığı|lık)?\b", "Arkadan Ustalık"),),
            "healing mastery": ((r"(?iu)\b(?:healing|iyileşme)\s+ustalık(?:lığı|lık)?\b", "İyileştirme Ustalığı"),),
            "critical mastery": ((r"(?iu)\beleştirel\s+(?:olmayan\s+)?ustalık(?:lığı|lık)?\b", lambda m: "Kritik Olmayan Ustalık" if "olmayan" in m.group(0).casefold() else "Kritik Ustalığı"),),
            "elemental mastery": ((r"(?iu)\belemental\s+mastery\b", "Element Ustalığı"),),
            "melee mastery": ((r"(?iu)\bmelee\s+mastery\b", "Yakın Dövüş Ustalığı"),),
        }
        for english_term, rules in mastery_replacements.items():
            if english_term in source_folded:
                for pattern, replacement in rules:
                    translated = re.sub(pattern, replacement, translated)
        if "participation grade" in source_folded:
            translated = re.sub(r"(?iu)\bkatılım (?:derecesi|puanı)\b", "katılım notu", translated)
        if "marketplace" in source_folded:
            translated = re.sub(r"(?iu)\bMarketplace['’]?de\b", "Pazar Yerinde", translated)
            translated = re.sub(r"(?iu)\bMarketplace['’]?den\b", "Pazar Yerinden", translated)
            translated = re.sub(r"(?iu)\bMarketplace\b", "Pazar Yeri", translated)
        if "battlefield" in source_folded:
            translated = re.sub(r"(?iu)\bSavaş Alanı['’]a\b", "Savaş Alanına", translated)
            translated = re.sub(r"(?iu)\bSavaş Alanları['’]a\b", "Savaş Alanlarına", translated)
        return translated

    def glossary_problem(source, translated):
        source_folded = source.casefold()
        target_folded = translated.casefold()
        for english, turkish in sorted(glossary.items(), key=lambda pair: len(pair[0]), reverse=True):
            if not english or not turkish or english.casefold() not in source_folded:
                continue
            required = turkish.casefold()
            required_stem = re.sub(r"(?:ları|leri|lığı|liği|luğu|lüğü)$", "", required)
            if len(english) >= 4 and required not in target_folded and required_stem not in target_folded:
                return f"mandatory WAKFU term missing: {english} => {turkish}"
        return ""

    import torch
    if os.name == "nt":
        os.add_dll_directory(os.path.join(os.path.dirname(torch.__file__), "lib"))
        # The portable CUDA wheel keeps llama.cpp and its dependent DLLs in
        # the package-level bin directory. Registering that directory makes
        # the worker independent from the EXE's current working directory.
        package_bin = os.path.join(os.path.dirname(torch.__file__), "..", "bin")
        package_bin = os.path.abspath(package_bin)
        if os.path.isdir(package_bin):
            os.add_dll_directory(package_bin)
    from huggingface_hub import hf_hub_download
    from llama_cpp import Llama
    from transformers import MarianMTModel, MarianTokenizer

    if not torch.cuda.is_available():
        emit("ERROR|NVIDIA CUDA kullanılamıyor; ekran kartı sürücüsünü kontrol edin.")
        return 2

    device_name = torch.cuda.get_device_name(0)
    total_vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    emit(f"DEVICE|{device_name}|{total_vram:.1f} GB")

    opus_tokenizer = None
    opus_model = None
    if not args.force_qwen:
        emit("STATUS|Hızlı İngilizce-Türkçe OPUS modeli yükleniyor…")
        loading_stop = start_loading_heartbeat("OPUS_INDIRME_YUKLEME")
        try:
            opus_id = "Helsinki-NLP/opus-mt-tc-big-en-tr"
            opus_cache = os.path.join(args.cache, "opus_en_tr_cache")
            try:
                opus_tokenizer = MarianTokenizer.from_pretrained(
                    opus_id, cache_dir=opus_cache, local_files_only=True
                )
                opus_model = MarianMTModel.from_pretrained(
                    opus_id, cache_dir=opus_cache, dtype=torch.float16, local_files_only=True
                ).to("cuda").eval()
            except Exception:  # noqa: BLE001
                emit("STATUS|OPUS modeli ilk kullanım için indiriliyor; bu işlem yalnız bir kez yapılır…")
                opus_tokenizer = MarianTokenizer.from_pretrained(
                    opus_id, cache_dir=opus_cache, local_files_only=False
                )
                opus_model = MarianMTModel.from_pretrained(
                    opus_id, cache_dir=opus_cache, dtype=torch.float16, local_files_only=False
                ).to("cuda").eval()
        finally:
            loading_stop.set()
        emit("STATUS|Hızlı OPUS hazır; Qwen yalnız kalite reddi alan satırları düzeltecek.")
    else:
        emit("STATUS|Zorunlu kalite turu: OPUS atlandı, tüm satırlar Qwen ile işlenecek.")

    model = None

    def ensure_qwen():
        nonlocal model
        if model is not None:
            return model
        emit("STATUS|Şüpheli satırlar için Qwen3-8B Q4 kalite düzelticisi yükleniyor…")
        qwen_loading_stop = start_loading_heartbeat("QWEN_INDIRME_YUKLEME")
        try:
            if args.qwen_model == "4b-q6":
                qwen_repo = "Qwen/Qwen3-4B-GGUF"
                qwen_filename = "Qwen3-4B-Q6_K.gguf"
                qwen_cache = os.path.join(args.cache, "qwen3_model_cache")
            else:
                qwen_repo = "Qwen/Qwen3-8B-GGUF"
                qwen_filename = "Qwen3-8B-Q4_K_M.gguf"
                qwen_cache = os.path.join(args.cache, "qwen3_8b_model_cache")
            try:
                model_path = hf_hub_download(
                    repo_id=qwen_repo, filename=qwen_filename,
                    cache_dir=qwen_cache, local_files_only=True,
                )
            # Her yerel önbellek hatasında çevrimiçi indirmeyi bir kez dene.
            except Exception:  # noqa: BLE001
                emit("STATUS|Qwen3-8B modeli ilk kullanım için indiriliyor; bu işlem yalnız bir kez yapılır…")
                model_path = hf_hub_download(
                    repo_id=qwen_repo, filename=qwen_filename,
                    cache_dir=qwen_cache, local_files_only=False,
                )
            model = Llama(
                model_path=model_path,
                n_gpu_layers=-1,
                # RTX 2080 Super'da 151 bin sözcüklü Qwen çıktısının 512'lik
                # logits tamponu yaklaşık 300 MB ayırıyordu ve uzun çalışmada
                # MemoryError üretiyordu. 64 aynı kaliteyi korur; yalnızca
                # geçici çalışma belleğini ciddi biçimde küçültür.
                n_ctx=4096,
                n_batch=64,
                n_threads=max(2, (os.cpu_count() or 4) // 2),
                flash_attn=True,
                verbose=False,
            )
        finally:
            qwen_loading_stop.set()
        emit("STATUS|Qwen3-8B Q4 kalite düzelticisi hazır.")
        return model

    category_guidance = {
        "ARAYUZ": "Use concise, immediately understandable and consistent Turkish UI wording.",
        "PAZAR_TICARET": "Use clear Turkish marketplace terminology. Never translate item names.",
        "GOREV_HEDEF": "Use natural quest language. Objectives should be concise Turkish imperatives.",
        "DIYALOG_HIKAYE": "Preserve emotion, humor and intent in natural spoken Turkish. Never translate proper names.",
        "REHBER_EGITIM": "Translate every instruction in fluent, beginner-friendly Turkish without omissions.",
        "MEKANIK_BUFF_ACIKLAMA": "Translate mechanics precisely. Preserve values, abbreviations and all protected names.",
        "ESYA_ACIKLAMA": "Translate flavor and mechanics fluently while keeping the item name unchanged.",
        "OZEL_MEKAN_ADI": "Keep lore proper names unchanged, but translate generic place words naturally into Turkish.",
        "GENEL_OYUN_METNI": "Use fluent, idiomatic Turkish suitable for a polished commercial game localization.",
    }
    base_prompt = (
        "/no_think\nYou are the senior Turkish localization editor for WAKFU. Translate the English text into polished, "
        "natural and unambiguous Turkish. Never translate character names, NPC names, monster names, class names, "
        "item names, skill names or buff/state names. Preserve numbers, abbreviations, meaning, tone and every "
        "sentence. Never invent, censor, summarize or explain. Preserve every ZXQ0000QXZ-style placeholder "
        "exactly; you may add normal Turkish suffixes after name placeholders. "
        "Translate by meaning, never word-for-word. Use correct Turkish case suffixes, possessives, subjects and "
        "natural word order. Never mix text from separate input items. Before answering, silently verify meaning, "
        "Turkish grammar, terminology, completeness and placeholders. "
        "Prefer concise game language: 'Take part in 5 Battlefields' means '5 Savaş Alanına katıl'; "
        "'when health is below 50%' means 'can %50'nin altındayken'. Avoid literal English word order. "
        "Return only the Turkish translation with no label, quotation marks or commentary."
    )

    def translate_segment(segment, category, replacements):
        leading = segment[: len(segment) - len(segment.lstrip())]
        trailing = segment[len(segment.rstrip()):]
        source_core = segment.strip()
        if not source_core:
            return segment, ""
        exact_term = glossary_casefold.get(source_core.casefold())
        if exact_term:
            return leading + exact_term + trailing, ""
        lowered = source_core.casefold()
        relevant_terms = [(src, dst) for src, dst in glossary.items() if src and src.casefold() in lowered][:24]
        term_text = ""
        if relevant_terms:
            term_text = "\nMandatory WAKFU terminology: " + "; ".join(f"{src} => {dst}" for src, dst in relevant_terms)
        guidance = category_guidance.get(category, category_guidance["GENEL_OYUN_METNI"])
        last = ""
        problem = ""
        qwen = ensure_qwen()
        for attempt in range(2):
            correction = "" if not problem else f"\nPrevious output failed validation: {problem}. Correct it fully."
            response = qwen.create_chat_completion(
                messages=[
                    {"role": "system", "content": base_prompt + "\nCategory: " + category + ". " + guidance + term_text + correction},
                    {"role": "user", "content": "/no_think\n" + source_core},
                ],
                temperature=0.05,
                top_p=0.95,
                top_k=20,
                repeat_penalty=1.05,
                max_tokens=min(768, max(32, int(len(source_core) * 1.5))),
                seed=attempt,
                stream=True,
            )
            chunks = []
            last_heartbeat = time.time()
            for chunk in response:
                delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    chunks.append(delta)
                if time.time() - last_heartbeat >= 1.5:
                    emit("HEARTBEAT|MODEL_YANITI")
                    last_heartbeat = time.time()
            last = normalize_target_terms(
                source_core, apply_glossary(source_core, clean_generated_segment("".join(chunks)))
            )
            if replacements:
                restored_last, problem = restore_protected(last, replacements)
                if not problem:
                    restored_source, _ = restore_protected(source_core, replacements)
                    protected_name_values = {original for _, original in replacements}
                    problem = quality_problem_ignoring_names(
                        restored_source, restored_last, protected_name_values
                    )
            else:
                problem = quality_problem(source_core, last)
            if not problem:
                return leading + last + trailing, ""
        return leading + last + trailing, problem

    def stream_text(messages, max_tokens, seed=0, response_format=None):
        response = ensure_qwen().create_chat_completion(
            messages=messages,
            temperature=0.05,
            top_p=0.95,
            top_k=20,
            repeat_penalty=1.05,
            max_tokens=max_tokens,
            seed=seed,
            response_format=response_format,
            stream=True,
        )
        chunks = []
        last_heartbeat = time.time()
        for chunk in response:
            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if delta:
                chunks.append(delta)
            if time.time() - last_heartbeat >= 1.5:
                emit("HEARTBEAT|MODEL_YANITI")
                last_heartbeat = time.time()
        return clean_generated_segment("".join(chunks))

    def opus_translate(texts):
        encoded = opus_tokenizer(
            texts, return_tensors="pt", padding=True, truncation=True, max_length=512
        ).to("cuda")
        with torch.inference_mode():
            generated = opus_model.generate(
                **encoded,
                num_beams=2,
                max_new_tokens=384,
                renormalize_logits=True,
            )
        return [clean_generated_segment(value) for value in opus_tokenizer.batch_decode(
            generated, skip_special_tokens=True
        )]

    def preserve_outer_whitespace(source_segment, translated):
        """OPUS trims fragments; retain spaces around protected WAKFU names."""
        leading = source_segment[: len(source_segment) - len(source_segment.lstrip())]
        trailing = source_segment[len(source_segment.rstrip()):]
        return leading + translated.strip() + trailing

    def normalize_objective(source, translation):
        match = re.match(r"(?i)^\s*Defeat\s+((?:\[#\d+\]|\d+))\s+(.+?)\s*$", source)
        if match:
            return f"{match.group(1)} adet {match.group(2)} yen"
        if re.match(r"(?i)^\s*Defeat\b", source) and not re.search(
            r"(?iu)\b(?:yen|yenilgiye\s+uğrat|mağlup\s+et)", translation
        ):
            remainder = re.sub(r"(?i)^\s*Defeat\s*", "", translation).strip()
            return f"{remainder} yen" if remainder else translation
        return translation

    def translate_unit(unit):
        names = names_for_category(unit["category"])
        source = normalize_game_english(unit["english"])
        # Cümleyi özel adların etrafından bölmek bağlamı ve Türkçe söz dizimini
        # bozuyordu. Adları/biçim kodlarını güvenli işaretlerle kilitle, metnin
        # tamamını tek bağlamda çevir ve ardından özgün değerleri geri koy.
        protected_source, replacements = protect_for_model(source, names)
        translated, problem = translate_segment(
            protected_source, unit["category"], replacements
        )
        if problem:
            return "", problem
        translation, restore_problem = restore_protected(translated, replacements)
        if restore_problem:
            return "", restore_problem
        translation = normalize_objective(source, translation)
        problem = quality_problem_ignoring_names(source, translation, names)
        return translation, problem

    def translate_units_qwen_batch(units):
        """Repair rejected rows in one constrained Qwen call.

        Each complete sentence is protected and sent as one JSON item. Older
        code split a sentence around proper names and translated the fragments
        independently; that destroyed Turkish word order and case suffixes.
        """
        category = units[0]["category"]
        prepared = []
        metadata = {}
        exact_results = {}
        for unit_index, unit in enumerate(units):
            names = names_for_category(unit["category"])
            source = normalize_game_english(unit["english"])
            exact = glossary_casefold.get(source.strip().casefold())
            if exact:
                exact_results[unit_index] = (exact, "")
                continue
            protected_source, replacements = protect_for_model(source, names)
            row_id = len(prepared)
            prepared.append({"id": row_id, "text": protected_source})
            metadata[row_id] = (unit_index, source, replacements, names)

        if not prepared:
            return [exact_results[index] for index in range(len(units))]

        relevant_terms = {}
        combined_source = "\n".join(row["text"] for row in prepared).casefold()
        for english, turkish in sorted(glossary.items(), key=lambda pair: len(pair[0]), reverse=True):
            if english and turkish and english.casefold() in combined_source:
                relevant_terms[english] = turkish
            if len(relevant_terms) >= 40:
                break
        term_prompt = ""
        if relevant_terms:
            term_prompt = "\nMandatory WAKFU terminology: " + "; ".join(
                f"{english} => {turkish}" for english, turkish in relevant_terms.items()
            )

        prompt = (
            "Translate every JSON row independently into polished Turkish. Return only valid JSON as "
            "{\"translations\":[{\"id\":0,\"tr\":\"...\"}]}. Preserve every id exactly once. "
            "Do not add explanations or combine rows. Translate every sentence completely. Preserve every "
            "ZXQ0000QXZ placeholder exactly and place normal Turkish suffixes after it when needed.\n"
            "Category: " + category + ". " + category_guidance.get(category, category_guidance["GENEL_OYUN_METNI"]) +
            "." + term_prompt + "\n/no_think\n" + json.dumps(prepared, ensure_ascii=False)
        )
        schema = {
            "type": "object",
            "properties": {"translations": {"type": "array", "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "tr": {"type": "string"}},
                "required": ["id", "tr"], "additionalProperties": False,
            }, "minItems": len(prepared), "maxItems": len(prepared)}},
            "required": ["translations"], "additionalProperties": False,
        }
        raw = stream_text(
            [{"role": "system", "content": base_prompt}, {"role": "user", "content": prompt}],
            min(1800, max(128, int(sum(len(row["text"]) for row in prepared) * 1.45))),
            response_format={"type": "json_object", "schema": schema},
        )
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < start:
            raise ValueError("Qwen paket JSON yanıtı bulunamadı")
        payload = json.loads(raw[start:end + 1])
        mapped = {int(row["id"]): clean_generated_segment(str(row["tr"])) for row in payload["translations"]}
        if set(mapped) != set(range(len(prepared))):
            raise ValueError("Qwen paket yanıtında eksik/fazla kimlik var")

        repaired = dict(exact_results)
        for row_id, mapped_translation in mapped.items():
            unit_index, source, replacements, names = metadata[row_id]
            protected_translation = normalize_target_terms(
                source, apply_glossary(source, mapped_translation)
            )
            translation, restore_problem = restore_protected(protected_translation, replacements)
            translation = normalize_objective(source, translation)
            problem = restore_problem or quality_problem_ignoring_names(source, translation, names)
            if not problem:
                problem = glossary_problem(source, translation)
            if problem:
                # Paket yanıtında yalnız bu satır başarısızsa bütün paketi
                # yeniden üretme; satırı tam bağlamıyla iki denemeli tekli
                # kalite yoluna gönder.
                retry_translation, retry_problem = translate_unit(units[unit_index])
                if not retry_problem:
                    translation, problem = retry_translation, ""
            repaired[unit_index] = (translation, problem)
        return [repaired[index] for index in range(len(units))]

    def translate_unit_batch(units):
        if args.force_qwen:
            return translate_units_qwen_batch(units)
        batch_category = units[0]["category"]
        if any(unit["category"] != batch_category for unit in units):
            raise ValueError("aynı pakette farklı metin kategorileri bulunamaz")
        slots_by_id = {}
        segment_ranges = {}
        all_segments = []
        source_by_id = {}
        for index, unit in enumerate(units):
            names = names_for_category(unit["category"])
            source = normalize_game_english(unit["english"])
            slots, segments = split_protected(source, names)
            start = len(all_segments)
            all_segments.extend(segments)
            segment_ranges[index] = (start, len(all_segments))
            slots_by_id[index] = slots
            source_by_id[index] = source
        drafts = []
        # Biçim kodları modele hiç gönderilmez. Kalan düz metin parçaları
        # küçük GPU paketleriyle çevrilir; böylece ZXQ sızıntısı ve büyük geçici
        # bellek tahsisi tamamen ortadan kalkar.
        for start in range(0, len(all_segments), 64):
            drafts.extend(opus_translate(all_segments[start:start + 64]))
        results = []
        for index, unit in enumerate(units):
            exact = glossary_casefold.get(unit["english"].strip().casefold())
            first, last = segment_ranges[index]
            translated_parts = []
            for source_segment, draft in zip(all_segments[first:last], drafts[first:last]):
                translated_parts.append(normalize_target_terms(
                    source_segment,
                    apply_glossary(source_segment, clean_generated_segment(draft)),
                ))
            translated_parts = [
                preserve_outer_whitespace(src, tr)
                for src, tr in zip(all_segments[first:last], translated_parts)
            ]
            translation = exact or rebuild(slots_by_id[index], translated_parts)
            translation = normalize_target_terms(
                source_by_id[index], apply_glossary(source_by_id[index], translation)
            )
            translation = normalize_objective(source_by_id[index], translation)
            names = names_for_category(unit["category"])
            problem = quality_problem_ignoring_names(source_by_id[index], translation, names)
            if problem:
                emit(f"QUALITY_FALLBACK|{unit['items'][0].get('key', '')}|{problem}")
                if not args.no_qwen_fallback:
                    translation, problem = translate_unit(unit)
            results.append((translation, problem))
        return results

    def translate_units_safe(units):
        try:
            return translate_unit_batch(units)
        # Model/işletim katmanındaki her hata paketi küçülterek yeniden denenir.
        except Exception as exc:  # noqa: BLE001
            emit(f"BATCH_RETRY|{len(units)}|{type(exc).__name__}: {exc}")
            if len(units) == 1:
                try:
                    return [translate_unit(units[0])]
                except Exception as single_exc:  # noqa: BLE001
                    return [("", f"worker exception: {type(single_exc).__name__}: {single_exc}")]
            middle = len(units) // 2
            return translate_units_safe(units[:middle]) + translate_units_safe(units[middle:])

    items = []
    with open(args.input, "r", encoding="utf-8-sig") as source:
        for line in source:
            if line.strip():
                items.append(json.loads(line))

    # Aynı İngilizce metin/kategoriyi yalnızca bir kez modele gönder. Dofus/Wakfu
    # veri tabanında aynı metin binlerce anahtarda tekrar edebiliyor.
    units = []
    unit_by_source = {}
    for item in items:
        token = (item["english"], item.get("category", "GENEL_OYUN_METNI"))
        unit = unit_by_source.get(token)
        if unit is None:
            unit = {"english": token[0], "category": token[1], "items": []}
            unit_by_source[token] = unit
            units.append(unit)
        unit["items"].append(item)

    batches = []
    by_category = {}
    for unit in units:
        by_category.setdefault(unit["category"], []).append(unit)
    for category_units in by_category.values():
        pending = []
        pending_chars = 0
        for unit in category_units:
            length = len(unit["english"])
            can_batch = length <= 1400
            has_long = length > 120 or any(len(row["english"]) > 120 for row in pending)
            if args.force_qwen:
                unit_limit = min(max(1, args.batch), 4 if has_long else 10)
                char_limit = 1800 if has_long else 2200
            else:
                unit_limit = min(max(1, args.batch), 8 if has_long else 32)
                char_limit = 5000 if has_long else 3000
            # Kısa arayüz satırları 32'li, uzun görev/öğretici metinleri 8'li
            # güvenli GPU paketlerinde çalışır. 8 GB VRAM sınırı aşılmaz.
            if not can_batch or len(pending) >= unit_limit or (pending and pending_chars + length > char_limit):
                if pending:
                    batches.append(pending)
                    pending = []
                    pending_chars = 0
                has_long = length > 120
                if args.force_qwen:
                    unit_limit = min(max(1, args.batch), 4 if has_long else 10)
                    char_limit = 1800 if has_long else 2200
                else:
                    unit_limit = min(max(1, args.batch), 8 if has_long else 32)
                    char_limit = 5000 if has_long else 3000
            if can_batch:
                pending.append(unit)
                pending_chars += length
            else:
                batches.append([unit])
        if pending:
            batches.append(pending)
    emit(f"DEDUP|{len(items)}|{len(units)}|{len(batches)}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = 0
    started = time.time()

    live_target = None
    if args.live_log:
        live_path = Path(args.live_log)
        live_path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not live_path.exists() or live_path.stat().st_size == 0
        live_target = live_path.open("a", encoding="utf-8-sig" if is_new else "utf-8", buffering=1)
        if is_new:
            live_target.write("Zaman\tYontem\tAnahtar\tKategori\tDurum\tIngilizce\tTurkce\tAciklama\n")

    def live_field(value):
        return str(value or "").replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")

    with output_path.open("w", encoding="utf-8", buffering=1) as target:
        for batch_number, batch_units in enumerate(batches, 1):
            first_key = batch_units[0]["items"][0].get("key", "")
            emit(f"ITEM_START|{first_key}|{completed + 1}|{len(items)}|paket {batch_number}/{len(batches)}")
            results = translate_units_safe(batch_units)
            for unit, (translation, worker_problem) in zip(batch_units, results):
                for item in unit["items"]:
                    target.write(json.dumps({
                        "key": item["key"],
                        "translation": translation,
                        "worker_quality": worker_problem,
                    }, ensure_ascii=False) + "\n")
                    if live_target is not None:
                        live_status = "REDDEDILDI" if worker_problem else "URETILDI"
                        live_target.write("\t".join(live_field(value) for value in (
                            # Canlı kullanıcı günlüğü yerel duvar saatini kullanır.
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],  # noqa: DTZ005
                            "OTOMATIK_GPU", item["key"], unit["category"], live_status,
                            item["english"], translation, worker_problem,
                        )) + "\n")
                    completed += 1
                target.flush()
                if live_target is not None:
                    live_target.flush()
            elapsed = max(time.time() - started, 0.001)
            rate = completed / elapsed
            remaining = int((len(items) - completed) / rate) if rate else 0
            emit(f"PROGRESS|{completed}|{len(items)}|{rate:.1f}|{remaining}")

    if live_target is not None:
        live_target.close()
    emit(f"DONE|{completed}|{time.time() - started:.1f}")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)

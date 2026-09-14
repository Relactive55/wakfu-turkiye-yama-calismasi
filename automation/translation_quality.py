"""Small, fail-closed checks for machine-translation quality.

The localization pipeline already validates placeholders and markup.  That is
necessary, but it cannot catch a candidate such as ``"Harvest ... on ada"``:
the syntax is valid while the sentence is visibly only half translated.  This
module deliberately checks only high-confidence signals so a proper game name
is not rejected merely because it is kept in English.
"""
from __future__ import annotations

from collections import Counter
import re
import unicodedata


# Ordinary format atoms are hidden while the natural-language portion is
# inspected.  Conditional *branch text* is intentionally not opaque: it is
# player-visible prose and must go through the same English-residue gate.
_FORMAT_ATOM = re.compile(
    r"\\[ntr]|<[^>]*>|"
    r"\[(?:[#$=,<>/-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|"
    r"%[A-Za-z_][A-Za-z0-9_.-]*%"
)
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)


# These are unambiguous English UI/action words in this project.  A generic
# word is checked regardless of capitalization, because Argos commonly emits
# title-case fragments (for example ``"Invalid hücresi"``).
ENGLISH_RESIDUE_WORDS = frozenset(
    {
        "age",
        "archmonster",
        "active",
        "ascending",
        "available",
        "bridge",
        "building",
        "cap",
        "cell",
        "center",
        "celestial",
        "crate",
        "damage",
        "dead",
        "descending",
        "disabled",
        "enabled",
        "entity",
        "environmental",
        "extreme",
        "family",
        "harvest",
        "inflicted",
        "interact",
        "invalid",
        "island",
        "ivory",
        "least",
        "limit",
        "living",
        "max",
        "maximum",
        "minimum",
        "monster",
        "most",
        "newest",
        "no",
        "oldest",
        "occupied",
        "paddock",
        "peddock",
        "place",
        "poster",
        "prairie",
        "prairies",
        "quarter",
        "quartermaster",
        "quest",
        "ranching",
        "reconstruction",
        "removal",
        "rewards",
        "score",
        "season",
        "sector",
        "starfish",
        "stool",
        "yes",
        "vomit",
    }
)

# A one-word technical value is not a translation failure by itself.  ``FPS``
# is deliberately allowed; it is a standard game setting label and can be
# wrapped in a WAKFU conditional marker.
ALLOWED_TECHNICAL_WORDS = frozenset({"fps"})
_COMMON_TURKISH_WORDS = frozenset(
    {
        "ama",
        "bu",
        "da",
        "de",
        "için",
        "ile",
        "mi",
        "mı",
        "mu",
        "mü",
        "ve",
        "bir",
        "şu",
    }
)


def _visible(text: str) -> str:
    """Remove syntax while retaining words inside conditional branches."""
    visible: list[str] = []
    conditional_stack: list[bool] = []
    index = 0
    while index < len(text):
        if text.startswith("{[", index):
            header_end = text.find("]?", index + 2)
            if header_end >= 0:
                visible.append(" ")
                conditional_stack.append(False)
                index = header_end + 2
                continue
        char = text[index]
        if conditional_stack and char == ":" and (index == 0 or text[index - 1] != "\\"):
            # The first unescaped colon owned by the current conditional is
            # syntax; later colons in its branch remain ordinary prose.
            if not conditional_stack[-1]:
                conditional_stack[-1] = True
                visible.append(" ")
                index += 1
                continue
        if conditional_stack and char == "}":
            conditional_stack.pop()
            visible.append(" ")
            index += 1
            continue
        atom = _FORMAT_ATOM.match(text, index)
        if atom:
            visible.append(" ")
            index = atom.end()
            continue
        visible.append(char)
        index += 1
    return unicodedata.normalize("NFKC", "".join(visible)).replace("’", "'")


def _words(text: str) -> list[str]:
    return [match.group(0).casefold() for match in _WORD.finditer(_visible(text))]


def _normal_form(text: str) -> str:
    return " ".join(_words(text))


def quality_problem(key: str, source: str, target: str) -> str | None:
    """Return a concise reason when a candidate is clearly low quality.

    This is intentionally a high-confidence gate, not a claim that a machine
    translation is stylistically perfect.  Human/manual entries remain
    trusted by the caller; automatic and remembered candidates pass through
    this check before they can enter a release PR.
    """
    source_words = _words(source)
    target_words = _words(target)
    if not target_words:
        return "çeviri boş"

    target_counts = Counter(target_words)
    source_counts = Counter(source_words)
    for word, count in target_counts.items():
        # Four consecutive/repeated copies are a strong machine-translation
        # symptom (for example ``Extreme Extreme Extreme Extreme``).  Three
        # occurrences are common in natural Turkish dialogue.
        if word not in _COMMON_TURKISH_WORDS and count >= 4 and count > source_counts.get(word, 0):
            return f"aynı kelime gereğinden fazla tekrarlandı: {word}"

    source_visible = _visible(source).casefold()
    target_visible = _visible(target).casefold()

    # A direct copy of a multi-word English sentence is never a useful new
    # translation.  One-word proper names and technical labels are excluded.
    if _normal_form(source) == _normal_form(target) and len(source_words) >= 2:
        if not (len(source_words) == 1 and source_words[0] in ALLOWED_TECHNICAL_WORDS):
            return "kaynak metin aynen kaldı"

    for word in target_words:
        if word in ENGLISH_RESIDUE_WORDS:
            return f"İngilizce kalıntı bulundu: {word}"

    # These are recurring, high-confidence mistranslation patterns that a
    # simple word list cannot distinguish from a legitimate Turkish word.
    if "stool" in source_visible and "tabur" in target_words:
        return "stool sözcüğü 'tabur' olarak hatalı çevrilmiş"
    if "ranched" in source_visible and "çalıştır" in target_visible:
        return "ranched sözcüğü 'çalıştır' olarak hatalı çevrilmiş"
    if "haven place" in source_visible and "haven place" in target_visible:
        return "Haven Place ifadesi çevrilmeden bırakılmış"

    return None

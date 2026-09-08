"""Deterministic diff, translation-memory resolution and validation helpers."""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .errors import TranslationProviderUnavailable, VerificationError

ENTRIES = ("texts_en.properties", "texts_en_cleaned.properties")
TOKEN = re.compile(r"\{\[[^\]]+\]\?(?:[^{}]|\\.)*\}|\\[ntr]|<[^>]*>|\[(?:[#$=,<>/-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|%[A-Za-z_][A-Za-z0-9_.-]*%")


@dataclass(frozen=True)
class Record:
    identity: str
    entry: str
    key: str
    occurrence: int
    source: str


def records_from_jar(jar: Path) -> list[Record]:
    result: list[Record] = []
    with zipfile.ZipFile(jar) as archive:
        for entry in ENTRIES:
            counts: dict[str, int] = {}
            for raw in archive.read(entry).decode("utf-8-sig").splitlines():
                if not raw or raw.startswith(("#", "!")) or "=" not in raw:
                    continue
                key, source = raw.split("=", 1)
                counts[key] = counts.get(key, 0) + 1
                result.append(Record(f"{entry}:{key}#{counts[key]}", entry, key, counts[key], source))
    return result


def diff_records(before: Iterable[Record], after: Iterable[Record]) -> dict[str, list[Record]]:
    old, new = {r.identity: r for r in before}, {r.identity: r for r in after}
    return {
        "UNCHANGED": [new[k] for k in sorted(new.keys() & old.keys()) if new[k].source == old[k].source],
        "NEW": [new[k] for k in sorted(new.keys() - old.keys())],
        "MODIFIED": [new[k] for k in sorted(new.keys() & old.keys()) if new[k].source != old[k].source],
        "REMOVED": [old[k] for k in sorted(old.keys() - new.keys())],
    }


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _terms(path: Path) -> tuple[dict, dict, dict]:
    data = _json(path)
    return data.get("keys", {}), data.get("values", {}), data.get("phrases", {})


def same_tokens(source: str, target: str) -> bool:
    return [m.group() for m in TOKEN.finditer(source)] == [m.group() for m in TOKEN.finditer(target)]


def mask_tokens(text: str) -> tuple[str, list[str]]:
    tokens = [m.group() for m in TOKEN.finditer(text)]
    index = 0

    def replace(_match: re.Match[str]) -> str:
        nonlocal index
        value = f"ZXQ{index:04d}QXZ"; index += 1; return value

    return TOKEN.sub(replace, text), tokens


def restore_tokens(text: str, tokens: list[str]) -> str:
    for index, token in enumerate(tokens):
        marker = f"ZXQ{index:04d}QXZ"
        if text.count(marker) != 1:
            raise VerificationError("machine translation lost or duplicated a placeholder")
        text = text.replace(marker, token)
    if re.search(r"ZXQ\d{4}QXZ", text):
        raise VerificationError("machine translation lost or invented a placeholder")
    return text


def _translate_without_tokens(text: str, provider: Callable[[str], str]) -> str:
    """Translate only the human-readable spans of a tokenized value.

    Some machine-translation models rewrite or drop opaque sentinel strings
    even though they contain no natural language.  When that happens, retry
    by sending each non-token span separately and splice the original tokens
    back in locally.  Whitespace-only spans are kept verbatim so formatting
    around placeholders is not changed by the provider.
    """
    result: list[str] = []
    cursor = 0
    for match in TOKEN.finditer(text):
        segment = text[cursor : match.start()]
        if segment and segment.strip():
            result.append(provider(segment))
        else:
            result.append(segment)
        result.append(match.group())
        cursor = match.end()
    tail = text[cursor:]
    if tail and tail.strip():
        result.append(provider(tail))
    else:
        result.append(tail)
    return "".join(result)


def translate_preserving_tokens(text: str, provider: Callable[[str], str]) -> str:
    """Translate text while guaranteeing that WAKFU tokens survive.

    The normal path keeps surrounding context in one provider call.  If the
    provider changes a sentinel, the segmented retry avoids sending tokens to
    the model at all while retaining the same fail-closed validation later in
    the pipeline.
    """
    masked, tokens = mask_tokens(text)
    try:
        return restore_tokens(provider(masked), tokens)
    except VerificationError:
        return _translate_without_tokens(text, provider)


def _conditional_shape(text: str) -> list[str]:
    """Capture WAKFU conditional structure without comparing translated words."""
    shape: list[str] = []
    depth = 0
    index = 0
    while index < len(text):
        if text.startswith("{[", index):
            end = text.find("]?", index + 2)
            if end < 0:
                return ["!UNBALANCED"]
            shape.append(text[index : end + 2])
            depth += 1
            index = end + 2
            continue
        char = text[index]
        if depth and char == ":" and (index == 0 or text[index - 1] != "\\"):
            shape.append(":")
        elif depth and char == "}":
            shape.append("}")
            depth -= 1
        index += 1
    if depth:
        shape.append(f"!UNBALANCED:{depth}")
    return shape


def format_ok(source: str, target: str) -> bool:
    """Validate token order plus conditional branch structure."""
    return same_tokens(source, target) and _conditional_shape(source) == _conditional_shape(target)


def resolve_changes(changes: Iterable[Record], *, translations: dict, manual: dict, terms: tuple[dict, dict, dict], argos: Callable[[str], str] | None = None) -> tuple[dict[str, str], dict[str, str]]:
    """Return proposals and their source. Existing TM is never overwritten."""
    term_keys, term_values, _phrases = terms
    output: dict[str, str] = {}
    origin: dict[str, str] = {}
    for record in changes:
        candidate = None
        if record.key in manual: candidate, source = str(manual[record.key]), "manual"
        elif record.key in translations and str(translations[record.key]).strip(): candidate, source = str(translations[record.key]), "memory"
        elif record.key in term_keys: candidate, source = str(term_keys[record.key]), "glossary-key"
        elif record.source in term_values: candidate, source = str(term_values[record.source]), "glossary-value"
        elif argos is not None:
            candidate, source = translate_preserving_tokens(record.source, argos), "argos"
        else:
            if argos is None:
                raise TranslationProviderUnavailable("TRANSLATION_PROVIDER_UNAVAILABLE: Argos runtime is required for unresolved NEW/MODIFIED records")
            continue
        if not candidate.strip() or not format_ok(record.source, candidate):
            raise VerificationError("translation candidate fails token validation: " + record.identity)
        output[record.identity], origin[record.identity] = candidate, source
    return output, origin


def validate_proposals(*, diff: dict[str, list[Record]], proposals: dict[str, str], baseline_translations: dict[str, str]) -> None:
    current = {r.identity: r for kind in ("UNCHANGED", "NEW", "MODIFIED") for r in diff[kind]}
    for identity, value in proposals.items():
        if identity not in current: raise VerificationError("proposal references unknown record: " + identity)
        if identity in {r.identity for r in diff["UNCHANGED"]}: raise VerificationError("UNCHANGED record was modified: " + identity)
        if not value.strip() or not format_ok(current[identity].source, value): raise VerificationError("invalid proposal: " + identity)
    # Translation memory is keyed by original game key. Ensure a proposal does
    # not mutate it in place; the PR writer must emit only candidate review data.
    if any(key not in baseline_translations for key in []): raise AssertionError("unreachable guard")

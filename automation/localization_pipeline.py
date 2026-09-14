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
from .translation_quality import quality_problem

ENTRIES = ("texts_en.properties", "texts_en_cleaned.properties")
# TOKEN protects ordinary format atoms whenever text is sent through Argos.
# ``mask_tokens`` keeps its historical whole-conditional behavior for callers
# that need a raw token snapshot; ``translate_preserving_tokens`` now parses
# conditionals separately so their visible branch words are translated while
# the control syntax stays local.  Validation below uses a recursive
# structural tokenizer, so translated branch prose is not compared byte-for-
# byte with the English source.
TOKEN = re.compile(r"\{\[[^\]]+\]\?(?:[^{}]|\\.)*\}|\\[ntr]|<[^>]*>|\[(?:[#$=,<>/-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|%[A-Za-z_][A-Za-z0-9_.-]*%")
_ORDINARY_TOKEN = re.compile(
    r"\\[ntr]|<(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>|"
    r"\[(?:[#$=,<>/-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|"
    r"%[A-Za-z_][A-Za-z0-9_.-]*%"
)
_SIMPLE_CONDITIONAL = re.compile(r"\{\[[^\]]+\]\?(?:s|es)?:\}")
_CONDITIONAL_MARKER = re.compile(r"\{\[[^\]]+\]\?(?:[^{}]|\\.)*\}")
_CONDITIONAL_HEADER = re.compile(r"\{\[[^\]]+\]\?")


@dataclass(frozen=True)
class Record:
    identity: str
    entry: str
    key: str
    occurrence: int
    source: str


def source_fingerprint(source: str) -> str:
    """Return the stable source-text fingerprint used by translation memory."""
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def memory_source_matches(record: Record, memory_sources: dict[str, str] | None) -> bool:
    """Require a source hash before a remembered translation can be reused.

    The project translation file intentionally stays a compact key-to-value
    map.  Its companion source map records which exact English text was
    reviewed for each key.  Missing metadata is treated as untrusted legacy
    memory and must go through Argos or manual review again.
    """
    if not isinstance(memory_sources, dict):
        return False
    recorded = memory_sources.get(record.key)
    if not isinstance(recorded, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", recorded):
        return False
    return recorded.casefold() == source_fingerprint(record.source)


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


def _legacy_format_signature(text: str) -> tuple:
    """Keep compatibility with legacy conditionals without a false branch.

    A few shipped strings use ``{[condition]?}`` (or contain an already
    malformed historical header).  They cannot be represented by the normal
    two-branch tree, but rejecting an unchanged reviewed value would make the
    builder silently drop existing translations.  The fallback compares the
    available headers, atoms and punctuation shape conservatively; all
    well-formed conditionals still use the branch-aware parser below.
    """
    headers = tuple(match.group(0).casefold() for match in _CONDITIONAL_HEADER.finditer(text))
    stripped = _CONDITIONAL_HEADER.sub(" ", text)
    ordinary = tuple(match.group(0).casefold() for match in _ORDINARY_TOKEN.finditer(stripped))
    punctuation = tuple(char for char in stripped if char in "{}?:")
    return ("legacy", headers, ordinary, punctuation, text.count("{"), text.count("}"))


def _format_signature(text: str) -> tuple | None:
    """Return a nested syntax signature while ignoring translated prose.

    A conditional is not an opaque token: placeholders and markup in its two
    branches belong to different runtime paths.  A flat token list therefore
    accepted an unsafe translation that moved a placeholder from the true
    branch to the false branch.  The recursive parser below keeps each branch
    as its own tuple and compares only control syntax, not ordinary words.
    """

    def segment(index: int, stops: set[str]):
        nodes: list[tuple] = []
        while index < len(text):
            if text.startswith("{[", index):
                conditional, index = parse_conditional(index)
                if conditional is None:
                    return None, index, None
                nodes.append(conditional)
                continue
            char = text[index]
            if char in stops and (char != ":" or index == 0 or text[index - 1] != "\\"):
                return tuple(nodes), index, char
            match = _ORDINARY_TOKEN.match(text, index)
            if match:
                # The cleaned upstream properties entry is lower-cased.  The
                # builder restores source spelling after validation, so token
                # identity is intentionally case-insensitive here.
                nodes.append(("atom", match.group(0).casefold()))
                index = match.end()
                continue
            index += 1
        return tuple(nodes), index, None

    def parse_conditional(start: int):
        header_end = text.find("]?", start + 2)
        if header_end < 0:
            return None, start
        first, separator, delimiter = segment(header_end + 2, {":", "}"})
        if first is None or delimiter != ":":
            return None, start
        second, close, delimiter = segment(separator + 1, {"}"})
        if second is None or delimiter != "}":
            return None, start
        header = text[start : header_end + 2].casefold()
        return ("conditional", header, first, second), close + 1

    signature, end, delimiter = segment(0, set())
    if signature is None or delimiter is not None or end != len(text):
        return _legacy_format_signature(text)
    return signature


def _repair_simple_conditional_boundaries(source: str, candidate: str) -> str:
    """Carry newly-added, suffix/prefix-only count markers into old TM text.

    Existing reviewed translations can predate a source-only marker such as
    ``Lucky Charm{[~1]?s:}``.  It is safe to graft these simple markers only at
    an unambiguous string boundary; conditional branches containing words are
    intentionally left for human review instead of being guessed.
    """
    result = candidate
    for marker in _SIMPLE_CONDITIONAL.findall(source):
        header = marker.split("?", 1)[0] + "?"
        trimmed_result = result.rstrip()
        has_same_suffix_header = any(
            match.group().startswith(header) and match.end() == len(trimmed_result)
            for match in _CONDITIONAL_MARKER.finditer(trimmed_result)
        )
        has_same_prefix_header = any(
            match.group().startswith(header) and match.start() == len(result) - len(result.lstrip())
            for match in _CONDITIONAL_MARKER.finditer(result)
        )
        if source.rstrip().endswith(marker) and not result.rstrip().endswith(marker):
            if not has_same_suffix_header:
                trailing = result[len(result.rstrip()):]
                result = result.rstrip() + marker + trailing
        elif source.lstrip().startswith(marker) and not result.lstrip().startswith(marker):
            if not has_same_prefix_header:
                leading = result[: len(result) - len(result.lstrip())]
                result = leading + marker + result.lstrip()
    return result


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


def _conditional_bounds(text: str, start: int) -> tuple[int, int, int] | None:
    """Return ``(header_end, separator, close)`` for a WAKFU conditional.

    The first colon and closing brace owned by the outer conditional delimit
    its two branches.  Nested conditionals are skipped as a unit, while an
    escaped punctuation character remains ordinary branch prose.
    """
    if not text.startswith("{[", start):
        return None
    header_end = text.find("]?", start + 2)
    if header_end < 0:
        return None
    index = header_end + 2
    depth = 1
    separator = -1
    while index < len(text):
        if text.startswith("{[", index):
            nested_header_end = text.find("]?", index + 2)
            if nested_header_end < 0:
                return None
            depth += 1
            index = nested_header_end + 2
            continue
        char = text[index]
        if char == "\\":
            # A backslash protects the following character from being treated
            # as a branch delimiter or a conditional close.
            index += 2
            continue
        if char == ":" and depth == 1 and separator < 0:
            separator = index
        elif char == "}":
            depth -= 1
            if depth == 0:
                return (header_end + 2, separator, index) if separator >= 0 else None
        index += 1
    return None


def _translate_plain_preserving_tokens(text: str, provider: Callable[[str], str]) -> str:
    """Translate a non-conditional span while keeping markup/placeholders."""
    if not text or not text.strip():
        return text
    # Avoid asking Argos to translate a span made solely of technical atoms.
    if not _ORDINARY_TOKEN.sub("", text).strip():
        return text
    masked, tokens = mask_tokens(text)
    try:
        return restore_tokens(provider(masked), tokens)
    except VerificationError:
        return _translate_without_tokens(text, provider)


def _translate_conditionals(text: str, provider: Callable[[str], str]) -> str:
    """Translate visible prose in and around conditionals recursively.

    Conditional headers, separators, braces and ordinary format atoms stay in
    the local process.  Only the natural-language spans are sent to Argos, so
    a branch such as ``{[=1]?damage:damage}`` can be translated without giving
    the provider an opportunity to rewrite the runtime syntax.
    """
    pieces: list[str] = []
    cursor = 0
    index = 0
    found = False
    while index < len(text):
        if text.startswith("{[", index):
            bounds = _conditional_bounds(text, index)
            if bounds is None:
                index += 2
                continue
            found = True
            header_end, separator, close = bounds
            pieces.append(_translate_plain_preserving_tokens(text[cursor:index], provider))
            pieces.append(text[index:header_end])
            pieces.append(_translate_conditionals(text[header_end:separator], provider))
            pieces.append(":")
            pieces.append(_translate_conditionals(text[separator + 1:close], provider))
            pieces.append("}")
            cursor = close + 1
            index = cursor
            continue
        index += 1
    if not found:
        return _translate_plain_preserving_tokens(text, provider)
    pieces.append(_translate_plain_preserving_tokens(text[cursor:], provider))
    return "".join(pieces)


def translate_preserving_tokens(text: str, provider: Callable[[str], str]) -> str:
    """Translate text while guaranteeing that WAKFU tokens survive.

    Ordinary text keeps surrounding context in one provider call.  Conditional
    branches are split recursively so their player-visible words are also
    translated; only their technical structure is kept opaque.  If a provider
    changes a sentinel, the segmented retry avoids sending tokens to the model
    at all while retaining the same fail-closed validation later in the
    pipeline.
    """
    return _translate_conditionals(text, provider) if "{[" in text else _translate_plain_preserving_tokens(text, provider)


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
    """Validate syntax atoms while allowing conditional text to translate."""
    source_signature = _format_signature(source)
    target_signature = _format_signature(target)
    return source_signature == target_signature


def resolve_changes(
    changes: Iterable[Record],
    *,
    translations: dict,
    manual: dict,
    terms: tuple[dict, dict, dict],
    argos: Callable[[str], str] | None = None,
    memory_sources: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return proposals and their source.

    Key-only memory is deliberately not trusted: a game update can reuse a
    key for a completely different English sentence.  A remembered value is
    eligible only when its companion source hash matches the current record.
    """
    term_keys, term_values, _phrases = terms
    output: dict[str, str] = {}
    origin: dict[str, str] = {}
    for record in changes:
        candidate = None
        if record.key in manual: candidate, source = str(manual[record.key]), "manual"
        elif (
            record.key in translations
            and str(translations[record.key]).strip()
            and memory_source_matches(record, memory_sources)
        ):
            candidate, source = str(translations[record.key]), "memory"
        elif record.key in term_keys: candidate, source = str(term_keys[record.key]), "glossary-key"
        elif record.source in term_values: candidate, source = str(term_values[record.source]), "glossary-value"
        elif argos is not None:
            candidate, source = translate_preserving_tokens(record.source, argos), "argos"
        else:
            if argos is None:
                raise TranslationProviderUnavailable("TRANSLATION_PROVIDER_UNAVAILABLE: Argos runtime is required for unresolved NEW/MODIFIED records")
            continue
        if source != "argos":
            candidate = _repair_simple_conditional_boundaries(record.source, candidate)
        if not candidate.strip() or not format_ok(record.source, candidate):
            raise VerificationError("translation candidate fails token validation: " + record.identity)
        # Manual repairs are reviewed source-of-truth entries.  Every other
        # provider (Argos, memory, or glossary) must also pass a semantic
        # smoke-test so half-English output cannot reach a release PR.
        if source != "manual":
            problem = quality_problem(record.key, record.source, candidate)
            if problem:
                raise VerificationError(
                    f"translation quality guard: {record.identity}: {problem}"
                )
        output[record.identity], origin[record.identity] = candidate, source
    return output, origin


def validate_proposals(*, diff: dict[str, list[Record]], proposals: dict[str, str], baseline_translations: dict[str, str]) -> None:
    baseline_before = dict(baseline_translations)
    current = {r.identity: r for kind in ("UNCHANGED", "NEW", "MODIFIED") for r in diff[kind]}
    for identity, value in proposals.items():
        if identity not in current: raise VerificationError("proposal references unknown record: " + identity)
        if identity in {r.identity for r in diff["UNCHANGED"]}: raise VerificationError("UNCHANGED record was modified: " + identity)
        if not value.strip() or not format_ok(current[identity].source, value): raise VerificationError("invalid proposal: " + identity)
    # Translation memory is supplied as an immutable baseline snapshot.  Keep
    # this invariant explicit so future validators cannot silently mutate the
    # caller's dictionary while checking proposals.
    if baseline_translations != baseline_before:
        raise AssertionError("baseline translation snapshot was mutated")

import argparse
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

from wakfu_audit import (
    EXPLICIT_PROTECTED_WORLD_LABELS,
    MANUAL_PROTECTED_TRANSLATION_KEYS,
    REVIEWED_TRANSLATABLE_NAME_KEYS,
    VISIBLE_WORLD_LABEL_PREFIXES,
    category,
    format_ok,
    is_protected_key,
)


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def align_markup(source, candidate):
    """Restore the exact source tag spelling while keeping translated text."""
    # Do not let a malformed source fragment such as ``</b\"text <b>``
    # swallow visible text as if it were one markup tag.  Quoted attributes
    # remain supported, but quotes and nested ``<`` characters must balance.
    tag_re = re.compile(r"<(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>")
    source_tags = list(tag_re.finditer(source))
    candidate_tags = list(tag_re.finditer(candidate))
    if len(source_tags) != len(candidate_tags):
        return candidate

    def tag_name(value):
        match = re.match(r"<\s*(/?)\s*([A-Za-z0-9]+)", value)
        return (match.group(1), match.group(2).casefold()) if match else None

    if any(tag_name(a.group()) != tag_name(b.group()) for a, b in zip(source_tags, candidate_tags)):
        return candidate
    pieces = list(candidate)
    for source_tag, candidate_tag in reversed(list(zip(source_tags, candidate_tags))):
        pieces[candidate_tag.start():candidate_tag.end()] = source_tag.group()
    candidate = "".join(pieces)

    bracket_re = re.compile(
        r"\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]"
    )
    source_tokens = list(bracket_re.finditer(source))
    candidate_tokens = list(bracket_re.finditer(candidate))
    if len(source_tokens) != len(candidate_tokens):
        return candidate
    if any(a.group().casefold() != b.group().casefold() for a, b in zip(source_tokens, candidate_tokens)):
        return candidate
    pieces = list(candidate)
    for source_token, candidate_token in reversed(list(zip(source_tokens, candidate_tokens))):
        pieces[candidate_token.start():candidate_token.end()] = source_token.group()
    return "".join(pieces)


def apply_phrase_rules(value, phrases):
    for old, new in phrases:
        pattern = r"(?<![\w])" + re.escape(old) + r"(?![\w])"
        value = re.sub(pattern, lambda _match, replacement=new: replacement, value)
    return value


def rewrite_properties(data, translations, term_keys, term_values, phrases, manual, protected_values, skipped_rows):
    text = data.decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    translated = protected = skipped = 0
    output = []

    for line in lines:
        if not line or line.startswith(("#", "!")) or "=" not in line:
            output.append(line)
            continue
        key, source = line.split("=", 1)
        protected_value = source.strip() in protected_values
        if protected_value and category(key) == "ARAYUZ":
            protected_value = len(source.strip()) >= 10 or len(source.split()) >= 2
        letters = len(re.findall(r"[^\W\d_]", source, re.UNICODE))
        # Değişken ağırlıklı kısa arayüz cümleleri (ör. "[#1] is KO'd!")
        # az harf içerir ama çevrilebilir metindir. Yalnız gerçekten harfsiz ya
        # da tek karakterlik teknik dizileri kod olarak koru.
        symbol_heavy_gibberish = (
            len(source) >= 12
            and letters <= 6
            and not re.search(r"[A-Za-z]{2,}", source)
        )
        # Büyü/yetenek, savaş içi durum ve eşya başlıklarında manuel bellek
        # dâhil hiçbir katman özgün İngilizce adın üzerine yazamaz. Sınıf
        # tanıtımındaki Gameplay sekmeleri bunun arayüz istisnasıdır.
        if (
            (
                key.startswith(("content.3.", "content.8.", "content.15."))
                and key not in REVIEWED_TRANSLATABLE_NAME_KEYS
            )
            or key == "content.6.1049"
        ):
            protected += 1
            output.append(line)
            continue
        # Zorunlu İngilizce beceri/eşya adları dışında insan onaylı anahtar ve
        # kaynak-değer terimleri üstün gelir. Kaynak-değer kuralı, JAR içinde
        # aynı anahtarın farklı dünya haritası metinleriyle tekrarlandığı
        # durumlarda anahtar bazlı belleğin yanlış kopyayı ezmesini önler.
        allow_intrinsic_override = (
            key in manual
            or key in term_keys
            or (
                key in MANUAL_PROTECTED_TRANSLATION_KEYS
                and (key in manual or key in term_keys or key in translations)
            )
        )
        source_term_forced = (
            source in term_values
            and key.startswith(VISIBLE_WORLD_LABEL_PREFIXES)
        )
        allow_value_override = key in manual or key in term_keys or source_term_forced
        if (
            (is_protected_key(key) and not allow_intrinsic_override)
            or (protected_value and not allow_value_override)
            or symbol_heavy_gibberish
        ):
            protected += 1
            output.append(line)
            continue

        candidate = None
        apply_phrases = True
        if key in term_keys:
            candidate = str(term_keys[key])
            apply_phrases = False
        elif source_term_forced:
            candidate = str(term_values[source])
            apply_phrases = False
        elif key in manual:
            candidate = str(manual[key])
            apply_phrases = False
        elif source in term_values:
            candidate = str(term_values[source])
            apply_phrases = False
        elif key in translations and str(translations[key]).strip():
            candidate = str(translations[key])

        if candidate is None:
            output.append(line)
            continue
        if apply_phrases:
            candidate = apply_phrase_rules(candidate, phrases)
        candidate = align_markup(source, candidate)
        if not format_ok(source, candidate):
            skipped += 1
            skipped_rows.setdefault(key, (source, candidate))
            output.append(line)
            continue
        candidate = candidate.replace("\r\n", "\\n").replace("\n", "\\n")
        output.append(f"{key}={candidate}")
        translated += 1

    return (newline.join(output) + (newline if text.endswith(("\n", "\r")) else "")).encode("utf-8"), translated, protected, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-jar", required=True)
    parser.add_argument("--output-jar", "--output", dest="output_jar", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--terminology", required=True)
    parser.add_argument("--manual-repairs", "--manual", dest="manual_repairs", required=True)
    args = parser.parse_args()

    source = Path(args.source_jar)
    output = Path(args.output_jar)
    translations = load_json(args.project)
    terminology = load_json(args.terminology)
    manual = load_json(args.manual_repairs)
    term_keys = {str(k): str(v) for k, v in terminology.get("keys", {}).items()}
    term_values = {str(k): str(v) for k, v in terminology.get("values", {}).items()}
    phrases = sorted(
        ((str(k), str(v)) for k, v in terminology.get("phrases", {}).items()),
        key=lambda pair: len(pair[0]),
        reverse=True,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=output.stem + ".", suffix=".tmp", dir=output.parent)
    os.close(fd)
    totals = [0, 0, 0]
    skipped_rows = {}
    try:
        with zipfile.ZipFile(source, "r") as src:
            source_name = "texts_en.properties" if "texts_en.properties" in src.namelist() else "texts_en_cleaned.properties"
            protected_values = set()
            for line in src.read(source_name).decode("utf-8-sig").splitlines():
                if not line or line.startswith(("#", "!")) or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if is_protected_key(key) and value.strip():
                    protected_values.add(value.strip())
            protected_values.update(EXPLICIT_PROTECTED_WORLD_LABELS)

        with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(temp_name, "w") as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename in {"texts_en.properties", "texts_en_cleaned.properties"}:
                    data, translated, protected, skipped = rewrite_properties(
                        data, translations, term_keys, term_values, phrases, manual, protected_values, skipped_rows
                    )
                    totals[0] += translated
                    totals[1] += protected
                    totals[2] += skipped
                dst.writestr(info, data)
        os.replace(temp_name, output)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise

    report = output.with_suffix(".skipped.tsv")
    with report.open("w", encoding="utf-8-sig", newline="\n") as handle:
        handle.write("Anahtar\tIngilizce\tTurkce\n")
        for key, (english, turkish) in skipped_rows.items():
            clean = lambda value: str(value).replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")
            handle.write(f"{clean(key)}\t{clean(english)}\t{clean(turkish)}\n")
    print(f"BUILD_OK|{output}|TRANSLATED={totals[0]}|PROTECTED={totals[1]}|SKIPPED={totals[2]}|REPORT={report}")


if __name__ == "__main__":
    main()

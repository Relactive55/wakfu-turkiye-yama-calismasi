import argparse
import csv
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path

TOKEN_RE = re.compile(
    r"\{\[[^\]]+\]\?(?:s|es)?:\}|\\[ntr]|"
    r"\[(?:[#$=,<>-][^\]]*|\d+[A-Za-z0-9*!<>=.$-]*|[A-Za-z][A-Za-z0-9_.-]{0,31})\]|"
    r"<(?:[^<>\"']|\"[^\"]*\"|'[^']*')*>|%[A-Za-z_][A-Za-z0-9_.-]*%"
)


def tokens(text):
    text = text or ""
    values = []

    def walk(start, stop):
        index = start
        while index < stop:
            if text.startswith("{[", index):
                condition_end = text.find("]?", index + 2, stop)
                if condition_end >= 0:
                    body_start = condition_end + 2; depth = 0; separator = None; cursor = body_start; close = None
                    while cursor < stop:
                        if text.startswith("{[", cursor): depth += 1; cursor += 2; continue
                        if text[cursor] == "}":
                            if depth: depth -= 1; cursor += 1; continue
                            close = cursor; break
                        if text[cursor] == ":" and depth == 0 and (cursor == 0 or text[cursor - 1] != "\\") and separator is None:
                            separator = cursor
                        cursor += 1
                    if close is not None and separator is not None:
                        values.append(text[index:body_start]); walk(body_start, separator)
                        values.append(":"); walk(separator + 1, close); values.append("}")
                        index = close + 1; continue
            match = TOKEN_RE.match(text, index)
            if match:
                values.append(match.group(0)); index = match.end(); continue
            index += 1

    walk(0, len(text))
    return values


def atomic_json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.stem + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--issues", required=True)
    args = parser.parse_args()

    latest = {}
    counters = Counter()
    # Eski surumlerden kalan tek bir ham satir sonu csv.DictReader'in sonraki
    # binlerce saglam kaydi tek hucre saymasina yol acabiliyor. Canli gunlukte
    # her yeni kayit zaman damgasi ve sekiz TSV alaniyla baslar; fiziksel
    # satirlari bagimsiz okuyarak bozuk devam satirlarini guvenle atla.
    def decode_live(value):
        # Günlükte oyunun gerçek satır/sekme karakterleri tek kaçışla, kaynakta
        # zaten bulunan ``\\n`` gibi yazılı kodlar ise çift ters eğik çizgiyle
        # saklanır. Önce çiftleri güvenli bir işarete alıp yalnız tek kaçışları
        # gerçek karaktere dönüştürmek iki durumu birbirine karıştırmaz.
        marker = "\0WAKFU_BACKSLASH\0"
        value = (value or "").replace("\\\\", marker)
        value = value.replace("\\t", "\t").replace("\\r", "\r").replace("\\n", "\n")
        return value.replace(marker, "\\")

    with open(args.live, "r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for row_number, raw_line in enumerate(handle, 1):
            if row_number == 1 and raw_line.startswith("Zaman\t"):
                continue
            fields = raw_line.rstrip("\r\n").split("\t", 7)
            if len(fields) != 8 or not re.match(r"^\d{4}-\d{2}-\d{2} ", fields[0]):
                counters["malformed_physical_line"] += 1
                continue
            row = dict(zip(
                ("Zaman", "Yontem", "Anahtar", "Kategori", "Durum", "Ingilizce", "Turkce", "Aciklama"),
                (decode_live(value) for value in fields),
            ))
            counters["rows"] += 1
            key = (row.get("Anahtar") or "").strip()
            source = row.get("Ingilizce") or ""
            target = row.get("Turkce") or ""
            status = (row.get("Durum") or "").strip().upper()
            method = (row.get("Yontem") or "").strip().upper()
            if not key:
                counters["missing_key"] += 1
                continue
            if status in {"SILINDI", "REDDEDILDI", "HATA"}:
                if status == "SILINDI":
                    latest.pop(key, None)
                counters[status.lower()] += 1
                continue
            if not target.strip():
                counters["empty"] += 1
                continue
            if status not in {"URETILDI", "KAYDEDILDI", "DUZELTILDI"}:
                counters["unknown_status"] += 1
                continue
            latest[key] = {
                "source": source,
                "target": target,
                "status": status,
                "method": method,
                "row": row_number,
                "time": row.get("Zaman") or "",
            }

    recovered = {}
    issues = []
    for key, item in latest.items():
        source = item["source"]
        target = item["target"]
        source_tokens = tokens(source)
        target_tokens = tokens(target)
        if source_tokens != target_tokens:
            counters["format_mismatch"] += 1
            issues.append({
                "Anahtar": key,
                "Ingilizce": source,
                "Turkce": target,
                "Sorun": "BICIM_KODU_UYUSMUYOR",
                "KaynakKodlari": " | ".join(source_tokens),
                "CeviriKodlari": " | ".join(target_tokens),
                "Yontem": item["method"],
                "Zaman": item["time"],
            })
            continue
        if re.search(r"(?:ZXQ|XQ)\d{4}QXZ|__WAKFU_", target):
            counters["placeholder_leak"] += 1
            issues.append({
                "Anahtar": key,
                "Ingilizce": source,
                "Turkce": target,
                "Sorun": "MODEL_YER_TUTUCUSU_KALDI",
                "KaynakKodlari": " | ".join(source_tokens),
                "CeviriKodlari": " | ".join(target_tokens),
                "Yontem": item["method"],
                "Zaman": item["time"],
            })
            continue
        recovered[key] = target

    atomic_json_write(args.output, recovered)
    Path(args.issues).parent.mkdir(parents=True, exist_ok=True)
    with open(args.issues, "w", encoding="utf-8-sig", newline="") as handle:
        fields = ["Anahtar", "Ingilizce", "Turkce", "Sorun", "KaynakKodlari", "CeviriKodlari", "Yontem", "Zaman"]
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(issues)

    print(json.dumps({
        "live_rows": counters["rows"],
        "latest_unique": len(latest),
        "recovered": len(recovered),
        "format_mismatch": counters["format_mismatch"],
        "placeholder_leak": counters["placeholder_leak"],
        "issues": len(issues),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

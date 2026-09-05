import argparse
import json
import re
from pathlib import Path


def load_json(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def save_json(path, value):
    temp = Path(str(path) + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def restore_tsv_cell(value):
    """wakfu_audit.py tarafından TSV için kaçırılan hücreyi geri açar."""
    restored = []
    index = 0
    escapes = {"t": "\t", "r": "\r", "n": "\n", "\\": "\\"}
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            marker = value[index + 1]
            if marker in escapes:
                restored.append(escapes[marker])
                index += 2
                continue
        restored.append(value[index])
        index += 1
    return "".join(restored)


def read_tsv(path):
    with open(path, encoding="utf-8-sig") as handle:
        header = handle.readline().rstrip("\r\n").split("\t")
        rows = []
        for line in handle:
            fields = line.rstrip("\r\n").split("\t")
            if len(fields) == len(header):
                rows.append(dict(zip(header, fields)))
        return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", required=True)
    parser.add_argument("--main", required=True)
    parser.add_argument("--manual", required=True)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    main_memory = load_json(args.main)
    manual_memory = load_json(args.manual)
    batch = load_json(args.batch)
    key_repairs = {str(k): str(v) for k, v in batch.get("keys", {}).items()}
    source_key_repairs = {
        str(k): str(v) for k, v in batch.get("source_keys", {}).items()
    }
    source_repairs = {str(k): str(v) for k, v in batch.get("sources", {}).items()}
    scoped_source_repairs = []
    for scope in batch.get("scoped_sources", []):
        prefixes = tuple(str(value) for value in scope.get("prefixes", []))
        repairs = {
            str(k): str(v) for k, v in scope.get("sources", {}).items()
        }
        if prefixes and repairs:
            scoped_source_repairs.append((prefixes, repairs))
    target_replacements = {
        str(k): str(v) for k, v in batch.get("target_replacements", {}).items()
    }
    restore_original_prefixes = tuple(
        str(value) for value in batch.get("restore_original_prefixes", [])
    )
    allowed_statuses = set(batch.get("statuses", []))

    issue_rows = read_tsv(args.issues)

    # Örnek anahtarın kaynak metnini bütün eş sorun satırlarına uygular. Bu,
    # özellikle WAKFU'nun ters eğik çizgili satır sonlarını elle JSON anahtarına
    # kopyalarken oluşabilecek biçim hatalarını önler.
    source_by_key = {
        row["Anahtar"]: restore_tsv_cell(row["Ingilizce"])
        for row in issue_rows
    }
    for seed_key, translation in source_key_repairs.items():
        source_text = source_by_key.get(seed_key)
        if source_text is None:
            raise KeyError(f"Örnek kaynak anahtarı sorun raporunda yok: {seed_key}")
        source_repairs[source_text] = translation

    selected = dict(key_repairs)
    for row in issue_rows:
        if allowed_statuses and row["Durum"] not in allowed_statuses:
            continue
        source_text = restore_tsv_cell(row["Ingilizce"])
        if row["Anahtar"] not in key_repairs:
            for prefixes, repairs in scoped_source_repairs:
                if row["Anahtar"].startswith(prefixes) and source_text in repairs:
                    selected[row["Anahtar"]] = repairs[source_text]
                    break
        if source_text in source_repairs:
            selected[row["Anahtar"]] = source_repairs[source_text]
            continue
        if target_replacements and row["Durum"] == "INGILIZCE_KALINTISI":
            current = str(main_memory.get(row["Anahtar"], row["Turkce"]))
            repaired = current
            for old, new in sorted(
                target_replacements.items(), key=lambda pair: len(pair[0]), reverse=True
            ):
                repaired = re.sub(
                    r"(?<![\w])" + re.escape(old) + r"(?![\w])",
                    lambda _match, replacement=new: replacement,
                    repaired,
                    flags=re.IGNORECASE,
                )
            if repaired != current:
                selected[row["Anahtar"]] = repaired

    restored_main = restored_manual = 0
    if restore_original_prefixes:
        for key in list(main_memory):
            if key.startswith(restore_original_prefixes):
                del main_memory[key]
                restored_main += 1
        for key in list(manual_memory):
            if key.startswith(restore_original_prefixes):
                del manual_memory[key]
                restored_manual += 1

    changed_main = changed_manual = 0
    for key, translation in selected.items():
        if main_memory.get(key) != translation:
            main_memory[key] = translation
            changed_main += 1
        if manual_memory.get(key) != translation:
            manual_memory[key] = translation
            changed_manual += 1

    save_json(args.main, main_memory)
    save_json(args.manual, manual_memory)
    report_lines = [
        "WAKFU İNSAN DENETİMLİ DÜZELTME PARTİSİ",
        f"Parti: {Path(args.batch).name}",
        f"Anahtar karşılığı: {len(key_repairs)}",
        f"Örnek kaynak anahtarı: {len(source_key_repairs)}",
        f"Kaynak metin karşılığı: {len(source_repairs)}",
        f"Kapsamlı kaynak metin grubu: {len(scoped_source_repairs)}",
        f"Hedef ifade düzeltmesi: {len(target_replacements)}",
        f"Özgün İngilizceye döndürülen anahtar öneki: {len(restore_original_prefixes)}",
        f"Ana bellekten kaldırılan korunan ad: {restored_main}",
        f"Manuel bellekten kaldırılan korunan ad: {restored_manual}",
        f"Seçilen toplam anahtar: {len(selected)}",
        f"Ana bellekte değişen: {changed_main}",
        f"Manuel bellekte değişen: {changed_manual}",
    ]
    Path(args.report).write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(
        f"APPLIED|SELECTED={len(selected)}|MAIN={changed_main}|MANUAL={changed_manual}|"
        f"RESTORED_MAIN={restored_main}|RESTORED_MANUAL={restored_manual}"
    )


if __name__ == "__main__":
    main()

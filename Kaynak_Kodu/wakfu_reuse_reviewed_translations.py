import argparse
import collections
import json
from pathlib import Path


def restore_tsv_cell(value):
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


def load_json(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


def save_json(path, value):
    temporary = Path(str(path) + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", required=True)
    parser.add_argument("--main", required=True)
    parser.add_argument("--manual", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    rows = read_tsv(args.status)
    reviewed = collections.defaultdict(set)
    for row in rows:
        if row["Durum"] != "CEVRILDI":
            continue
        source = restore_tsv_cell(row["Ingilizce"])
        target = restore_tsv_cell(row["Turkce"])
        if source.strip() and target.strip() and source.strip() != target.strip():
            reviewed[source].add(target)

    unambiguous = {
        source: next(iter(targets))
        for source, targets in reviewed.items()
        if len(targets) == 1
    }
    selected = {}
    for row in rows:
        if row["Durum"] != "EKSIK":
            continue
        source = restore_tsv_cell(row["Ingilizce"])
        if source in unambiguous:
            selected[row["Anahtar"]] = unambiguous[source]

    report_lines = [
        "WAKFU DOĞRULANMIŞ ÇEVİRİ YENİDEN KULLANIMI",
        f"Tek karşılıklı İngilizce kaynak: {len(unambiguous)}",
        f"Eşleşen eksik anahtar: {len(selected)}",
        f"Belirsiz kaynak: {sum(1 for targets in reviewed.values() if len(targets) > 1)}",
        f"Kuru çalışma: {'EVET' if args.dry_run else 'HAYIR'}",
    ]

    changed_main = changed_manual = 0
    if not args.dry_run:
        main_memory = load_json(args.main)
        manual_memory = load_json(args.manual)
        for key, target in selected.items():
            if main_memory.get(key) != target:
                main_memory[key] = target
                changed_main += 1
            if manual_memory.get(key) != target:
                manual_memory[key] = target
                changed_manual += 1
        save_json(args.main, main_memory)
        save_json(args.manual, manual_memory)

    report_lines.extend(
        (
            f"Ana bellekte değişen: {changed_main}",
            f"Manuel bellekte değişen: {changed_manual}",
        )
    )
    Path(args.report).write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(
        f"REUSE|CANDIDATES={len(selected)}|MAIN={changed_main}|MANUAL={changed_manual}"
    )


if __name__ == "__main__":
    main()

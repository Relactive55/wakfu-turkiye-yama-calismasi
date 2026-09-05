import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from recover_live_translations import atomic_json_write
from wakfu_audit import category, format_ok, read_properties


def live_field(value):
    return str(value or "").replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r").replace("\n", "\\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-jar", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--terminology", required=True)
    parser.add_argument("--manual-repairs")
    parser.add_argument("--live-log", required=True)
    args = parser.parse_args()

    project_path = Path(args.project)
    project = json.loads(project_path.read_text(encoding="utf-8-sig")) if project_path.exists() else {}
    terminology = json.loads(Path(args.terminology).read_text(encoding="utf-8-sig"))
    term_keys = {str(k): str(v) for k, v in terminology.get("keys", {}).items()}
    term_values = {str(k): str(v) for k, v in terminology.get("values", {}).items()}
    manual_repairs = {}
    if args.manual_repairs:
        manual_path = Path(args.manual_repairs)
        if manual_path.exists():
            manual_repairs = {
                str(k): str(v)
                for k, v in json.loads(manual_path.read_text(encoding="utf-8-sig")).items()
            }
    repairs = []

    for key, source in read_properties(args.source_jar):
        target = None
        reason = None
        if key in manual_repairs:
            target, reason = manual_repairs[key], "Elle doğrulanmış kesin düzeltme"
        elif key in term_keys:
            target, reason = term_keys[key], "Zorunlu Wakfu anahtar terimi"
        elif source in term_values:
            target, reason = term_values[source], "Zorunlu Wakfu kaynak terimi"
        else:
            match = re.fullmatch(r"\s*Defeat\s+(\[#\d+\]|\d+)\s+(.+?)\s*", source, re.IGNORECASE | re.DOTALL)
            if match:
                count, name = match.groups()
                target = f"{count} adet {name} yen"
                reason = "Görev hedefi emir kalıbı"

        if target is None or target == project.get(key):
            continue
        if not format_ok(source, target):
            continue
        project[key] = target
        repairs.append((key, source, target, reason))

    atomic_json_write(project_path, project)
    live_path = Path(args.live_log)
    live_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not live_path.exists() or live_path.stat().st_size == 0
    with live_path.open("a", encoding="utf-8-sig" if needs_header else "utf-8", newline="") as handle:
        if needs_header:
            handle.write("Zaman\tYontem\tAnahtar\tKategori\tDurum\tIngilizce\tTurkce\tAciklama\n")
        # Kullanıcı günlüğü özellikle bilgisayarın yerel duvar saatini kullanır.
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: DTZ005
        for key, source, target, reason in repairs:
            fields = (now, "KURAL_TABANLI", key, category(key), "DUZELTILDI", source, target, reason)
            handle.write("\t".join(live_field(value) for value in fields) + "\n")

    print(f"REPAIRS|{len(repairs)}|PROJECT|{len(project)}")


if __name__ == "__main__":
    main()

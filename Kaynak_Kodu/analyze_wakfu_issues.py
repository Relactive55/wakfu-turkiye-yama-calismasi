import argparse
import collections
import re


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
    parser.add_argument("tsv")
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--status")
    parser.add_argument("--category")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    rows = read_tsv(args.tsv)

    print(f"ROWS={len(rows)}")
    if args.status or args.category:
        selected = [
            row for row in rows
            if (not args.status or row["Durum"] == args.status)
            and (not args.category or row["Kategori"] == args.category)
        ]
        stop = None if args.limit <= 0 else args.offset + args.limit
        for row in selected[args.offset:stop]:
            print(
                f"KEY={row['Anahtar']}\nEN={row['Ingilizce']}\n"
                f"TR={row['Turkce']}\nWHY={row['Neden']}\n---"
            )
        return
    residue_tokens = collections.Counter()
    for row in rows:
        if row["Durum"] != "INGILIZCE_KALINTISI":
            continue
        match = re.search(r":\s*([^:]+)$", row["Neden"])
        if match and "Kaynak sözcük" in row["Neden"]:
            residue_tokens[match.group(1).strip()] += 1
    if residue_tokens:
        print("RESIDUE_TOKENS=" + repr(residue_tokens.most_common()))
    statuses = (
        "INGILIZCE_KALDI",
        "INGILIZCE_KALINTISI",
        "TERIM_HATASI",
        "EKSIK",
    )
    for status in statuses:
        group = [row for row in rows if row["Durum"] == status]
        frequencies = collections.Counter(row["Ingilizce"] for row in group)
        categories = collections.Counter(row["Kategori"] for row in group)
        print(
            f"\n{status}: rows={len(group)} unique_en={len(frequencies)} "
            f"categories={categories.most_common()}"
        )
        for english, count in frequencies.most_common(args.top):
            sample = next(row for row in group if row["Ingilizce"] == english)
            print(
                f"{count}\t{sample['Anahtar']}\t{english[:220]!r}\t"
                f"=> {sample['Turkce'][:220]!r}\t{sample['Neden']}"
            )


if __name__ == "__main__":
    main()

from collections import Counter

_NO_VALUE = {"", "—", "–", "-"}

def parse_readme(text, source_url, retrieved_by, retrieved_at):
    rows = []
    for line in text.strip().splitlines():
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(set(c) <= set("-:") for c in cells):
            continue
        rows.append(cells)
    header = rows[0]
    body = rows[1:]
    records = []
    skipped = Counter()
    for i, name in enumerate(header):
        if name.startswith("DeepSeek-"):
            for row in body:
                if row[i] in _NO_VALUE:
                    skipped["値なし（—・空欄）"] += 1
                    continue
                records.append({
                    "model": name,
                    "benchmark": row[0],
                    "score": float(row[i]),
                })
    return records, skipped, []
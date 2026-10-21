from collections import Counter
import re


_NO_VALUE = {"", "—", "–", "-"}

def _clean_value(text):
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    return re.sub(r"[*†‡§]+$", "", text).strip()

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
    skipped = Counter()
    body = []
    for row in rows[1:]:
        if all(c == "" for c in row[1:]):
            skipped["見出し行"] += 1
            continue
        body.append(row)
    records = []
   
    for i, name in enumerate(header):
        if name.startswith("DeepSeek-"):
            for row in body:
                if row[i] in _NO_VALUE:
                    skipped["値なし（—・空欄）"] += 1
                    continue
                records.append({
                    "model": name,
                    "benchmark": row[0],
                    "score": float(_clean_value(row[i])),
                })
    return records, skipped, []
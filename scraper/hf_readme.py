from collections import Counter
import re


_NO_VALUE = {"", "—", "–", "-"}

_VALUE = re.compile(r"-?\d+(?:\.\d+)?%?")

_MODES = ("Non-Think", "High", "Max")

def _split_mode(name):
    for mode in _MODES:
        if name.endswith(" " + mode):
            return name[: -len(mode) - 1], mode
    return name, None

def _clean_value(text):
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text).strip()
    text = text.strip("*")
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
    unreadable = []
   
    for i, name in enumerate(header):
        if name.startswith("DeepSeek-"):
            model, mode = _split_mode(name)
            for row in body:
                value = _clean_value(row[i])
                if value in _NO_VALUE:
                    skipped["値なし（—・空欄）"] += 1
                    continue
                if not _VALUE.fullmatch(value):
                    unreadable.append({"model": model, "benchmark": row[0], "raw_value": row[i]})
                    continue
                records.append({
                    "model": model,
                    "mode": mode,
                    "benchmark": row[0],
                    "score": float(value.rstrip("%")),
                })
    return records, skipped, unreadable
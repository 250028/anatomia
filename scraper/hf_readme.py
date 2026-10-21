from collections import Counter
import re


PROVIDER = "DeepSeek"
OWN_MODEL_PREFIX = "DeepSeek-"

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

_SEPARATOR_CELL = re.compile(r":?-+:?")

_BENCH_PAREN = re.compile(r"(.*?)\s*\(([^()]*)\)")

def _split_benchmark(cell):
    # 末尾の括弧(Pass@1・EM など)は測定条件。Rating は単位として分ける
    m = _BENCH_PAREN.fullmatch(cell)
    if not m:
        return cell, None, None
    name, inner = m.groups()
    return (name, None, "Rating") if inner == "Rating" else (name, inner, None)

def _split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]

def _tables(text):
    # 見出しの直後に区切り行(---)がある連続した | の行だけを表とみなす。空行など表でない行で表は終わる
    blocks, block = [], []
    for line in text.splitlines():
        if "|" in line:
            block.append(_split_row(line))
        else:
            blocks.append(block)
            block = []
    blocks.append(block)
    return [b for b in blocks if len(b) >= 2 and all(_SEPARATOR_CELL.fullmatch(c) for c in b[1])]

def parse_readme(text, source_url, retrieved_by, retrieved_at, sha):
    tables = _tables(text)
    if not tables:
        raise ValueError("Markdown の表が見つからない(README の構造が変わった可能性)")
    # 表が複数あるときは、最初の自社の列を持つ表だけを読む
    for table in tables:
        if any(name.startswith(OWN_MODEL_PREFIX) for name in table[0]):
            break
    else:
        raise ValueError("DeepSeek- で始まる列を持つ表が見つからない(README の構造が変わった可能性)")
    header, rows = table[0], table[2:]
    for row in rows:
        if len(row) != len(header):
            raise ValueError(f"列の数が見出し({len(header)})と違う行がある({len(row)}): {row[0]!r}")
    skipped = Counter()
    body = []
    for row in rows:
        if all(c == "" for c in row[1:]):
            skipped["見出し行"] += 1
            continue
        body.append(row)
    records = []
    unreadable = []
    for i, name in enumerate(header):
        if name.startswith(OWN_MODEL_PREFIX):
            model, mode = _split_mode(name)
            for row in body:
                value = _clean_value(row[i])
                if value in _NO_VALUE:
                    skipped["値なし（—・空欄）"] += 1
                    continue
                if not _VALUE.fullmatch(value):
                    unreadable.append({"model": model, "benchmark": row[0], "raw_value": row[i]})
                    continue
                benchmark, condition, unit = _split_benchmark(row[0])
                # 出力の形は暫定。§3-3【案】が決まったら合わせる(google_modelcard.py の records と項目をそろえている)
                records.append({
                    "provider": PROVIDER,
                    "model": model,
                    "mode": mode,
                    "benchmark": benchmark,
                    "score": float(value.rstrip("%")),
                    "unit": "%" if value.endswith("%") else unit,
                    "condition": condition,
                    "raw_value": row[i],
                    "source_url": source_url,
                    "sha": sha,
                    "retrieved_at": retrieved_at,
                    "retrieved_by": retrieved_by,
                    "retrieval_method": "script",
                })
    return records, skipped, unreadable
"""Hugging Face の公式組織の README.md（Markdown の表）から、自社モデルのスコアを取り出す。

README は huggingface_hub の hf_hub_download で生ファイルとして取る（R-2 §5）。ページを描画した
HTML には、マージされていない PR の第三者の値が混ざるため使わない（R-1 §4-1）。
メンバーが手動で実行する（企画書 §6-1）。取得結果は候補データで、正式データへは
実行者以外のメンバーが出典ページと照合してから反映する（企画書 §3-2 ③）。

    python3 -m scraper.hf_readme --by <取得者> --out <出力先.json>
"""

import argparse
import json
import re
import sys
import tempfile
import time
from collections import Counter
from datetime import date

from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.errors import HfHubHTTPError

from scraper.google_modelcard import MIN_INTERVAL_SEC, FetchStopped

# 取得してよいリポジトリを固定する。任意指定の引数は設けない（R-2 の判定外のリポジトリに触れないため）。
# 取得元の版（Preview・正式版・V4.1-Flash）は R-3 で決める（R-1 §2）。決まるまで空にしておく
REPO_IDS = []
OFFICIAL_ORG = "deepseek-ai"

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


def fetch_readme(repo_id):
    """README.md の本文と、取得した版（sha）を返す。再試行はしない。エラーが返ったら止める（回避しない）。"""
    # 保存先は一時ディレクトリ。README の本文をリポジトリに残さない（企画書 §3-2 ①・§6-3）
    with tempfile.TemporaryDirectory() as tmp:
        try:
            info = HfApi().model_info(repo_id)
            if info.author != OFFICIAL_ORG:
                raise FetchStopped(f"{repo_id} の作者が {OFFICIAL_ORG} ではない({info.author})。取得を止める")
            path = hf_hub_download(repo_id, "README.md", revision=info.sha, cache_dir=tmp, local_dir=tmp)
        except HfHubHTTPError as e:
            raise FetchStopped(f"{repo_id} の取得でエラーが返った({e})。取得を止める") from e
        with open(path, encoding="utf-8") as f:
            return f.read(), info.sha


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--by", required=True, help="取得者(実行したメンバーの名前)")
    ap.add_argument("--out", required=True, help="候補データの出力先(JSON)")
    args = ap.parse_args()

    if not REPO_IDS:
        sys.exit("取得するリポジトリが決まっていない(REPO_IDS が空。R-3 で決める)")
    today = date.today().isoformat()
    all_records = []
    try:
        for repo_id in REPO_IDS:
            time.sleep(MIN_INTERVAL_SEC)
            text, sha = fetch_readme(repo_id)
            url = f"https://huggingface.co/{repo_id}"
            records, skipped, unreadable = parse_readme(text, url, args.by, today, sha)
            print(f"{url}: {len(records)} 件。取り込まなかった: {dict(skipped)}", file=sys.stderr)
            for u in unreadable:
                print(f"  解釈できない値(要確認): {u['model']} / {u['benchmark']} / {u['raw_value']!r}", file=sys.stderr)
            all_records.extend(records)
    except FetchStopped as e:
        sys.exit(str(e))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"records": all_records}, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

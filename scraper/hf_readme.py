"""Hugging Face の公式組織の README.md（Markdown の表）から、自社モデルのスコアを取り出す。

README は、resolve の URL から生ファイルとして 1 回だけ取る（R-2 §5 の hf_hub_download と同じファイル）。
版（sha）は、同じ応答の X-Repo-Commit ヘッダーから取る（huggingface_hub も、この応答のヘッダーから取っている）。
ページを描画した HTML には、マージされていない PR の第三者の値が混ざるため使わない（R-1 §4-1）。
huggingface_hub と API は使わない：hf_hub_download は 429 でも内部で再試行し、企画書 §6-3 の「429 が返ったら止める」と
合わないため。requests で 1 回だけ取り、200 以外が返ったら止める（Google 側と同じ）。
メンバーが手動で実行する（企画書 §6-1）。取得結果は候補データで、正式データへは
実行者以外のメンバーが出典ページと照合してから反映する（企画書 §3-2 ③）。

    python3 -m scraper.hf_readme --by <取得者> --out <出力先.json>
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import date

import requests

from scraper.google_modelcard import MIN_INTERVAL_SEC, USER_AGENT, FetchStopped
from scraper.values import NO_VALUE, clean_value

# 取得してよいリポジトリを固定する。任意指定の引数は設けない（R-2 の判定外のリポジトリに触れないため）。
# 取得元の版（Preview・正式版・V4.1-Flash）は R-3 で決める（R-1 §2）。決まるまで空にしておく
REPO_IDS = []
OFFICIAL_ORG = "deepseek-ai"
README_URL = "https://huggingface.co/{repo_id}/resolve/main/README.md"

PROVIDER = "DeepSeek"
OWN_MODEL_PREFIX = "DeepSeek-"

_VALUE = re.compile(r"-?\d+(?:\.\d+)?%?")

_MODES = ("Non-Think", "High", "Max")


def _split_mode(name):
    for mode in _MODES:
        if name.endswith(" " + mode):
            return name[: -len(mode) - 1], mode
    return name, None


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
    # 表が複数あるときは、最初の自社の列を持つ表だけを読む。残りは数えて知らせる(黙って捨てない)
    own_tables = [t for t in tables if any(name.startswith(OWN_MODEL_PREFIX) for name in t[0])]
    if not own_tables:
        raise ValueError("DeepSeek- で始まる列を持つ表が見つからない(README の構造が変わった可能性)")
    table = own_tables[0]
    header, rows = table[0], table[2:]
    for row in rows:
        if len(row) != len(header):
            raise ValueError(f"列の数が見出し({len(header)})と違う行がある({len(row)}): {row[0]!r}")
    skipped = Counter()
    if len(own_tables) > 1:
        skipped["読まなかった表（自社の列あり）"] = len(own_tables) - 1
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
                value = clean_value(row[i])
                if value in NO_VALUE:
                    skipped["値なし（—・空欄）"] += 1
                    continue
                if not _VALUE.fullmatch(value):
                    unreadable.append({"model": model, "mode": mode, "benchmark": row[0], "raw_value": row[i]})
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


_SHA = re.compile(r"[0-9a-f]{40}")


def _get(url):
    # 再試行はしない。403・429 などが返ったら止める（回避しない）。token は付けない（メンバー個人の token を使わない）。
    # リダイレクトは追わない：移動先は R-2 の判定を受けていないサイトかもしれず、事後の確認では触れること自体を防げない
    res = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30, allow_redirects=False)
    if res.status_code != 200:
        raise FetchStopped(f"{url} が {res.status_code} を返した。取得を止める")
    return res


def fetch_readme(repo_id):
    """README.md の本文と、その応答が示す版（sha）を返す。README を 1 回だけ取り、200 以外なら止める。"""
    if repo_id.split("/")[0] != OFFICIAL_ORG:
        raise FetchStopped(f"{repo_id} は {OFFICIAL_ORG} のリポジトリではない。取得を止める")
    res = _get(README_URL.format(repo_id=repo_id))
    sha = res.headers.get("X-Repo-Commit")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise FetchStopped(f"{repo_id} の応答に版(X-Repo-Commit)が無いか、読めない({sha!r})。取得を止める")
    # 本文はメモリ上だけで持ち、ファイルに残さない（企画書 §3-2 ①・§6-3）
    return res.content.decode("utf-8"), sha


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
                print(f"  解釈できない値(要確認): {u['model']} / {u['mode']} / {u['benchmark']} / {u['raw_value']!r}", file=sys.stderr)
            all_records.extend(records)
    except FetchStopped as e:
        sys.exit(str(e))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"records": all_records}, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

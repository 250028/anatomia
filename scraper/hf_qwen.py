"""Hugging Face の Qwen の公式組織の README.md（HTML の表）から、自社モデルのスコアを取り出す。

Qwen の自社サイト（qwen.ai）からは取らない（企画書 §6-3。自社規約が自動での取得を禁止している。R-2 §3-1）。
README の取り方は hf_readme.fetch_readme をそのまま使う（公式組織だけを Qwen にする。企画書 §6-3 の Hugging Face の行）。
Qwen の README の表は、Markdown ではなく README に直書きされた HTML の <table>（R-1 §2・§4-1）なので、
hf_readme.py の Markdown の表の解析は使えない。表の作りは、水戸が 2026-11-16 に自分のブラウザで開いた
`/raw/main/README.md` のマークアップで確かめた（そのときの版〔sha〕は確かめていない）。
メンバーが手動で実行する（企画書 §6-1）。取得結果は候補データで、正式データへは
実行者以外のメンバーが出典ページと照合してから反映する（企画書 §3-2 ③）。

    python3 -m scraper.hf_qwen --by <取得者> --out <出力先.json>
"""

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import date
from html.parser import HTMLParser

from scraper import hf_readme
from scraper.google_modelcard import MIN_INTERVAL_SEC, FetchStopped, unmapped_version_like
from scraper.values import NO_VALUE, clean_value

# 取得してよいリポジトリを固定する。任意指定の引数は設けない（R-2 の判定外のリポジトリに触れないため）。
# R-1 §2 の Qwen の行・R-3 §2-1 の Qwen の行による(Qwen3.8 系と Qwen3.6-27B を、このカードの列から取る前提で数えている)。
# License は R-2 §3-3 で Apache 2.0(README 先頭の YAML)。Qwen3.6-27B 自身のカードがあればそちらを正とする(R-3 §2-1)が、有無は確かめていない。
# 実際に取るのはメンバーが手で実行するときだけで、エージェントは実行しない(AGENTS.md 禁則 3)。#47・#48 の後の実取得には、
# リーダーの改めての判断が要る(R-2 §3-3 の「実取得の判断」の条件 1)
REPO_IDS = ["Qwen/Qwen3.8-27B"]
OFFICIAL_ORG = "Qwen"

PROVIDER = "Qwen"
# 取る列は「取る一覧」で決める(R-3 §2-1 の対象だけ)。Qwen3.8 系はサイズ違いを 1 モデルと数える(R-3 §3 の 2)が、
# README の 2 つの表の列見出しは Qwen3.8-27B・Qwen3.6-27B・Qwen3.7-Plus と他社の 2 列で、Qwen3.8 系のほかのサイズの列は無い
# (2026-11-16 に水戸が開いた README のマークアップで確かめた)。Qwen3.7-Plus は R-1 §2 の列にないので取らない(R-3 §3 の 1)。
# 一覧にない列は、取り込まずに数える。足すときは企画書 §4-3 の「見直し」で行う(hf_readme.py と同じ形)
TAKEN_MODELS = frozenset({"Qwen3.8-27B", "Qwen3.6-27B"})
# 他社の列と、自社の取らない列を分けて数えるための接頭辞(google_modelcard.py の OWN_MODEL_PREFIX と同じ使い方)
OWN_MODEL_PREFIX = "Qwen"
# README の名前 → (benchmark, benchmark_version)。google_modelcard.py の BENCHMARK_NAMES と同じ形・同じ書き方にそろえた【案】
# (チームの決定ではない。名前に含めるか別の項目にするかの最終的な決め方は §3-3・R-4・R-5)。末尾の数字から自動で分けない理由も同じ。
# ほかの会社の同じベンチマークに合わせた:Terminal-Bench(Google・OpenAI・xAI)、DeepSWE の v1.1(Google・xAI)、LiveCodeBench(Mistral AI)。
# ここにない名前は、README の表記のまま持つ(版は null)。CharXiv (RQ) の RQ・HLE の略記は、README に意味が書かれていないので、表記のまま
BENCHMARK_NAMES = {
    "Terminal Bench 2.1 (Terminus)": ("Terminal-Bench", "2.1"),
    "DeepSWE 1.1": ("DeepSWE", "v1.1"),
    "LiveCodeBench v6": ("LiveCodeBench", "v6"),
    "OmniDocBench 1.5": ("OmniDocBench", "1.5"),
}
# README の名前の括弧のうち、ハーネスなので測定条件に入れるもの【案】(企画書 §3-3 の測定条件の行「括弧内の指標やハーネスは、名前ではなく
# ここに記録する」。R-1 §4-2 が、この名前の Terminus をハーネスの例に挙げている)
BENCHMARK_CONDITIONS = {
    "Terminal Bench 2.1 (Terminus)": "Terminus",
}

# 値なしの表記。Qwen/Qwen3.8-27B の README の、表の下の注に、`--` は結果がまだ無いか当てはまらないことを示す、と書かれている。
# values.NO_VALUE に `--` が無いので、ここで足す【案】(共通の NO_VALUE に足すかは決めていない。R-1 §4-3 も「--」を未公表の表記に挙げている)。
# 値なしの組はレコードを作らない(企画書 §3-3。画面は「未公表」と出す)
_NO_VALUE = NO_VALUE | {"--"}
_VALUE = re.compile(r"-?\d+(?:\.\d+)?%?")
# 脚注らしい記号。2026-11-16 の README の表には無いが、付いたら意味が分からないので取らずに「要確認」に出す(hf_readme.py の † と同じ考え方)
_FOOTNOTE_MARKS = "†‡§"


class _CellLinesParser(HTMLParser):
    """README の <table> を、行ごとのセルに読む。セルは {"colspan", "lines"} で、lines は <div> で区切られた文字列のリスト。

    2026-11-16 の README では、左端のセルは <div class="benchmark-capability">（説明）と <div class="benchmark-name">
    （ベンチマーク名）、ラベルつきの値は <div class="metric-label"> と <div class="metric-value"> の組を並べた
    <div class="metric-stack">、太字は <strong>。どれも <div> の区切りで lines の 1 つずつになり、<strong> は区切らない。
    google_modelcard._TableParser は、セルの文字を本文と <small> の 2 つにしか分けないので、ここでは使えない。
    """

    _BREAKS = ("div", "br", "p")

    def __init__(self):
        super().__init__()
        self.tables = []
        self._row = None
        self._cell = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
            self.tables[-1].append(self._row)
        elif tag in ("th", "td") and self._row is not None:
            attrs = dict(attrs)
            # rowspan は 2026-11-16 の README には無い。あれば、行と列の対応が変わるので止める
            if int(attrs.get("rowspan") or 1) != 1:
                raise ValueError("rowspan のあるセルがある(表の形が変わった可能性)")
            self._cell = {"colspan": int(attrs.get("colspan") or 1), "lines": []}
            self._buf = []
        elif tag in self._BREAKS and self._cell is not None:
            self._flush()

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._cell is not None:
            self._flush()
            self._row.append(self._cell)
            self._cell = None
        elif tag in self._BREAKS and self._cell is not None:
            self._flush()
        elif tag == "tr":
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._buf.append(data)

    def _flush(self):
        text = " ".join("".join(self._buf).split())
        if text:
            self._cell["lines"].append(text)
        self._buf = []


def _rows(table):
    """_CellLinesParser の表を、records_from_rows の中間の形(行ごとのセル、セルは文字列のリスト)に直す。

    colspan は、領域の見出しの行(表の幅いっぱいの 1 セル。2026-11-16 の README では <td colspan="6">)だけに許す。
    """
    width = len(table[0])
    rows = []
    for row in table:
        full_width = len(row) == 1 and row[0]["colspan"] == width
        if not full_width and any(c["colspan"] != 1 for c in row):
            raise ValueError(f"colspan の使い方が想定と違う行がある: {[c['lines'] for c in row]!r}")
        rows.append([c["lines"] for c in row])
    return rows


def parse_readme(text, source_url, retrieved_by, retrieved_at, sha):
    """README の HTML の表から、取る一覧の列の値を、hf_readme.parse_readme と同じ形（records, skipped, unreadable）で返す。

    取る列を持つ表は、すべて読む【案】(2026-11-16 の README では Text Performance と VL Performance の 2 つ)。
    hf_readme.py は最初の表だけを読むが、Qwen で同じにすると VL の表を落とすため。チームの決定ではない。
    取る列を持たない表は、読まずに数える。
    """
    parser = _CellLinesParser()
    parser.feed(text)
    parser.close()
    tables = [t for t in parser.tables if t]
    if not tables:
        raise ValueError("HTML の表が見つからない(README の構造が変わった可能性)")
    records, skipped, unreadable = [], Counter(), []
    read = 0
    for table in tables:
        if not any(_join_lines(c["lines"]) in TAKEN_MODELS for c in table[0][1:]):
            skipped["読まなかった表（取る一覧の列がない）"] += 1
            continue
        r, s, u = records_from_rows(_rows(table), source_url, retrieved_by, retrieved_at, sha)
        records.extend(r)
        skipped.update(s)
        unreadable.extend(u)
        read += 1
    if not read:
        raise ValueError("取る列(取る一覧にある Qwen の列)を持つ表が見つからない(README の構造が変わった可能性)")
    skipped["読んだ表"] = read
    return records, skipped, unreadable


def _join_lines(cell):
    return " ".join(s.strip() for s in cell if s.strip())


def _is_category_row(row):
    # 領域の見出しの行(Coding など)。中間の形では、セルが 1 つか、2 つ目以降が空の行とする
    return len(row) == 1 or all(not _join_lines(c) for c in row[1:])


def _labeled_values(cell):
    """値のセルを、(値, ラベル) のリストにする。[値] はラベルなし、[ラベル, 値, ラベル, 値, ...] はラベルつき。形が違えば None。

    2026-11-16 の README では、ラベルつきの値は metric-label と metric-value の <div> が、この順で交互に並ぶ。
    """
    lines = [s.strip() for s in cell if s.strip()]
    if len(lines) == 1:
        return [(lines[0], None)]
    if not lines or len(lines) % 2:
        return None
    labels, values = lines[0::2], lines[1::2]
    # ラベルの位置に値が来ていたら、並びが想定と違う
    if any(_VALUE.fullmatch(clean_value(label)) for label in labels):
        return None
    return list(zip(values, labels))


def _join(*parts):
    return " / ".join(p for p in parts if p) or None


def records_from_rows(rows, source_url, retrieved_by, retrieved_at, sha):
    """表を行ごとのセル（セルは、<div> で区切られた文字列のリスト）に直した中間の形から、取る一覧の列のレコードを作る。

    rows[0] は見出しの行で、左端は空、2 つ目以降がモデルの列。hf_readme.parse_readme と同じく (records, skipped, unreadable) を返す。
    """
    if not rows:
        raise ValueError("表が空")
    header, body = rows[0], rows[1:]
    if _join_lines(header[0]):
        raise ValueError(f"見出しの行の左端が空ではない({_join_lines(header[0])!r})。表の形が変わった可能性")
    names = {i: _join_lines(c) for i, c in enumerate(header) if i > 0}
    taken = {i: n for i, n in names.items() if n in TAKEN_MODELS}
    if not taken:
        raise ValueError("取る列(取る一覧にある Qwen の列)が見つからない(表の形かモデル名が変わった可能性)")
    own = [n for n in names.values() if n.startswith(OWN_MODEL_PREFIX)]
    skipped = Counter()
    if len(names) - len(own):
        skipped["他社モデルの列"] = len(names) - len(own)
    if len(own) - len(taken):
        skipped["除いた列（取る一覧にない）"] = len(own) - len(taken)

    records = []
    unreadable = []
    category = None
    for row in body:
        if _is_category_row(row):
            category = _join_lines(row[0]) or None
            skipped["領域の見出しの行"] += 1
            continue
        if len(row) != len(header):
            raise ValueError(f"列の数が見出し({len(header)})と違う行がある({len(row)}): {_join_lines(row[0])!r}")
        left = [s.strip() for s in row[0] if s.strip()]
        # 左端のセルは、説明(benchmark-capability)とベンチマーク名(benchmark-name)の 2 つ
        if len(left) != 2:
            for i, model in taken.items():
                unreadable.append({"model": model, "mode": None, "benchmark": _join_lines(row[0]), "raw_value": _join_lines(row[i])})
            continue
        description, name = left
        benchmark, benchmark_version = BENCHMARK_NAMES.get(name, (name, None))
        cells = {i: _labeled_values(c) for i, c in enumerate(row) if i > 0}
        # ラベルつきの値がある行で、取る列のセルにラベルのない値があるときは、どの条件の値か分からないので取らない。
        # 値なし(--)のセルにはラベルが付かない(README の表)ので、それは値なしとして数える
        labeled_row = any(p and any(label for _, label in p) for p in cells.values())
        for i, model in taken.items():
            raw = _join_lines(row[i])
            pairs = cells[i]
            unlabeled_value = labeled_row and pairs is not None and any(
                label is None and clean_value(v) not in _NO_VALUE for v, label in pairs)
            if pairs is None or unlabeled_value or any(m in raw for m in _FOOTNOTE_MARKS):
                unreadable.append({"model": model, "mode": None, "benchmark": name, "raw_value": raw})
                continue
            for value, label in pairs:
                # 太字(<strong>。README の表の下の注に、太字は行ごとの最高値を示す、と書かれている)は、タグを読まないので文字に残らない。
                # Markdown の ** が来ても clean_value が外す。強調は取り込まない(R-1 §4-3)
                value = clean_value(value)
                if value in _NO_VALUE:
                    skipped["値なし（--・空欄）"] += 1
                    continue
                if not _VALUE.fullmatch(value):
                    unreadable.append({"model": model, "mode": None, "benchmark": name, "raw_value": raw})
                    continue
                # キー名は §3-3 と google_modelcard.py の records に合わせている(§3-3 にないキーは to_official.py が落とす)。
                # ラベル(Pass@1・Without CI など)は、表記のまま測定条件に入れ、値ごとに 1 件にする(hf_readme.py の「a / b」のセルと同じ)
                records.append({
                    "provider": PROVIDER,
                    "model": model,
                    "mode": None,
                    "benchmark": benchmark,
                    "benchmark_version": benchmark_version,
                    "benchmark_description": description,
                    "source_category": category,
                    "score": float(value.rstrip("%")),
                    "unit": "%" if value.endswith("%") else None,
                    "condition": _join(BENCHMARK_CONDITIONS.get(name), label),
                    "raw_value": raw,
                    "source_url": source_url,
                    "sha": sha,
                    "retrieved_at": retrieved_at,
                    "retrieved_by": retrieved_by,
                    "retrieval_method": "script",
                })
    return records, skipped, unreadable


def fetch_readme(repo_id):
    """README.md の本文と版（sha）を返す。取り方は hf_readme.fetch_readme と同じ(307 は resolve-cache の README のときだけ 1 回追う)。"""
    return hf_readme.fetch_readme(repo_id, official_org=OFFICIAL_ORG)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--by", required=True, help="取得者(実行したメンバーの名前)")
    ap.add_argument("--out", required=True, help="候補データの出力先(JSON)")
    args = ap.parse_args()

    if not REPO_IDS:
        sys.exit("取得するリポジトリがない(REPO_IDS が空)")
    today = date.today().isoformat()
    all_records = []
    try:
        for repo_id in REPO_IDS:
            time.sleep(MIN_INTERVAL_SEC)
            text, sha = fetch_readme(repo_id)
            # 照合する人が、取得した版(sha)の README をブラウザでそのまま開けるようにする(企画書 §3-3 の出典URL)
            url = f"https://huggingface.co/{repo_id}/blob/{sha}/README.md"
            records, skipped, unreadable = parse_readme(text, url, args.by, today, sha)
            print(f"{url}: {len(records)} 件。取り込まなかった: {dict(skipped)}", file=sys.stderr)
            for u in unreadable:
                print(f"  解釈できない値(要確認): {u['model']} / {u['mode']} / {u['benchmark']} / {u['raw_value']!r}", file=sys.stderr)
            for name in unmapped_version_like(records):
                print(f"  版らしい数字を含むが、対応表にない名前（要確認。BENCHMARK_NAMES に足すかを決める）: {name}", file=sys.stderr)
            all_records.extend(records)
    except FetchStopped as e:
        sys.exit(str(e))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"records": all_records}, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

"""Google DeepMind のモデルカード（HTML の表）から、自社モデルのスコアを取り出す。

対象は、R-1・R-2 で「取得可」と判定された次の 2 ページだけ（企画書 §6-3）。
メンバーが手動で実行する（企画書 §6-1）。取得結果は候補データで、正式データへは
実行者以外のメンバーが出典ページと照合してから反映する（企画書 §3-2 ③）。

    python3 -m scraper.google_modelcard --by <取得者> --out <出力先.json>
"""

import argparse
import json
import re
import sys
import time
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

# 取得してよいページを固定する。--url のような任意指定は設けない（R-2 の判定外のサイトに触れないため）
MODEL_CARD_URLS = [
    "https://deepmind.google/models/model-cards/gemini-3-5-flash/",
    "https://deepmind.google/models/model-cards/gemini-3-8-flash/",
]
# Google を取得可としたのは、robots.txt に従うことが条件のため（R-2 §1）。実行のたびに確かめる
ROBOTS_URL = "https://deepmind.google/robots.txt"
PROVIDER = "Google"
# 表には他社モデル（Claude・GPT など）の列も並ぶ。取り込むのは自社モデルの値だけ（R-1 §4-6）
OWN_MODEL_PREFIX = "Gemini"
MIN_INTERVAL_SEC = 3
USER_AGENT = "Anatomia-class-project (manual run)"


class FetchStopped(Exception):
    """取得を止める理由があった（200 以外・robots.txt の禁止など）。回避せず、そのサイトでの取得を止める（企画書 §6-3）。"""


class _TableParser(HTMLParser):
    """<table> を、セルごとの本文（text）と <small> の中身（small）に分けて読む。"""

    def __init__(self):
        super().__init__()
        self.tables = []
        self._row = None
        self._cell = None
        self._small_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
            self.tables[-1].append(self._row)
        elif tag in ("th", "td") and self._row is not None:
            attrs = dict(attrs)
            self._cell = {
                "tag": tag,
                "rowspan": int(attrs.get("rowspan") or 1),
                "colspan": int(attrs.get("colspan") or 1),
                "text": [],
                "small": [],
            }
        elif tag == "small" and self._cell is not None:
            self._small_depth += 1

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._cell is not None:
            self._cell["text"] = _squash(" ".join(self._cell["text"]))
            self._cell["small"] = _squash(" ".join(self._cell["small"]))
            self._row.append(self._cell)
            self._cell = None
        elif tag == "small" and self._small_depth:
            self._small_depth -= 1

    def handle_data(self, data):
        if self._cell is not None:
            self._cell["small" if self._small_depth else "text"].append(data)


def _squash(text):
    return re.sub(r"\s+", " ", text).strip()


def _expand(rows):
    """rowspan・colspan を展開して、行×列の格子にする。引き継いだセルには carried=True を付ける。"""
    grid = []
    pending = {}
    for row in rows:
        out = []
        col = 0
        i = 0
        while i < len(row) or col in pending:
            if col in pending:
                cell, left = pending[col]
                out.append((cell, True))
                if left == 1:
                    del pending[col]
                else:
                    pending[col] = (cell, left - 1)
                col += 1
                continue
            cell = row[i]
            i += 1
            for _ in range(cell["colspan"]):
                out.append((cell, False))
                if cell["rowspan"] > 1:
                    pending[col] = (cell, cell["rowspan"] - 1)
                col += 1
        grid.append(out)
    return grid


# 値として読める形。ここに全体が合わないものは、黙って取り込まず「解釈できない値」にする
_VALUE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(%?)")
_NO_VALUE = {"", "—", "–", "-"}


def _clean_value(text):
    """桁区切りのカンマと、末尾の脚注の記号を除く。"""
    return re.sub(r"[*†‡§]+$", "", re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)).strip()


def _join(*parts):
    return " / ".join(p for p in parts if p)


def parse_modelcard(html, source_url, retrieved_by, retrieved_at):
    """モデルカードの HTML から、自社モデルのスコアのレコード、取り込まなかった件数、
    解釈できなかった値（照合する人が見られるように呼び出し側で出す）を返す。"""
    parser = _TableParser()
    parser.feed(html)
    # ベンチマーク表は、見出し行に "Benchmark" がある最初の表
    rows = next(
        (t for t in parser.tables if t and any(c["text"] == "Benchmark" for c in t[0])),
        None,
    )
    if rows is None:
        raise ValueError("ベンチマークの表が見つからない（ページの構造が変わった可能性）")

    grid = _expand(rows)
    header = [c["text"] for c, _ in grid[0]]
    bench_idx = header.index("Benchmark")
    first_model_idx = next(
        i for i, h in enumerate(header) if i > bench_idx and h not in ("", "Notes")
    )
    models = {i: header[i] for i in range(first_model_idx, len(header))}
    own = {i: m for i, m in models.items() if m.startswith(OWN_MODEL_PREFIX)}

    as_of = re.search(r"Results as of ([A-Za-z]+,? \d{4})", html)
    as_of = as_of.group(1) if as_of else None

    records = []
    skipped = {
        "他社モデルの列": len(models) - len(own),
        "値なし（—・空欄）": 0,
        "料金の行（R-6 で扱う）": 0,
    }
    unreadable = []
    for row in grid[1:]:
        bench_cell = row[bench_idx][0]
        notes = _join(*(row[i][0]["text"] + " " + row[i][0]["small"] for i in range(bench_idx + 1, first_model_idx)))
        notes = _squash(notes)
        category = _squash(" ".join(row[i][0]["text"] for i in range(bench_idx))) or None
        for i, model in own.items():
            cell, carried = row[i]
            # rowspan で引き継いだ値は、継続行の条件に当てはまらないので、最初の行でだけ取る
            if carried:
                continue
            text = cell["text"]
            if text.startswith("$"):
                skipped["料金の行（R-6 で扱う）"] += 1
                continue
            value = _clean_value(text)
            if value in _NO_VALUE:
                skipped["値なし（—・空欄）"] += 1
                continue
            m = _VALUE.fullmatch(value)
            if not m:
                unreadable.append({"model": model, "benchmark": bench_cell["text"], "raw_value": text})
                continue
            unit = "%" if m.group(2) else ("Elo" if notes.lower() == "elo" else None)
            condition = _join("" if notes.lower() == "elo" else notes, cell["small"])
            # 出力の形は暫定。§3-3【案】が決まったら合わせる（§3-3 にない項目: as_of・source_category・benchmark_description・raw_value）
            records.append(
                {
                    "provider": PROVIDER,
                    "model": model,
                    "benchmark": bench_cell["text"],
                    "benchmark_description": bench_cell["small"] or None,
                    "source_category": category,
                    "score": float(m.group(1)),
                    "unit": unit,
                    "condition": condition or None,
                    "raw_value": _squash(text + " " + cell["small"]),
                    "source_url": source_url,
                    "as_of": as_of,
                    "retrieved_at": retrieved_at,
                    "retrieved_by": retrieved_by,
                    "retrieval_method": "script",
                }
            )
    return records, skipped, unreadable


def fetch(url):
    # 再試行はしない。403・429 などが返ったら止める（回避しない）。
    # リダイレクトは追わない：移動先は R-2 の判定を受けていないサイトかもしれず、事後の確認では触れること自体を防げない
    res = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30, allow_redirects=False)
    if res.status_code != 200:
        raise FetchStopped(f"{url} が {res.status_code} を返した。取得を止める")
    return res.text


def check_robots(text, urls):
    """robots.txt の本文を読み、urls のどれかに当てはまる Disallow が 1 つでもあれば止める。

    標準ライブラリの RobotFileParser は、最初に合った規則で決め、`*`・`$` を解釈しないので、
    `Allow: /` の後の `Disallow: /models/` などを取得可と判定する。ここでは安全側に倒し、
    Allow の有無にかかわらず、当てはまる Disallow があれば止める（R-2 §1 の条件は robots.txt 準拠）。
    """
    groups = []
    agents, rules, in_rules = [], [], False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        field, value = (x.strip() for x in line.split(":", 1))
        field = field.lower()
        if field == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(value.lower())
        elif field in ("allow", "disallow"):
            # 先頭の BOM（UTF-8、または ISO-8859-1 で読んだ ï»¿）で最初の User-agent の行を読み落とすと、
            # その下の Disallow が、どの User-agent にも当てはまらないまま無視される。読み方が分からないときは止める
            if not agents:
                raise FetchStopped("robots.txt の User-agent の前に規則がある（読み方が分からない）。取得を止める")
            in_rules = True
            rules.append((field, value))
    groups.append((agents, rules))
    if not any(a for a, _ in groups):
        raise FetchStopped("robots.txt として読めない（User-agent の行がない）。取得を止める")

    name = USER_AGENT.split()[0].split("/")[0].lower()
    for agents, rules in groups:
        if "*" not in agents and not any(a and a in name for a in agents):
            continue
        for field, value in rules:
            if field != "disallow" or not value:
                continue
            pattern = re.escape(value).replace(r"\*", ".*")
            pattern = pattern[:-2] + "$" if pattern.endswith(r"\$") else pattern
            for url in urls:
                if re.match(pattern, urlparse(url).path):
                    raise FetchStopped(f"{url} は robots.txt で禁止されている（Disallow: {value}）。取得を止める")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--by", required=True, help="取得者（実行したメンバーの名前）")
    ap.add_argument("--out", required=True, help="候補データの出力先（JSON）")
    args = ap.parse_args()

    today = date.today().isoformat()
    all_records = []
    try:
        check_robots(fetch(ROBOTS_URL), MODEL_CARD_URLS)
        for url in MODEL_CARD_URLS:
            # robots.txt の取得も 1 回のアクセスなので、すべてのページの前に間隔を空ける
            time.sleep(MIN_INTERVAL_SEC)
            records, skipped, unreadable = parse_modelcard(fetch(url), url, args.by, today)
            print(f"{url}: {len(records)} 件。取り込まなかった: {skipped}", file=sys.stderr)
            for u in unreadable:
                print(f"  解釈できない値（要確認）: {u['model']} / {u['benchmark']} / {u['raw_value']!r}", file=sys.stderr)
            all_records.extend(records)
    except FetchStopped as e:
        sys.exit(str(e))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"records": all_records}, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

"""Hugging Face の Qwen の公式組織の README.md（HTML の表）から、自社モデルのスコアを取り出す。

Qwen の自社サイト（qwen.ai）からは取らない（企画書 §6-3。自社規約が自動での取得を禁止している。R-2 §3-1）。
README の取り方は hf_readme.fetch_readme をそのまま使う（公式組織だけを Qwen にする。企画書 §6-3 の Hugging Face の行）。
Qwen の README の表は、Markdown ではなく README に直書きされた HTML の <table>（R-1 §2・§4-1）なので、
hf_readme.py の Markdown の表の解析は使えない。表の作りは、水戸が 2026-11-16 に自分のブラウザで開いた
`/raw/main/README.md` のマークアップで確かめた（そのときの版〔sha〕は確かめていない）。
メンバーが手動で実行する（企画書 §6-1）。取得結果は候補データで、正式データへは
実行者以外のメンバーが出典ページと照合してから反映する（企画書 §3-2 ③）。

    python3 -m scraper.hf_qwen --by <取得者> --out <出力先.json>

実行の前に：Qwen の実取得についてのリーダーの判断は、まだ無い（R-2 §3-3 の「実取得の判断」は、DeepSeek の 2 リポジトリの
1 回の実行についてのもの）。実行の前に、リーダーの判断が要る。
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

# 実行の前に要る判断。--help の末尾(epilog)に出す。上の docstring の「実行の前に：」の段落と同じ文で、同じことはテストが確かめる。
# docstring から切り出さないのは、python3 -OO では docstring が無くなり、import の時点で落ちるため
BEFORE_RUN = ("実行の前に：Qwen の実取得についてのリーダーの判断は、まだ無い（R-2 §3-3 の「実取得の判断」は、DeepSeek の 2 リポジトリの"
              " 1 回の実行についてのもの）。実行の前に、リーダーの判断が要る。")

# 取得してよいリポジトリを固定する。任意指定の引数は設けない（R-2 の判定外のリポジトリに触れないため）。
# R-1 §2 の Qwen の行・R-3 §2-1 の Qwen の行による(Qwen3.8 系と Qwen3.6-27B を、このカードの列から取る前提で数えている)。
# License は R-2 §3-3 で Apache 2.0(README 先頭の YAML)。Qwen3.6-27B 自身のカードがあればそちらを正とする(R-3 §2-1)が、有無は確かめていない。
# 実際に取るのはメンバーが手で実行するときだけで、エージェントは実行しない(AGENTS.md 禁則 3)。
# Qwen の実取得についてのリーダーの判断は、まだ無い(R-2 §3-3 の「実取得の判断」〔2026-11-11〕は、DeepSeek の 2 リポジトリの
# 1 回の実行についてのもの)。実行の前に、リーダーの判断が要る(docstring に書き、--help にも出す)
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

    README に無い形で、黙って誤った値・分類を出さないようにする:
    - セルの中に div・br・p・strong 以外のタグ(<sup> の脚注、<span> など)があれば、そこでも区切ったうえで、セルに印(extra)を付ける。
      印のあるセルは、_rows と records_from_rows が止めるか「要確認」に出す(<sup>1</sup> が値につながって 12.31 になるのを防ぐ)
    - 表の中に <table> があれば止める(入れ子の表の行が、外の表の行に混ざるのを防ぐ)
    - class が metric-label・metric-value の <div> は、空でも lines に空の文字列として残す(空の <div> を捨てると、ラベルと値の組がずれる)

    表の直後の <ol> の <li>（README では、表の下の注）の文字列も、表ごとに notes に集める（tables と同じ並び）。
    値としては読まず、取得の終わりに「要確認」を出すためだけに使う。表の後、<ol> の前に文字があれば、その <ol> は表の注とみなさない。
    """

    _BREAKS = ("div", "br", "p")
    _INLINE = ("strong",)
    _KEEP_EMPTY = ("metric-label", "metric-value")

    def __init__(self):
        super().__init__()
        self.tables = []
        self.notes = []
        self._in_table = False
        # 直前に閉じた表の番号。表の後に文字が来るか、最初の <ol> が閉じるまでの間だけ持つ
        self._notes_for = None
        self._in_ol = False
        self._li = None
        self._row = None
        self._cell = None
        self._buf = []
        self._divs = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self._in_table:
                raise ValueError("表の中に表がある(表の形が変わった可能性)")
            self.tables.append([])
            self.notes.append([])
            self._in_table = True
            self._notes_for = None
        elif tag == "ol" and not self._in_table and self._notes_for is not None:
            self._in_ol = True
        elif tag == "li" and self._in_ol:
            self._li = []
        elif tag == "tr" and self.tables:
            self._row = []
            self.tables[-1].append(self._row)
        elif tag in ("th", "td") and self._row is not None:
            attrs = dict(attrs)
            # rowspan は 2026-11-16 の README には無い。あれば、行と列の対応が変わるので止める
            if int(attrs.get("rowspan") or 1) != 1:
                raise ValueError("rowspan のあるセルがある(表の形が変わった可能性)")
            self._cell = {"colspan": int(attrs.get("colspan") or 1), "lines": [], "extra": set()}
            self._buf = []
            self._divs = []
        elif tag in self._BREAKS and self._cell is not None:
            self._flush()
            if tag == "div":
                self._divs.append((dict(attrs).get("class") or "").split())
        elif self._cell is not None and tag not in self._INLINE:
            self._cell["extra"].add(tag)
            self._flush()

    def handle_endtag(self, tag):
        if tag in ("th", "td") and self._cell is not None:
            self._flush()
            self._row.append(self._cell)
            self._cell = None
        elif tag == "div" and self._cell is not None:
            classes = self._divs.pop() if self._divs else []
            self._flush(keep_empty=any(c in self._KEEP_EMPTY for c in classes))
        elif tag in self._BREAKS and self._cell is not None:
            self._flush()
        elif self._cell is not None and tag not in self._INLINE and tag not in ("tr", "table"):
            self._cell["extra"].add(tag)
            self._flush()
        elif tag == "tr":
            self._row = None
        elif tag == "table":
            self._in_table = False
            self._notes_for = len(self.tables) - 1
        elif tag == "li" and self._li is not None:
            text = " ".join("".join(self._li).split())
            if text:
                self.notes[self._notes_for].append(text)
            self._li = None
        elif tag == "ol" and self._in_ol:
            self._in_ol = False
            self._notes_for = None

    def handle_data(self, data):
        if self._cell is not None:
            self._buf.append(data)
        elif self._li is not None:
            self._li.append(data)
        elif data.strip() and not self._in_table and not self._in_ol:
            self._notes_for = None

    def _flush(self, keep_empty=False):
        text = " ".join("".join(self._buf).split())
        if text or keep_empty:
            self._cell["lines"].append(text)
        self._buf = []


def _rows(table):
    """_CellLinesParser の表を、records_from_rows の中間の形(行ごとのセル、セルは文字列のリスト)に直す。

    colspan は、領域の見出しの行(表の幅いっぱいの 1 セル。2026-11-16 の README では <td colspan="6">)だけに許す。
    中間の形では、セルが 1 つだけの行を領域の見出しの行とするので、幅いっぱいでない 1 セルだけの行は止める。
    想定外のタグの印(extra)のあるセルの位置を、(行, 列) の集合で一緒に返す。見出しの行と領域の見出しの行に印があれば止める。
    """
    width = len(table[0])
    rows, flagged = [], set()
    for r, row in enumerate(table):
        full_width = len(row) == 1 and row[0]["colspan"] == width
        if not full_width and any(c["colspan"] != 1 for c in row):
            raise ValueError(f"colspan の使い方が想定と違う行がある: {[c['lines'] for c in row]!r}")
        if len(row) == 1 and not full_width:
            raise ValueError(f"セルが 1 つだけで、表の幅いっぱいでない行がある: {row[0]['lines']!r}")
        for c, cell in enumerate(row):
            if cell["extra"]:
                if r == 0 or full_width:
                    raise ValueError(f"見出しの行か領域の見出しの行に、想定外のタグ({sorted(cell['extra'])})がある: {cell['lines']!r}")
                flagged.add((r, c))
        rows.append([c["lines"] for c in row])
    return rows, flagged


def parse_readme(text, source_url, retrieved_by, retrieved_at, sha):
    """README の HTML の表から、取る一覧の列の値を、hf_readme.parse_readme と同じ形（records, skipped, unreadable）で返す。

    取る列を持つ表は、すべて読む【案】(2026-11-16 の README では Text Performance と VL Performance の 2 つ)。
    hf_readme.py は最初の表だけを読むが、Qwen で同じにすると VL の表を落とすため。チームの決定ではない。
    取る列を持たない表は、読まずに数える。
    """
    read, not_read = _read_tables(text)
    records, skipped, unreadable = [], Counter(), []
    if not_read:
        skipped["読まなかった表（取る一覧の列がない）"] = not_read
    for table, _ in read:
        rows, flagged = _rows(table)
        r, s, u = records_from_rows(rows, source_url, retrieved_by, retrieved_at, sha, flagged)
        records.extend(r)
        skipped.update(s)
        unreadable.extend(u)
    skipped["読んだ表"] = len(read)
    return records, skipped, unreadable


def _read_tables(text):
    """README の表のうち、取る列を持つものを (表, 表の直後の注) のリストで、取る列を持たない表をその数で返す。"""
    parser = _CellLinesParser()
    parser.feed(text)
    parser.close()
    tables = [(t, n) for t, n in zip(parser.tables, parser.notes) if t]
    if not tables:
        raise ValueError("HTML の表が見つからない(README の構造が変わった可能性)")
    read = [(t, n) for t, n in tables if any(_join_lines(c["lines"]) in TAKEN_MODELS for c in t[0][1:])]
    if not read:
        raise ValueError("取る列(取る一覧にある Qwen の列)を持つ表が見つからない(README の構造が変わった可能性)")
    return read, len(tables) - len(read)


def readme_warnings(text):
    """取得の終わりに「要確認」として出す、レコードには入れない点を、1 行ずつの文字列のリストで返す。

    読んだ表に、取る一覧の列のうち見出しに無いものがあれば、その名前を出す(列の名前が変わると、その表の値は件数が減るだけで、
    ほかには何も出ないため)。
    読んだ表の直後に注(<ol> の <li>)があれば、その件数と、注の先頭(最初の「:」の前)に名前が出る、その表のベンチマークを出す。
    2026-11-16 の README では、注に測定条件(ハーネスなど)や社内のベンチマークであることが書かれているが、注は取り込まない。
    注の条件を測定条件(condition)に入れるかは決まっていない(チームに聞く点)。注の文はここでは返さない。
    """
    read, _ = _read_tables(text)
    warnings = []
    for number, (table, notes) in enumerate(read, 1):
        missing = sorted(TAKEN_MODELS - {_join_lines(c["lines"]) for c in table[0][1:]})
        if missing:
            warnings.append(f"読んだ表 {number} の見出しに、取る一覧の列が無い（要確認。列の名前が変わった可能性）: {', '.join(missing)}")
        if not notes:
            continue
        names = []
        for row in _rows(table)[0][1:]:
            left = [s.strip() for s in row[0] if s.strip()]
            if len(row) > 1 and len(left) == 2 and left[1] not in names:
                names.append(left[1])
        heads = [note.split(":", 1)[0] for note in notes if ":" in note]
        noted = [n for n in names if any(re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", h) for h in heads)]
        warnings.append(
            f"読んだ表 {number} の下に注が {len(notes)} 件ある（要確認。注は取り込んでいない。測定条件などが書かれていることがある）。"
            f"注の先頭に名前が出るベンチマーク: {', '.join(noted) or 'なし'}")
    return warnings


def _join_lines(cell):
    return " ".join(s.strip() for s in cell if s.strip())


def _is_category_row(row):
    # 領域の見出しの行(Coding など)。中間の形では、セルが 1 つだけの行とする(_rows は、表の幅いっぱいの 1 セルの行だけをこの形にする)。
    # 値のセルがすべて空の行は、領域の行とみなさない(取る列のセルは「要確認」に出る)
    return len(row) == 1


def _labeled_values(cell):
    """値のセルを、(値, ラベル) のリストにする。[値] はラベルなし、[ラベル, 値, ラベル, 値, ...] はラベルつき。形が違えば None。

    2026-11-16 の README では、ラベルつきの値は metric-label と metric-value の <div> が、この順で交互に並ぶ。
    空のラベル・空の値(空の metric-label・metric-value の <div>。_CellLinesParser が空の文字列として残す)があれば、
    組がずれていないか分からないので None にする。
    空のセル(<td></td>。lines が空)も None にする(「要確認」に出す)。値なしにはしない【案】:2026-11-16 の README は、
    値なしを `--` で示していて、空のセルは無い。空のセルは README に無い形なので、値が読めない形に変わった可能性を、
    値なしとして黙って数えずに出す(hf_readme.py・google_modelcard.py の Markdown の表では、空のセルは値なし)。
    """
    lines = [s.strip() for s in cell]
    if len(lines) == 1:
        return [(lines[0], None)] if lines[0] else None
    if not lines or len(lines) % 2:
        return None
    labels, values = lines[0::2], lines[1::2]
    if not all(labels) or not all(values):
        return None
    # ラベルの位置に値が来ていたら、並びが想定と違う
    if any(_VALUE.fullmatch(clean_value(label)) for label in labels):
        return None
    return list(zip(values, labels))


def _join(*parts):
    return " / ".join(p for p in parts if p) or None


def records_from_rows(rows, source_url, retrieved_by, retrieved_at, sha, flagged=frozenset()):
    """表を行ごとのセル（セルは、<div> で区切られた文字列のリスト）に直した中間の形から、取る一覧の列のレコードを作る。

    rows[0] は見出しの行で、左端は空、2 つ目以降がモデルの列。hf_readme.parse_readme と同じく (records, skipped, unreadable) を返す。
    flagged は、想定外のタグのあったセルの (行, 列)(_rows が返す)。左端に印があればその行の、取る列のセルに印があればそのセルの値を、
    取らずに「要確認」に出す。
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
    for r, row in enumerate(body, 1):
        if _is_category_row(row):
            category = _join_lines(row[0]) or None
            skipped["領域の見出しの行"] += 1
            continue
        if len(row) != len(header):
            raise ValueError(f"列の数が見出し({len(header)})と違う行がある({len(row)}): {_join_lines(row[0])!r}")
        left = [s.strip() for s in row[0] if s.strip()]
        # 左端のセルは、説明(benchmark-capability)とベンチマーク名(benchmark-name)の 2 つ
        if len(left) != 2 or (r, 0) in flagged:
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
            if pairs is None or unlabeled_value or (r, i) in flagged or any(m in raw for m in _FOOTNOTE_MARKS):
                unreadable.append({"model": model, "mode": None, "benchmark": name, "raw_value": raw})
                continue
            for value, label in pairs:
                # 太字(<strong>。README の表の下の注に、太字は行ごとの最高値を示す、と書かれている)は、タグを読まないので文字に残らない。
                # Markdown の ** が来ても clean_value が外す。強調は取り込まない(R-1 §4-3)
                value = clean_value(value)
                # ここに来るのは -- などの記号だけ。空のセル・空の <div> は、_labeled_values が None にして「要確認」に出す
                if value in _NO_VALUE:
                    skipped["値なし（-- などの記号）"] += 1
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
    # docstring が無いとき(python3 -OO)も落ちないよう、無ければ説明を空にする
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0], epilog=BEFORE_RUN)
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
            for warning in readme_warnings(text):
                print(f"  {warning}", file=sys.stderr)
            all_records.extend(records)
    except FetchStopped as e:
        sys.exit(str(e))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"records": all_records}, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

"""Hugging Face の Qwen の公式組織の README.md（HTML の表）から、自社モデルのスコアを取り出す（HTML を読む部分はまだない）。

Qwen の自社サイト（qwen.ai）からは取らない（企画書 §6-3。自社規約が自動での取得を禁止している。R-2 §3-1）。
README の取り方は hf_readme.py（DeepSeek）と同じで、resolve の URL から生ファイルとして 1 回だけ取り、
版（sha）は同じ応答の X-Repo-Commit ヘッダーから取る（企画書 §6-3 の Hugging Face の行）。
Qwen の README の表は、Markdown ではなく README に直書きされた HTML の <table>（R-1 §2・§4-1）なので、
hf_readme.py の Markdown の表の解析は使えない。表の見た目は、水戸が 2026-11-16 にブラウザで見た画面の画像で確かめた。
それをもとに、表を行ごとのセルに直した中間の形からレコードを作る部分（records_from_rows）は書いた。
HTML から中間の形を作る部分（parse_readme）は、実物のマークアップを確かめていないので書いていない。
確かめるまで REPO_IDS を空にしておき、取得もしない。
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

from scraper.google_modelcard import MIN_INTERVAL_SEC, FetchStopped
from scraper.hf_readme import README_URL, _SHA, _get
from scraper.values import NO_VALUE, clean_value

# 取得してよいリポジトリを固定する。任意指定の引数は設けない（R-2 の判定外のリポジトリに触れないため）。
# 取得元は Qwen/Qwen3.8-27B の 1 つを予定している（R-1 §2 の Qwen の行・R-3 §2-1 の Qwen の行。License は R-2 §3-3 で Apache 2.0）。
# HTML を読む部分(parse_readme)を書くまでは、取得しても読めないので空にしておく（main は、空なら取得せずに止まる）
REPO_IDS = []
OFFICIAL_ORG = "Qwen"

PROVIDER = "Qwen"
# 取る列は「取る一覧」で決める(R-3 §2-1 の対象だけ)。Qwen3.8 系はサイズ違いを 1 モデルと数える(R-3 §3 の 2)が、
# 取るのは R-1 で形式を確かめた Qwen3.8-27B のカードの列とし、Qwen3.6-27B もそのカードの列から取る(R-3 §2-1)。
# 同じカードの Qwen3.7-Plus の列は R-1 §2 の列にないので取らない(R-3 §3 の 1)。列見出しの綴りと、Qwen3.8 系のほかのサイズの列が無いことは、
# 水戸が 2026-11-16 にブラウザで見た画面の画像で確かめた(表は 2 つ。マークアップの中の綴りは確かめていない)。
# 一覧にない列は、取り込まずに数える。足すときは企画書 §4-3 の「見直し」で行う(hf_readme.py と同じ形)
TAKEN_MODELS = frozenset({"Qwen3.8-27B", "Qwen3.6-27B"})
# 他社の列と、自社の取らない列を分けて数えるための接頭辞(google_modelcard.py の OWN_MODEL_PREFIX と同じ使い方)
OWN_MODEL_PREFIX = "Qwen"

# 値なしの表記。values.NO_VALUE に `--` が無いので、ここで足す(R-1 §4-3 は「--」も未公表の表記に挙げている)。
# 値なしの組はレコードを作らない(企画書 §3-3。画面は「未公表」と出す)
_NO_VALUE = NO_VALUE | {"--"}
_VALUE = re.compile(r"-?\d+(?:\.\d+)?%?")
# 脚注らしい記号。意味は README ごとに違い(hf_readme.py の † の扱い)、Qwen の表の脚注はまだ確かめていないので、付いた値は取らずに「要確認」に出す
_FOOTNOTE_MARKS = "†‡§"


def parse_readme(text, source_url, retrieved_by, retrieved_at, sha):
    """README の HTML の表から、取る一覧の列の値を、hf_readme.parse_readme と同じ形（records, skipped, unreadable）で返す。

    HTML の表を、records_from_rows が受け取る中間の形に直す部分は、まだ書いていない。実物のマークアップ
    （セルの中の 2 段の書き方が <br> か別の要素か、colspan・rowspan の有無）を確かめていないため。
    """
    raise NotImplementedError("Qwen の README の表のマークアップを実物で確かめてから書く")


def _join_lines(cell):
    return " ".join(s.strip() for s in cell if s.strip())


def _column_name(cell):
    # 列見出しは画面では「Qwen3.8-」「27B」の 2 段に見える。画面の折り返しか、改行の要素かは確かめていないので、空白を除いてつなぐ。
    # 取る一覧の名前は空白を含まないので、これで比べられる
    return "".join(_join_lines(cell).split())


def _is_category_row(row):
    # 領域の見出しの行(Coding など)は、画面では表の幅いっぱいの 1 つのセル。中間の形では、セルが 1 つか、2 つ目以降が空の行とする
    return len(row) == 1 or all(not _join_lines(c) for c in row[1:])


def _labeled_values(cell):
    """値のセルを、(値, ラベル) のリストにする。[値] はラベルなし、[ラベル, 値, ラベル, 値, ...] はラベルつき。形が違えば None。

    画面では、1 つのセルに小さい字のラベル(Pass@1 など)とその値が、上下に交互に並ぶ行がある。マークアップは確かめていない。
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


def records_from_rows(rows, source_url, retrieved_by, retrieved_at, sha):
    """表を行ごとのセル（セルは、画面で上下に並ぶ文字列のリスト）に直した中間の形から、取る一覧の列のレコードを作る。

    中間の形はこのモジュールで決めたもので、実物のマークアップから作れるかは確かめていない（形は水戸が 2026-11-16 に
    ブラウザで見た画面の画像による）。rows[0] は見出しの行で、左端は空、2 つ目以降がモデルの列。
    hf_readme.parse_readme と同じく (records, skipped, unreadable) を返す。
    """
    if not rows:
        raise ValueError("表が空")
    header, body = rows[0], rows[1:]
    if _join_lines(header[0]):
        raise ValueError(f"見出しの行の左端が空ではない({_join_lines(header[0])!r})。表の形が変わった可能性")
    names = {i: _column_name(c) for i, c in enumerate(header) if i > 0}
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
        # 左端のセルは、上に説明(例：Agentic terminal coding)、下に小さい字でベンチマーク名、の 2 段
        if len(left) != 2:
            for i, model in taken.items():
                unreadable.append({"model": model, "mode": None, "benchmark": _join_lines(row[0]), "raw_value": _join_lines(row[i])})
            continue
        description, benchmark = left
        cells = {i: _labeled_values(c) for i, c in enumerate(row) if i > 0}
        # ラベルつきの値がある行で、取る列のセルにラベルがないときは、どの条件の値か分からないので取らない
        labeled_row = any(p and any(label for _, label in p) for p in cells.values())
        for i, model in taken.items():
            raw = _join_lines(row[i])
            pairs = cells[i]
            if pairs is None or (labeled_row and any(label is None for _, label in pairs)) \
                    or any(m in raw for m in _FOOTNOTE_MARKS):
                unreadable.append({"model": model, "mode": None, "benchmark": benchmark, "raw_value": raw})
                continue
            for value, label in pairs:
                # 太字(行の中の最大の値の強調)の * は clean_value が外す。強調は取り込まない(R-1 §4-3)
                value = clean_value(value)
                if value in _NO_VALUE:
                    skipped["値なし（--・空欄）"] += 1
                    continue
                if not _VALUE.fullmatch(value):
                    unreadable.append({"model": model, "mode": None, "benchmark": benchmark, "raw_value": raw})
                    continue
                # キー名は §3-3 と hf_readme.py・google_modelcard.py の records に合わせている。
                # benchmark はページの表記のまま持つ(括弧・版を名前から分けるかは決まっていない)。
                # ラベル(Pass@1・Without CI など)は、表記のまま測定条件に入れる(hf_readme.py の「a / b」のセルと同じく、値ごとに 1 件)
                records.append({
                    "provider": PROVIDER,
                    "model": model,
                    "mode": None,
                    "benchmark": benchmark,
                    "benchmark_description": description,
                    "source_category": category,
                    "score": float(value.rstrip("%")),
                    "unit": "%" if value.endswith("%") else None,
                    "condition": label,
                    "raw_value": raw,
                    "source_url": source_url,
                    "sha": sha,
                    "retrieved_at": retrieved_at,
                    "retrieved_by": retrieved_by,
                    "retrieval_method": "script",
                })
    return records, skipped, unreadable


def fetch_readme(repo_id):
    """README.md の本文と、その応答が示す版（sha）を返す。README を 1 回だけ取り、200 以外なら止める。

    hf_readme.fetch_readme と同じ取り方で、公式組織の確認だけを Qwen にしている。
    """
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
        sys.exit("取得するリポジトリがない(REPO_IDS が空。README の表の解析を書いてから入れる)")
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
            all_records.extend(records)
    except FetchStopped as e:
        sys.exit(str(e))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"records": all_records}, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

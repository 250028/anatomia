"""手入力の CSV と、取得スクリプトの出力 JSON を、正式データ(`data/official/<会社>.json`)の形に変換する。

Web にはアクセスしない(手元のファイルを読んで形を変えるだけ)。正式データのキーと必須・任意は企画書 §3-3。
変換しただけでは正式データにならない。実行者以外のメンバーが出典と照合してから、PR で反映する(§3-2 ③)。

    python3 -m scraper.to_official data/manual/OpenAI.csv [--out-dir data/official]
    python3 -m scraper.to_official candidate.json [--out-dir data/official]
"""

import argparse
import csv
import json
import math
import os
import re
import sys
import warnings
from collections import Counter
from datetime import date
from pathlib import Path

# 企画書 §3-3 の表の順。正式データに入れるのは、このキーだけ
OFFICIAL_KEYS = [
    "model",
    "provider",
    "model_type",
    "mode",
    "benchmark",
    "benchmark_version",
    "score",
    "unit",
    "condition",
    "raw_value",
    "source_url",
    "retrieved_at",
    "retrieved_by",
    "retrieval_method",
    "sha",
    "as_of",
]

# 手入力の CSV の見出しの行(§3-3「手入力の値の持ち方」)。会社ごとの CSV で変わらないよう、完全に一致を求める
CSV_COLUMNS = [
    ("モデル名", "model"),
    ("モデルの種類", "model_type"),
    ("推論モード", "mode"),
    ("ベンチマーク名", "benchmark"),
    ("ベンチマークの版・種類", "benchmark_version"),
    ("スコア", "score"),
    ("単位", "unit"),
    ("測定条件", "condition"),
    ("取得元の表記", "raw_value"),
    ("出典URL", "source_url"),
    ("取得日", "retrieved_at"),
    ("取得者", "retrieved_by"),
    ("READMEの版(sha)", "sha"),
    ("備考", None),  # 備考は表にない列なので、正式データに入れない
]

# provider は CSV では列に持たずファイル名から、retrieval_method は読み込み時に付ける(§3-3)
REQUIRED_KEYS = ["model", "provider", "benchmark", "score", "raw_value", "source_url", "retrieved_at", "retrieved_by", "retrieval_method"]

_SCORE = re.compile(r"-?\d+(?:\.\d+)?")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SHA = re.compile(r"[0-9a-f]{40}")
# 会社名は出力のファイル名になるので、ディレクトリの区切りや `..` を含められない(出力先の外に書かないため)
_PROVIDER = re.compile(r"\w[\w ._-]*")

# JSON のレコードで、文字列でなければならないキーと、文字列か null のキー(取得スクリプトの出力が想定外の形のときに止める)
STRING_KEYS = ["model", "provider", "benchmark", "raw_value", "source_url", "retrieved_by"]
OPTIONAL_STRING_KEYS = ["model_type", "mode", "benchmark_version", "unit", "condition", "as_of"]


class ConversionError(ValueError):
    """入力が §3-3 の形になっていない。黙って直さず、どこが違うかを示して止める。"""


def _is_date(value):
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_date(value, where, label):
    if not _is_date(value):
        raise ConversionError(f"{where}: {label} が YYYY-MM-DD の形(実在する日付)でない: {value!r}")


def _check_sha(value, where, label):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ConversionError(f"{where}: {label}が 40 桁の 16 進数でない: {value!r}")


def _check_provider(value, where):
    if not isinstance(value, str) or not _PROVIDER.fullmatch(value) or ".." in value:
        raise ConversionError(f"{where}: provider(会社名)がファイル名にできない形: {value!r}")


def read_manual_csv(path):
    path = Path(path)
    try:
        return _parse_manual_csv(path)
    except UnicodeDecodeError as e:
        raise ConversionError(f"{path.name}: UTF-8 で読めない({e.reason})") from None


def _parse_manual_csv(path):
    provider = path.stem
    # BOM なしが決まりだが、Excel などで保存されて BOM が付いても読めるように utf-8-sig で読む(§3-3)
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header != [name for name, _ in CSV_COLUMNS]:
            raise ConversionError(f"{path.name}: 見出しの行が §3-3 の 14 列と違う: {header}")
        records = []
        for row in reader:
            where = f"{path.name} {reader.line_num} 行目"
            if all(c.strip() == "" for c in row):
                continue
            if len(row) != len(CSV_COLUMNS):
                raise ConversionError(f"{where}: 列の数が見出し({len(CSV_COLUMNS)})と違う({len(row)})")
            cells = {key: cell.strip() or None for (_, key), cell in zip(CSV_COLUMNS, row) if key}
            for (label, key) in CSV_COLUMNS:
                if key in REQUIRED_KEYS and cells.get(key) is None:
                    raise ConversionError(f"{where}: 必須の列「{label}」が空")
            if not _SCORE.fullmatch(cells["score"]):
                raise ConversionError(f"{where}: スコアが数字でない: {cells['score']!r}")
            cells["score"] = float(cells["score"])
            _check_date(cells["retrieved_at"], where, "取得日")
            if cells["sha"] is not None:
                _check_sha(cells["sha"], where, "READMEの版(sha)")
            cells.update(provider=provider, retrieval_method="manual", as_of=None)
            records.append({key: cells.get(key) for key in OFFICIAL_KEYS})
    return records


def read_scraper_json(path):
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ConversionError(f"{path.name}: JSON として読めない: {e}") from None
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ConversionError(f"{path.name}: {{\"records\": [...]}} の形でない")
    records = []
    bad_as_of = []
    for i, rec in enumerate(data["records"], 1):
        where = f"{path.name} {i} 件目"
        if not isinstance(rec, dict):
            raise ConversionError(f"{where}: オブジェクトでない: {rec!r}")
        for key in REQUIRED_KEYS:
            if rec.get(key) in (None, ""):
                raise ConversionError(f"{where}: 必須のキー {key} がない")
        for key in STRING_KEYS:
            if not isinstance(rec[key], str):
                raise ConversionError(f"{where}: {key} が文字列でない: {rec[key]!r}")
        _check_provider(rec["provider"], where)
        for key in OPTIONAL_STRING_KEYS:
            if rec.get(key) is not None and not isinstance(rec[key], str):
                raise ConversionError(f"{where}: {key} が文字列でも null でもない: {rec[key]!r}")
        # NaN や Infinity は、Python の json は読めるが、JSON としては不正な形で出力に入ってしまう
        if isinstance(rec["score"], bool) or not isinstance(rec["score"], (int, float)) or not math.isfinite(rec["score"]):
            raise ConversionError(f"{where}: score が有限の数値でない: {rec['score']!r}")
        _check_date(rec["retrieved_at"], where, "取得日(retrieved_at)")
        if rec["retrieval_method"] not in ("script", "manual"):
            raise ConversionError(f"{where}: retrieval_method が script でも manual でもない: {rec['retrieval_method']!r}")
        if rec.get("sha") is not None:
            _check_sha(rec["sha"], where, "sha")
        # 表にないキー(Google の benchmark_description・source_category など)は落とし、足りない任意のキーは null にする
        out = {key: rec.get(key) for key in OFFICIAL_KEYS}
        # Google のモデルカードの as_of は「May, 2026」のように年月だけで、§3-3 の YYYY-MM-DD にできない。日にちを作らず null にして知らせる
        if out["as_of"] is not None and not _is_date(out["as_of"]):
            bad_as_of.append(out["as_of"])
            out["as_of"] = None
        records.append(out)
    if bad_as_of:
        warnings.warn(
            f"{path.name}: as_of が YYYY-MM-DD でない {len(bad_as_of)} 件は null にした(例: {bad_as_of[0]!r})。年月だけの日付の書き方は §3-3 にない",
            stacklevel=2,
        )
    return records


def write_official(records, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"records": records}, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _read(src):
    """入力 1 つを読み、(会社名, レコード)を返す。"""
    if src.suffix == ".csv":
        return src.stem, read_manual_csv(src)
    if src.suffix == ".json":
        records = read_scraper_json(src)
        providers = {r["provider"] for r in records}
        if len(providers) != 1:
            raise ConversionError(f"{src.name}: 提供企業が 1 つに決まらない: {sorted(providers)}")
        return providers.pop(), records
    raise ConversionError(f"{src.name}: 拡張子が .csv でも .json でもない")


def _warn_duplicates(name, records):
    keys = ("model", "model_type", "mode", "benchmark", "benchmark_version", "condition")
    counts = Counter(tuple(r[k] for k in keys) for r in records)
    dups = [k for k, n in counts.items() if n > 1]
    if dups:
        warnings.warn(
            f"{name}: 同じ組(モデル・種類・推論モード・ベンチマーク・版・測定条件)の値が {len(dups)} 組で複数ある(例: {dups[0]})。"
            "どれを正式データに入れるかは未決(企画書 §8 Q-4)なので、すべて残した",
            stacklevel=2,
        )


def convert(sources, out_dir):
    """入力をすべて読み、会社ごとに 1 つのファイルへ書き出す。書き出したパスを返す。
    同じ会社の入力が複数あっても、1 回でまとめて書くので、先に書いた分を消さない。
    読み込みか出力先の確認で 1 つでも失敗したら、何も書かない。書き出しは、まず一時ファイルにすべて書いてから置き換える
    (一時ファイルへの書き出しが途中で失敗しても、先に書いた会社のファイルは残らない。置き換えの途中の失敗までは防げない)。"""
    grouped = {}
    for src in sources:
        name, records = _read(Path(src))
        grouped.setdefault(name, []).extend(records)
    plan = []
    for name, records in grouped.items():
        _check_provider(name, f"{name}: 会社名")
        _warn_duplicates(name, records)
        out = Path(out_dir) / f"{name}.json"
        if out.exists() and not out.is_file():
            raise ConversionError(f"{out}: 出力先がファイルでない(ディレクトリなど)")
        plan.append((out, records))
    tmps = []
    try:
        for out, records in plan:
            tmp = out.with_name(out.name + ".tmp")
            tmps.append(tmp)
            write_official(records, tmp)
        for tmp, (out, _) in zip(tmps, plan):
            os.replace(tmp, out)
    finally:
        for tmp in tmps:
            tmp.unlink(missing_ok=True)
    return [out for out, _ in plan]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sources", nargs="+", help="手入力の CSV(data/manual/<会社>.csv)か、取得スクリプトの出力 JSON")
    ap.add_argument("--out-dir", default="data/official", help="書き出す先のディレクトリ")
    args = ap.parse_args()
    try:
        outs = convert(args.sources, args.out_dir)
    except (ConversionError, OSError) as e:
        sys.exit(str(e))
    for out in outs:
        print(f"→ {out}", file=sys.stderr)


if __name__ == "__main__":
    main()

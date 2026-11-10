"""手入力の CSV と、取得スクリプトの出力 JSON を、正式データ(`data/official/<会社>.json`)の形に変換する。

Web にはアクセスしない(手元のファイルを読んで形を変えるだけ)。正式データのキーと必須・任意は企画書 §3-3。
変換しただけでは正式データにならない。実行者以外のメンバーが出典と照合してから、PR で反映する(§3-2 ③)。

    python3 -m scraper.to_official data/manual/OpenAI.csv [--out-dir data/official]
    python3 -m scraper.to_official candidate.json [--out-dir data/official]
"""

import argparse
import csv
import json
import re
import sys
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


class ConversionError(ValueError):
    """入力が §3-3 の形になっていない。黙って直さず、どこが違うかを示して止める。"""


def _check_date(value, where, label):
    if not _DATE.fullmatch(value):
        raise ConversionError(f"{where}: {label} が YYYY-MM-DD の形でない: {value!r}")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ConversionError(f"{where}: {label} が存在しない日付: {value!r}") from None


def read_manual_csv(path):
    path = Path(path)
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
            if cells["sha"] is not None and not _SHA.fullmatch(cells["sha"]):
                raise ConversionError(f"{where}: READMEの版(sha)が 40 桁の 16 進数でない: {cells['sha']!r}")
            cells.update(provider=provider, retrieval_method="manual", as_of=None)
            records.append({key: cells.get(key) for key in OFFICIAL_KEYS})
    return records


def read_scraper_json(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise ConversionError(f"{path.name}: {{\"records\": [...]}} の形でない")
    records = []
    for i, rec in enumerate(data["records"], 1):
        for key in REQUIRED_KEYS:
            if rec.get(key) in (None, ""):
                raise ConversionError(f"{path.name} {i} 件目: 必須のキー {key} がない")
        if isinstance(rec["score"], bool) or not isinstance(rec["score"], (int, float)):
            raise ConversionError(f"{path.name} {i} 件目: score が数値でない: {rec['score']!r}")
        # 表にないキー(Google の benchmark_description・source_category など)は落とし、足りない任意のキーは null にする
        records.append({key: rec.get(key) for key in OFFICIAL_KEYS})
    return records


def write_official(records, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"records": records}, f, ensure_ascii=False, indent=2)
        f.write("\n")


def convert(src, out_dir):
    src = Path(src)
    if src.suffix == ".csv":
        records = read_manual_csv(src)
        name = src.stem
    elif src.suffix == ".json":
        records = read_scraper_json(src)
        providers = {r["provider"] for r in records}
        if len(providers) != 1:
            raise ConversionError(f"{src.name}: 提供企業が 1 つに決まらない: {sorted(providers)}")
        name = providers.pop()
    else:
        raise ConversionError(f"{src.name}: 拡張子が .csv でも .json でもない")
    out = Path(out_dir) / f"{name}.json"
    write_official(records, out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sources", nargs="+", help="手入力の CSV(data/manual/<会社>.csv)か、取得スクリプトの出力 JSON")
    ap.add_argument("--out-dir", default="data/official", help="書き出す先のディレクトリ")
    args = ap.parse_args()
    try:
        for src in args.sources:
            out = convert(src, args.out_dir)
            print(f"{src} → {out}", file=sys.stderr)
    except ConversionError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()

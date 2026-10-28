"""正式データ(`data/official/<会社>.json`)の 1 件のスコアの型と、ファイルからの読み込み。

画面のコードは、ここが返す `ScoreRecord` だけを見る。正式データの形は PR #33 の
企画書 §3-3【案】のキーの表が正で、ここは「そのコードでの写し」にすぎない。
#33 が変わったときに直すのは、このファイルの「境界」(`record_from_dict`・`records_in_file`)だけにする。
ロジック層なので `streamlit`・`requests`・`pandas` は import しない(tests/test_viewer_records.py で確かめる)。
"""

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path


class RecordError(ValueError):
    """読み込めないレコードがあった。`problems` に、どのファイルの何番目が何で読めないかを 1 件ずつ持つ。
    黙って捨てると「未公表」に見えて原則 2 が崩れるので、読めたものだけを返さず、必ずこの例外で止める。"""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


@dataclass(frozen=True)
class ScoreRecord:
    """1 件のスコア。フィールド名は #33 のキー名にそろえる(意味は企画書 §3-3 を参照)。"""

    provider: str
    model: str
    benchmark: str
    score: float
    unit: str | None  # %・Elo など。単位なしは None
    source_url: str
    retrieved_at: str  # YYYY-MM-DD
    retrieved_by: str
    retrieval_method: str
    mode: str | None = None
    model_type: str | None = None
    benchmark_version: str | None = None
    condition: str | None = None
    raw_value: str | None = None  # 画面では使わない(③の照合用)
    sha: str | None = None
    as_of: str | None = None  # 画面では使わない


# 取得方法の表示名。#33 は `script`/`manual`、#28 は「手入力」と書き、表記が未確定。
# 知らない値(ダミーの「ダミー」など)は、そのまま出す
_METHOD_LABELS = {"script": "スクリプト", "manual": "手入力"}


def retrieval_method_label(method):
    return _METHOD_LABELS.get(method, method)


def _required_str(raw, key):
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"必須の `{key}` が無いか、文字列でない")
    return value.strip()


def _optional_str(raw, key):
    """任意のキー。#33 で未確定(「なければ省く」と「なければ null」が混在)なので、
    キーが無いのも null も空文字も None として受け付ける。"""
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"`{key}` が文字列でない")
    return value.strip() or None


def record_from_dict(raw, file_provider=None):
    """JSON の 1 件(dict)を `ScoreRecord` にする。形が読めなければ ValueError(理由の 1 文)。

    ここが「JSON の形」と「画面が見る型」の境界。#33 で未確定の点は、すべてここで吸収する
    (決まったらここを直す):
    - `provider`: レコードのキーとファイル名(`file_provider`)の両方を受け付ける。
      どちらか片方だけでもよい。両方あって食い違うときは、どちらが正か分からないので誤りにする
    - `unit`: キーが無い・null・空文字は「単位なし」(None)
    - `raw_value`・`as_of`: 意味の表に行が無い。必須か分からないので、無くても読む
    - `retrieval_method`: `script`/`manual` に限らず、空でない文字列なら受け付ける
    出典(`source_url`・`retrieved_at`・`retrieved_by`)は、#33 でも必須で、禁則 5 の根拠なので、必ず検査する。
    """
    if not isinstance(raw, dict):
        raise ValueError("オブジェクトでない")

    provider = _optional_str(raw, "provider")
    if provider is None:
        provider = file_provider
    elif file_provider is not None and provider != file_provider:
        raise ValueError(f"`provider`({provider})がファイル名({file_provider})と食い違う")
    if not provider:
        raise ValueError("`provider` がレコードにもファイル名にも無い")

    score = raw.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
        raise ValueError("必須の `score` が数値でない")

    retrieved_at = _required_str(raw, "retrieved_at")
    try:
        date.fromisoformat(retrieved_at)
    except ValueError:
        raise ValueError(f"`retrieved_at` が YYYY-MM-DD の日付でない: {retrieved_at}") from None

    return ScoreRecord(
        provider=provider,
        model=_required_str(raw, "model"),
        benchmark=_required_str(raw, "benchmark"),
        score=score,
        unit=_optional_str(raw, "unit"),
        source_url=_required_str(raw, "source_url"),
        retrieved_at=retrieved_at,
        retrieved_by=_required_str(raw, "retrieved_by"),
        retrieval_method=_required_str(raw, "retrieval_method"),
        mode=_optional_str(raw, "mode"),
        model_type=_optional_str(raw, "model_type"),
        benchmark_version=_optional_str(raw, "benchmark_version"),
        condition=_optional_str(raw, "condition"),
        raw_value=_optional_str(raw, "raw_value"),
        sha=_optional_str(raw, "sha"),
        as_of=_optional_str(raw, "as_of"),
    )


def records_in_file(data):
    """1 つのファイルの JSON から、レコードの dict のリストを取り出す。
    ファイルの外形は #33 で未確定(`{"records": [...]}` か配列か)。両方を受け付ける。決まったらここを直す。"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return data["records"]
    raise ValueError('`{"records": [...]}` でも配列でもない')


def load_official(directory):
    """`directory/*.json`(会社ごとのファイル)をすべて読み、1 つのリストにして返す。

    - ファイル名(拡張子を除く)は、レコードの `provider` が無いときの代わりに使う
    - ディレクトリが無い・JSON が 1 つも無いときは空のリスト(「正式データがまだない」の判定は呼び出し側)
    - 読めないレコードが 1 件でもあれば、全部のファイルを見終えてから `RecordError` で止める
      (`problems` に全件の理由が入る)。読めたものだけを返すことはしない
    """
    directory = Path(directory)
    records = []
    problems = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = records_in_file(data)
        except (OSError, ValueError) as e:
            problems.append(f"{path.name}: 読み込めない: {e}")
            continue
        for i, raw in enumerate(items):
            try:
                records.append(record_from_dict(raw, file_provider=path.stem))
            except ValueError as e:
                problems.append(f"{path.name} の {i + 1} 件目: {e}")
    if problems:
        raise RecordError(problems)
    return records

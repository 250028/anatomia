"""正式データ(`data/official/<会社>.json`)の 1 件のスコアの型と、ファイルからの読み込み。

画面のコードは、ここが返す `ScoreRecord` だけを見る。正式データの形は企画書 §3-3
(「正式データの形式と置き場所」と、キーの表)が正で、ここは「そのコードでの写し」にすぎない。
§3-3 が変わったときに直すのは、このファイルの「境界」(`record_from_dict`・`records_in_file`)だけにする。
ロジック層なので `streamlit`・`requests`・`pandas` は import しない(tests/test_viewer_records.py で確かめる)。
"""

import json
import math
import re
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
    """1 件のスコア。フィールド名は企画書 §3-3 のキー名にそろえる(意味は §3-3 を参照)。"""

    provider: str
    model: str
    benchmark: str
    score: float
    unit: str | None  # %・Elo など。単位なしは None
    source_url: str
    retrieved_at: str  # YYYY-MM-DD
    retrieved_by: str
    retrieval_method: str  # `script` か `manual`(企画書 §3-3。検査は `record_from_dict`)
    mode: str | None = None
    model_type: str | None = None
    benchmark_version: str | None = None
    condition: str | None = None
    raw_value: str | None = None  # 画面では使わない(③の照合用)
    sha: str | None = None
    as_of: str | None = None  # 画面では使わない


# 企画書 §3-3 の表のキー(16 個)。正式データのレコードは、これを常に全部置き、これ以外のキーは入れない
OFFICIAL_KEYS = (
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
)

# `retrieval_method` の値(§3-3 の表「必須(`script` か `manual`)」)と、その表示名
RETRIEVAL_METHODS = ("script", "manual")
_METHOD_LABELS = {"script": "スクリプト", "manual": "手入力"}


def record_key(record):
    """同じ値を指す組(モデル＋種類＋推論モード＋ベンチマーク＋版＋測定条件)。
    この組が同じレコードが 2 件あるのは誤りなので、`load_official` が止める。
    測定条件だけが違う値は別の組で、表では同じセルに並ぶ。"""
    return (
        record.provider,
        record.model,
        record.model_type,
        record.mode,
        record.benchmark,
        record.benchmark_version,
        record.condition,
    )


def retrieval_method_label(method):
    return _METHOD_LABELS.get(method, method)


def _required_str(raw, key):
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"必須の `{key}` が無いか、文字列でない")
    return value.strip()


def _check_date(value, key):
    """YYYY-MM-DD の実在する日付か(§3-3「日付(`retrieved_at`・`as_of`)は `YYYY-MM-DD`」)。"""
    # date.fromisoformat は 3.11 以降 `20261020` や `2026-W43-2` も通すので、形も確かめる
    # (`\d` は全角数字にも合うので `[0-9]` を使う)
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError(f"`{key}` が YYYY-MM-DD の日付でない: {value}")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"`{key}` が YYYY-MM-DD の日付でない: {value}") from None


def _optional_str(raw, key):
    """任意のキー。§3-3 は「表のキーは常に置き、値がないときは null」なので、キーが無いことは
    呼び出し元(`record_from_dict`)が先に弾く。ここでは null も空文字も None として受け付ける
    (空文字の扱いは §3-3 に書いておらず、緩いまま)。"""
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"`{key}` が文字列でない")
    return value.strip() or None


def record_from_dict(raw, file_provider=None):
    """JSON の 1 件(dict)を `ScoreRecord` にする。形が読めなければ ValueError(理由の 1 文)。

    ここが「JSON の形」と「画面が見る型」の境界。企画書 §3-3 の決定どおりに検査する:
    - 表のキー(`OFFICIAL_KEYS` の 16 個)を常に置く。キーが足りないのも、表にないキーがあるのも誤り
      (「表のキーは常に置き、値がないときは `null`」「正式データに入れるのは、下の表のキーだけ」)
    - 必須(`model`・`provider`・`benchmark`・`score`・`raw_value`・`source_url`・`retrieved_at`・
      `retrieved_by`・`retrieval_method`)は、null や空文字も誤り。任意のキーは null でよい
    - `provider` はレコードの値が正(「レコードの `provider` を正とし、ファイル名は入れ物の名前」)。
      `file_provider`(ファイル名)と食い違うときは、どちらが正か人が確かめるべきなので誤りにする
    - `retrieval_method` は `script` か `manual`
    - 日付(`retrieved_at`・`as_of`)は `YYYY-MM-DD`。`as_of` は null でもよい
    - `unit`: 単位がなければ null(キーは置く)
    出典(`source_url`・`retrieved_at`・`retrieved_by`)は、禁則 5 の根拠なので、必ず検査する
    (`source_url` は http(s) の URL)。`score` は nan・inf・大きすぎる整数も誤り。
    """
    if not isinstance(raw, dict):
        raise ValueError("オブジェクトでない")

    missing = [k for k in OFFICIAL_KEYS if k not in raw]
    if missing:
        raise ValueError("表のキーが足りない(値がなければ null を置く): " + "・".join(f"`{k}`" for k in missing))
    extra = [k for k in raw if k not in OFFICIAL_KEYS]
    if extra:
        raise ValueError("表にないキーがある(正式データに入れるのは表のキーだけ): " + "・".join(f"`{k}`" for k in extra))

    provider = _required_str(raw, "provider")
    if file_provider is not None and provider != file_provider:
        raise ValueError(f"`provider`({provider})がファイル名({file_provider})と食い違う")

    score = raw.get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("必須の `score` が数値でない")
    try:
        finite = math.isfinite(score)  # 桁数の大きい整数は OverflowError になる
    except (OverflowError, ValueError):
        finite = False
    if not finite:
        raise ValueError("必須の `score` が有限の数値でない(nan・inf・大きすぎる整数)")

    retrieved_at = _required_str(raw, "retrieved_at")
    _check_date(retrieved_at, "retrieved_at")

    as_of = _optional_str(raw, "as_of")
    if as_of is not None:
        _check_date(as_of, "as_of")

    source_url = _required_str(raw, "source_url")
    if not re.match(r"https?://", source_url, re.IGNORECASE):
        raise ValueError(f"`source_url` が http:// か https:// で始まらない: {source_url}")

    retrieval_method = _required_str(raw, "retrieval_method")
    if retrieval_method not in RETRIEVAL_METHODS:
        raise ValueError(f"`retrieval_method` が script でも manual でもない: {retrieval_method}")

    return ScoreRecord(
        provider=provider,
        model=_required_str(raw, "model"),
        benchmark=_required_str(raw, "benchmark"),
        score=score,
        unit=_optional_str(raw, "unit"),
        source_url=source_url,
        retrieved_at=retrieved_at,
        retrieved_by=_required_str(raw, "retrieved_by"),
        retrieval_method=retrieval_method,
        mode=_optional_str(raw, "mode"),
        model_type=_optional_str(raw, "model_type"),
        benchmark_version=_optional_str(raw, "benchmark_version"),
        condition=_optional_str(raw, "condition"),
        raw_value=_required_str(raw, "raw_value"),
        sha=_optional_str(raw, "sha"),
        as_of=as_of,
    )


def records_in_file(data):
    """1 つのファイルの JSON から、レコードの dict のリストを取り出す。
    ファイルの外形は `{"records": [...]}` だけ(企画書 §3-3「ファイルの外形」)。配列だけの形は誤り。"""
    if isinstance(data, dict) and isinstance(data.get("records"), list):
        return data["records"]
    raise ValueError('`{"records": [...]}` の形でない')


def load_official(directory):
    """`directory/*.json`(会社ごとのファイル)をすべて読み、1 つのリストにして返す。

    - ファイル名(拡張子を除く)は、レコードの `provider` と食い違っていないかの確認にだけ使う(正はレコードの値)
    - ディレクトリが存在しない(または、ディレクトリでない)ときは `FileNotFoundError`・`NotADirectoryError`
      (どちらも `OSError`)。パスの誤りを「データなし」に見せないため。存在して JSON が 1 つも無いときだけ空のリスト
      (「正式データがまだない」の判定は呼び出し側)
    - 読めないレコードが 1 件でもあれば、全部のファイルを見終えてから `RecordError` で止める
      (`problems` に全件の理由が入る)。読めたものだけを返すことはしない
    - `record_key` が同じレコードが重なっているときも `RecordError`(どちらの値が正か分からないため)。
      企画書 §8 Q-4(同じ値が複数あるときの扱い)が未決のあいだの暫定で、Q-4 が決まったらここを直す
      (変換の部品 scraper/to_official.py は警告してすべて残すので、決まるまで食い違う)
    """
    directory = Path(directory)
    if not directory.exists():
        raise FileNotFoundError(f"正式データのディレクトリが無い: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"正式データのパスがディレクトリでない: {directory}")
    records = []
    problems = []
    first_seen = {}  # record_key → "ファイル名 の N 件目"
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            items = records_in_file(data)
        except (OSError, ValueError) as e:
            problems.append(f"{path.name}: 読み込めない: {e}")
            continue
        for i, raw in enumerate(items):
            where = f"{path.name} の {i + 1} 件目"
            try:
                record = record_from_dict(raw, file_provider=path.stem)
            except ValueError as e:
                problems.append(f"{where}: {e}")
                continue
            key = record_key(record)
            if key in first_seen:
                problems.append(
                    f"{where}: {first_seen[key]} と、モデル・種類・推論モード・ベンチマーク・版・測定条件が"
                    f"すべて同じ({record.model} / {record.benchmark})。重複か矛盾"
                )
                continue
            first_seen[key] = where
            records.append(record)
    if problems:
        raise RecordError(problems)
    return records

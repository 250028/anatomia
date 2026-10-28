"""`ScoreRecord` の一覧から、「モデル×ベンチマーク」の表を作る整形。画面(app.py)が呼ぶ関数はここに集める。

方針(docs/proposal.md §2-4 の原則 2・§2-3 のやらないこと):
- 値が無い組は「未公表」にする。読み込めない値は `records.load_official` が止めるので、表には出ない
- 領域の列・強中弱・総合スコア・平均・順位は作らない。行の並びもスコアでは並べ替えない
- ロジック層なので `streamlit`・`requests`・`pandas` は import しない(tests/test_viewer_records.py で確かめる)

app.py からの使い方:

    records = load_official("data/official")      # RecordError なら .problems を画面に出す
    shown = filter_by_company(records, selected)  # selected=None で絞り込まない
    grid = build_grid(shown)
    header, rows = table_header(grid), table_rows(grid)   # DataFrame(rows, columns=header) などへ
    items = detail_items(grid.cell(row_index, column_index))   # 選んだセルの詳細
    last = last_retrieved_by_company(records)     # {会社: 最終取得日}
"""

from dataclasses import dataclass
from datetime import date

from viewer.records import ScoreRecord, load_official, retrieval_method_label  # noqa: F401 (load_official は app.py 向けの再公開)

NOT_PUBLISHED = "未公表"
# 測定条件が付いた値の印。条件の中身は詳細(detail_items)で見せる
CONDITION_MARK = "※"
_NONE_TEXT = "（なし）"


@dataclass(frozen=True)
class ModelRow:
    """表の行。「モデル名＋種類＋推論モード」の組(企画書 §3-3)。"""

    provider: str
    model: str
    model_type: str | None
    mode: str | None

    @property
    def label(self):
        extra = " / ".join(x for x in (self.model_type, self.mode) if x)
        return f"{self.model} ({extra})" if extra else self.model


@dataclass(frozen=True)
class BenchmarkColumn:
    """表の列。ベンチマーク名と、版・種類(#33 の `benchmark_version`)の組。"""

    benchmark: str
    benchmark_version: str | None

    @property
    def label(self):
        return f"{self.benchmark} {self.benchmark_version}" if self.benchmark_version else self.benchmark


@dataclass(frozen=True)
class Cell:
    """行と列の交点。`records` が空なら未公表。測定条件だけが違う値は複数入る。"""

    records: tuple[ScoreRecord, ...]

    @property
    def is_published(self):
        return bool(self.records)

    @property
    def text(self):
        if not self.records:
            return NOT_PUBLISHED
        text = " / ".join(format_score(r) for r in self.records)
        return text + CONDITION_MARK if any(r.condition for r in self.records) else text


@dataclass(frozen=True)
class Grid:
    rows: tuple[ModelRow, ...]
    columns: tuple[BenchmarkColumn, ...]
    _cells: dict

    def cell(self, row_index, column_index):
        return self._cells[(self.rows[row_index], self.columns[column_index])]


def format_score(record):
    """72.5 + `%` → `72.5%`、1656 + `Elo` → `1656 Elo`、単位なし → `0.8`。"""
    score = record.score
    text = str(int(score)) if float(score).is_integer() else str(score)
    if record.unit is None:
        return text
    return text + record.unit if record.unit == "%" else f"{text} {record.unit}"


def companies(records):
    """データのある企業の一覧(名前順)。1 件も無い企業は出ない。"""
    return sorted({r.provider for r in records})


def filter_by_company(records, selected):
    """`selected`(企業名の集まり)に含まれる企業のレコードだけ返す。None なら絞り込まない。"""
    if selected is None:
        return list(records)
    selected = set(selected)
    return [r for r in records if r.provider in selected]


def build_grid(records):
    """行(モデル×種類×推論モード)と列(ベンチマーク×版)を、並びが決まった形で作る。
    並びは名前順で、スコアでは並べ替えない(順位を作らない)。"""
    # None と文字列を比べられないので、並べ替えのキーでは None を空文字にする
    rows = sorted(
        {ModelRow(r.provider, r.model, r.model_type, r.mode) for r in records},
        key=lambda x: (x.provider, x.model, x.model_type or "", x.mode or ""),
    )
    columns = sorted(
        {BenchmarkColumn(r.benchmark, r.benchmark_version) for r in records},
        key=lambda x: (x.benchmark, x.benchmark_version or ""),
    )
    found = {}
    for r in records:
        key = (ModelRow(r.provider, r.model, r.model_type, r.mode), BenchmarkColumn(r.benchmark, r.benchmark_version))
        found.setdefault(key, []).append(r)
    cells = {(row, col): Cell(tuple(found.get((row, col), ()))) for row in rows for col in columns}
    return Grid(tuple(rows), tuple(columns), cells)


def table_header(grid):
    return ["提供企業", "モデル", "種類", "推論モード"] + [c.label for c in grid.columns]


def table_rows(grid):
    """表示用の文字列の行。`table_header` と同じ並びで、スコアの列は `Cell.text`(未公表を含む)。"""
    return [
        [row.provider, row.model, row.model_type or _NONE_TEXT, row.mode or _NONE_TEXT]
        + [grid.cell(i, j).text for j in range(len(grid.columns))]
        for i, row in enumerate(grid.rows)
    ]


def detail_items(cell):
    """選んだセルの詳細。セルの値ごと(測定条件違いなら複数)に、「(項目名, 表示する文字列)」の
    リストを作り、それを並べたリストを返す。未公表のセルは空のリスト。出典 URL はそのまま入るので、app.py でリンクにする。
    `raw_value`・`as_of`・`benchmark_description` は出さない(MVP の範囲外)。"""
    details = []
    for r in cell.records:
        items = [
            ("モデル", ModelRow(r.provider, r.model, r.model_type, r.mode).label),
            ("ベンチマーク", BenchmarkColumn(r.benchmark, r.benchmark_version).label),
            ("スコア", format_score(r)),
            ("測定条件", r.condition or "記載なし"),
            ("出典 URL", r.source_url),
            ("取得日", r.retrieved_at),
            ("取得者", r.retrieved_by),
            ("取得方法", retrieval_method_label(r.retrieval_method)),
        ]
        if r.sha:
            items.append(("sha", r.sha))
        details.append(items)
    return details


def last_retrieved_by_company(records):
    """企業ごとの最終取得日(YYYY-MM-DD)。全体の最大値だけでは古い企業が新しく見えるため、企業ごとに出す。"""
    last = {}
    for r in records:
        if r.provider not in last or date.fromisoformat(r.retrieved_at) > date.fromisoformat(last[r.provider]):
            last[r.provider] = r.retrieved_at
    return dict(sorted(last.items()))

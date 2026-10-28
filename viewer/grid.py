"""`ScoreRecord` の一覧から、「モデル×ベンチマーク」の表を作る整形。画面(app.py)が呼ぶ関数はここに集める。

方針(docs/proposal.md §2-4 の原則 2・§2-3 のやらないこと):
- 値が無い組は「未公表」にする。読み込めない値は `records.load_official` が止めるので、表には出ない
- 領域の列・強中弱・総合スコア・平均・順位は作らない。行の並びもスコアでは並べ替えない
- ロジック層なので `streamlit`・`requests`・`pandas` は import しない(tests/test_viewer_records.py で確かめる)

app.py からの使い方(`load_official` は `viewer.records` から import する。ここでは再公開しない):

    from viewer.records import load_official
    records = load_official("data/official")      # RecordError なら .problems を画面に出す
    shown = filter_by_company(records, selected)  # selected=None で絞り込まない。企業名の集まり(文字列 1 つは TypeError)
    grid = build_grid(shown)
    header, rows = table_header(grid), table_rows(grid)   # DataFrame(rows, columns=header) などへ
    # 選んだセルの詳細。位置の番号ではなく、行・列の値で引く(下の注を参照)
    items = detail_items(grid.cell_at(row, column))       # row は grid.rows の要素、column は grid.columns の要素
    last = last_retrieved_by_company(records)     # {会社: 最終取得日}

注:
- セルは `grid.cell_at(row, column)` で引くことを勧める。`grid.cell(row_index, column_index)` は位置の番号なので、
  `st.session_state` に番号を残すと、企業の絞り込みを変えた瞬間に別のセルを指す(範囲外なら IndexError)。
  `ModelRow`・`BenchmarkColumn` は frozen でハッシュできるので、`session_state` や `selectbox` の選択肢にはそちらを使う

Streamlit でのキャッシュの案(Streamlit の API・挙動は実機で確かめていない。すべて【未確認】):
- キャッシュするのは `load_official` の戻り値(`list[ScoreRecord]`、frozen の dataclass)だけ。
  鍵は「ディレクトリのパス」と「`*.json` の更新時刻」にする(更新時刻を引数に入れて、ファイルを直したら読み直す)
- `Grid` は毎回 `build_grid` で作り直す。数百件なら安く、`Grid` は内部に dict を持つのでハッシュできない
  (`hash(grid)` は TypeError)。`Grid` を引数に取る関数をキャッシュ対象にしない
- `RecordError` は例外なのでキャッシュされず、データを直すたびに読み直される(これも【未確認】)
"""

from dataclasses import dataclass
from datetime import date

from viewer.records import ScoreRecord, retrieval_method_label

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
        # 版を名前に含める書き方(`Bench A 2.1`)と別の項目にする書き方(`benchmark_version`)は、#33 の決定待ち。
        # 混在すると別の列に同じ見出しができ得るが、決まるまでは直さない(決まれば実質消える)
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
        """位置の番号で引く。表の描画の中で使う。画面の状態(選択したセル)には使わず、`cell_at` を使う。"""
        return self._cells[(self.rows[row_index], self.columns[column_index])]

    def cell_at(self, row, column):
        """行(`ModelRow`)と列(`BenchmarkColumn`)の値で引く。app.py はこちらを勧める。
        この Grid に無い行・列なら KeyError(絞り込みで消えた行・列を、別のセルと取り違えない)。"""
        return self._cells[(row, column)]


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
    """`selected`(企業名の集まり)に含まれる企業のレコードだけ返す。None なら絞り込まない。
    文字列 1 つを渡すと、文字の集まりとして扱われて 0 件になるので TypeError にする
    (`st.selectbox` は文字列、`st.multiselect` はリストを返す。取り違えを黙って通さない)。"""
    if selected is None:
        return list(records)
    if isinstance(selected, (str, bytes)):
        raise TypeError("`selected` は企業名の集まり(リスト・集合など)で、文字列 1 つではない")
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
    # セルの中の並びは、測定条件の文字列順(条件なしが先)。入力の順に依らず、スコアでは並べない。
    # 同じ測定条件のレコードの重複は load_official が止めるが、build_grid に直接渡されたときのため、
    # 同じ条件の中だけスコアを最後のキーにして並びを決める(順位の意味は持たせない)
    def in_cell(key):
        return Cell(tuple(sorted(found.get(key, ()), key=lambda r: (r.condition or "", r.score))))

    cells = {(row, col): in_cell((row, col)) for row in rows for col in columns}
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

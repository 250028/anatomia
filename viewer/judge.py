"""領域単位の「強・中・弱」の判定(モデル×領域のセル)。画面から切り離した、標準ライブラリだけの純粋な関数。

**位置づけ(必ず読む)**:これは企画書 §3-4 の暫定ルール【案】(PR #39 の head 7a934bb の規則 1〜6)を
そのままコードにした**暫定の実装で、チームの決定ではない**。算出方法は企画書 §8 Q-6 で【未決】。
未決の点の既定値は、水戸の意見(2026-11-11。#39 のコメント 6783472128。チームの決定ではない)にしてある。
Q-6 が変わったら、このファイルの引数の既定値か、下の関数(`split_thirds`・`majority_vote` など)を直す。
画面(app.py)の側は、`judge_domains` の呼び出しを変えずに済むようにしている。

未決の点と、切り替える場所。記号 A〜I は**このファイルで付けた記号**で、#39 のコメント 6783472128 には無い。
「出典」の列が、そのコメントの見出し:

| 点 | 出典(コメント 6783472128 の見出し) | 既定値(水戸の意見。未決) | 切り替える引数・定数 |
| --- | --- | --- | --- |
| A 順位の向き | 「そのほかの点」の「順位の向き」 | 値が大きいほど上位。小さいほど良い・向きが決まらないベンチマークは判定不可 | `directions`(**必ず渡す**)、`rank_lower`(既定 None = 小さいほど良いものは判定不可) |
| B 分け方 | 「そのほかの点」の「3 等分」 | 3 等分(規則 3) | `split`(既定 `split_thirds`) |
| C 判定不可の境界 | 「そのほかの点」の「判定不可の境界の 3」 | モデル数 3 未満(規則 2) | `min_group_size`(既定 `MIN_GROUP_SIZE` = 3) |
| D 同点 | 「そのほかの点」の「端数と同点」 | 上の順位の判定にそろえる(規則 3) | `rank`(既定 `rank_descending`) |
| E 領域の判定 | 「そのほかの点」の「規則 4 の多数決」 | 多数決(規則 4) | `decide`(既定 `majority_vote`) |
| F 測定条件の見分け方 | 【質問】4 | 完全一致。`null` どうしは同じ | `condition_key`(既定は文字列のまま比べる)、`null_condition_comparable` |
| G モデルの単位 | 【質問】5 | **未決。既定値を置かない** | `model_key`(**必ず渡す**。候補 `model_key_name_type_mode`・`model_key_name`) |
| H 1 票の単位 | 【質問】6 | ベンチマーク名ごとに 1 票、版が複数なら最新の版だけ。「最新」の決め方と、どの範囲の版から選ぶかは未決 | `pick_version`(既定 None = 版が複数あるベンチマークの票は判定不可) |
| I セルの意味 | 【質問】7 | 常に「強（2/3 件）」の形(一致した件数／判定が付いた件数) | 戻り値の `DomainCell`。文字列は `cell_text` |

A と G を、既定値の無い必須の引数にした理由:既定値を置くと、呼ぶ側が選んだつもりのないまま仮の判断で動き、
どこが仮だったかが呼び出しに残らない。必須にすると、`app.py` の呼び出しに選んだもの(どのベンチマークの向きを
確かめたか・何を 1 モデルと数えるか)が必ず書かれ、省けば TypeError で気づける。向きの対応をどこに持つか
(`data/domains.json` の中か、別の表か)も決まっていないので、呼ぶ側が渡す。

規則の文面と上の意見で決まらない挙動は、決め打ちにせず、判定不可とその理由を返すか、例外にする。
そのうち、判定に効く**暫定の挙動**(水戸の判断に残すもの)と切り替え方:
- 同じモデル(`model_key` が同じ)の値が 1 グループに 2 件以上 → そのグループ全体を判定不可(`REASON_DUPLICATE_MODEL`)。
  `model_key_name` を選ぶと、推論モードを 2 つ公表したモデルが 1 つあるだけで、そのグループの全員が判定不可になる。
  切り替え:`model_key` を変える。どの値を使うかが決まれば `judge_values` のその分岐を直す
- 同じベンチマーク・同じ版で、測定条件の違う値の判定がすべて同じなら 1 票、食い違えば判定不可
  (`REASON_CONDITIONS_DISAGREE`)。切り替え:`_vote` を直す
- 混在の文字列は「混在（強 1・中 1・弱 1）」。切り替え:`cell_text` を直す(件数は `DomainCell.votes` にある)
- 順位は、渡された `records` の中で付く。企業で絞り込んだ `records` を渡すと、グループが小さくなり判定が変わる。
  版の一覧(そのベンチマークに版がいくつあるか。H の `pick_version` に渡す `benchmark_versions`)も、渡された
  `records` から作る。絞り込むと、「版が複数あるので判定不可」になるかどうかや、選ばれる版も変わる。
  絞り込みの前の `records` で判定し、表示する行だけを絞ることを勧める(どちらにするかは画面の設計で決める)

入力:
- `records`:正式データのレコードの並び。`viewer.records.ScoreRecord` か、正式データの 1 件の dict。
  どちらも `viewer.records.record_from_dict` の検査に通し、通した後の(正規化された)`ScoreRecord` を使う
  (`score` が有限の数値か、など。検査をここに二重に書かない)。
  読めないものが 1 件でもあれば `viewer.records.RecordError`(`.problems` に「records の N 件目: 理由」)。
  使うキーは企画書 §3-3 のキー(PR #42 の head 68bae73 の `scraper/to_official.py` の `OFFICIAL_KEYS` と同じ名前。
  このブランチには `to_official.py` は無い)
- `domains`:ベンチマーク名 → 領域名の対応表(R-4【案】。`data/domains.json` はまだ無いので、呼ぶ側が渡す)。
  キーはレコードの `benchmark` と同じ綴り。表に無いベンチマークの値は、どの領域にも数えず、
  `DomainTable.unclassified` に入れる(R-4 §3 の「未分類」)
- `directions`:ベンチマーク名 → 向き(`HIGHER_IS_BETTER`・`LOWER_IS_BETTER`)。向きを確かめたベンチマークだけを書く。
  表に無いベンチマークの値は判定不可(`REASON_DIRECTION_UNKNOWN`)

ロジック層なので `streamlit`・`requests`・`pandas` は import しない(tests/test_viewer_records.py で確かめる)。
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from viewer.records import RecordError, ScoreRecord, record_from_dict

# 判定の名前(企画書 §3-4 の表と規則 4・5 の言葉)
STRONG = "強"
MIDDLE = "中"
WEAK = "弱"
MIXED = "混在"
NOT_JUDGEABLE = "判定不可"
NOT_PUBLISHED = "未公表"

# A:ベンチマークの向き(`directions` の値)
HIGHER_IS_BETTER = "大きいほど良い"
LOWER_IS_BETTER = "小さいほど良い"
_DIRECTIONS = (HIGHER_IS_BETTER, LOWER_IS_BETTER)

# C:グループのモデル数がこれ未満なら判定不可(規則 2。水戸の意見は 3 のまま。未決)
MIN_GROUP_SIZE = 3

# 判定不可の理由
REASON_FEW_MODELS = "グループのモデル数が {min} 未満"  # 規則 2
REASON_DIRECTION_UNKNOWN = "順位の向きを確かめていないベンチマーク(directions に無い)"  # A
REASON_LOWER_IS_BETTER = "値が小さいほど良いベンチマーク(逆の順位で判定するかは未決)"  # A
REASON_NULL_CONDITION = "測定条件が null で、ほかの値と比べない設定"  # F(null_condition_comparable=False のとき)
REASON_DUPLICATE_MODEL = "同じモデルの値がグループに複数ある(モデルの単位が未決のため、どれを使うか決めない)"  # G
REASON_VERSIONS_UNDECIDED = "版が複数あり、最新の版の決め方が指定されていない"  # H
REASON_NO_VALUE_IN_VERSION = "票に使う版に、このモデルの値が無い"  # H(ベンチマーク全体の版から選んだとき)
REASON_CONDITIONS_DISAGREE = "同じベンチマーク・版で、測定条件の違う値の判定が食い違う"  # 暫定の挙動
REASON_NO_JUDGED_VALUE = "判定が付く値がない"
REASON_NO_JUDGED_BENCHMARK = "判定が付くベンチマークがない"  # 規則 5


# ---- 入力の読み方 ----


def _field(record, key):
    """`ScoreRecord`(属性)と dict(キー)の両方から読む。無いキーは None(任意のキーは null と同じ。企画書 §3-3)。"""
    if isinstance(record, Mapping):
        return record.get(key)
    return getattr(record, key, None)


def _checked_records(records):
    """すべてのレコードを `record_from_dict` の検査に通し、`ScoreRecord` のリストにする。
    dict も `ScoreRecord` も、検査を通した後の(正規化された)`ScoreRecord` を返す
    (前後の空白を除き、空文字は None。`ScoreRecord(condition="")` は `condition=None` の値と同じグループになる)。
    読めないものがあれば、全件を見てから `RecordError` で止める(`load_official` と同じ扱い)。"""
    checked = []
    problems = []
    for i, record in enumerate(records):
        where = f"records の {i + 1} 件目"
        if isinstance(record, ScoreRecord):
            raw = asdict(record)
        elif isinstance(record, Mapping):
            raw = record
        else:
            problems.append(f"{where}: ScoreRecord でも dict でもない({type(record).__name__})")
            continue
        try:
            converted = record_from_dict(raw)
        except ValueError as e:
            problems.append(f"{where}: {e}")
            continue
        checked.append(converted)
    if problems:
        raise RecordError(problems)
    return checked


def _check_directions(directions):
    if not isinstance(directions, Mapping):
        raise TypeError("directions は「ベンチマーク名 → 向き」の対応表(dict など)で渡す")
    for name, direction in directions.items():
        if direction not in _DIRECTIONS:
            raise ValueError(f"directions の {name!r} の向きが {_DIRECTIONS} のどれでもない: {direction!r}")


def model_key_name_type_mode(record):
    """G の候補 1:「提供企業＋モデル名＋種類＋推論モード」を 1 つのモデルとする(企画書 §3-3 の値の区別の単位。
    `viewer.grid.ModelRow` と同じ組)。チームの決定ではない。"""
    return (_field(record, "provider"), _field(record, "model"), _field(record, "model_type"), _field(record, "mode"))


def model_key_name(record):
    """G の候補 2:「提供企業＋モデル名」を 1 つのモデルとする(企画書 §4-3 の数え方の単位)。チームの決定ではない。
    種類・推論モードの違う値が同じグループに入ると、そのグループは判定不可になる(`REASON_DUPLICATE_MODEL`)。"""
    return (_field(record, "provider"), _field(record, "model"))


# ---- 戻り値の型 ----


@dataclass(frozen=True)
class GroupKey:
    """比べてよい値の組(規則 1:ベンチマーク・版・単位・測定条件が同じ)。`condition` は `condition_key` を通した後の値。"""

    benchmark: str
    benchmark_version: str | None
    unit: str | None
    condition: object


@dataclass(frozen=True)
class ValueJudgment:
    """1 件の値の判定。`judgment` が None のときは `reason` に判定不可の理由がある(規則 6 の内訳の 1 行)。"""

    record: ScoreRecord
    group: GroupKey
    group_size: int | None  # グループのモデル数(規則 6)。グループに入れなかった値(向き・null の設定)は None
    rank: int | None  # グループの中の順位(1 が最上位。同点は同じ順位)。判定不可なら None
    judgment: str | None  # STRONG・MIDDLE・WEAK
    reason: str | None


@dataclass(frozen=True)
class BenchmarkVote:
    """1 つのモデル・1 つのベンチマーク名の 1 票(H)。`values` には、そのモデルのそのベンチマーク名の値をすべて
    (票に使わなかった版・測定条件の値も)入れる。規則 6 の「グループに入らなかった値も内訳に並べる」のため。"""

    benchmark: str
    version: str | None  # 票に使った版。版が決まらないときは None(`reason` を見る)
    judgment: str | None
    reason: str | None
    values: tuple[ValueJudgment, ...]


@dataclass(frozen=True)
class DomainCell:
    """モデル×領域のセル(I)。`label` は STRONG・MIDDLE・WEAK・MIXED・NOT_JUDGEABLE・NOT_PUBLISHED のどれか。

    - `judged`:判定が付いたベンチマークの件数(規則 4 の「件」)
    - `count`:`label` と同じ判定のベンチマークの件数(強・中・弱のときだけ。それ以外は None)
    - `votes`:ベンチマークごとの票と内訳(規則 6)。未公表なら空
    「強（2/3 件）」は `label`・`count`・`judged` から組み立てる(`cell_text`)。
    """

    model: object
    domain: str
    label: str
    count: int | None
    judged: int
    votes: tuple[BenchmarkVote, ...]
    reason: str | None = None

    @property
    def is_published(self):
        return self.label != NOT_PUBLISHED


@dataclass(frozen=True)
class DomainTable:
    """判定の結果の表。`models` は records に出てくる順、`domains` は対応表に出てくる順。
    `unclassified` は、対応表に無いベンチマークの値(`ScoreRecord`。records の順。R-4 §3 の「未分類」)。"""

    models: tuple
    domains: tuple[str, ...]
    _cells: dict
    unclassified: tuple[ScoreRecord, ...] = ()

    def cell_at(self, model, domain):
        """モデル(`model_key` の戻り値)と領域名で引く。無い組は KeyError。"""
        return self._cells[(model, domain)]

    @property
    def unclassified_benchmarks(self):
        """未分類のベンチマーク名(出てくる順。重なりなし)。対応表に足すかを判断するための一覧。"""
        return tuple(dict.fromkeys(r.benchmark for r in self.unclassified))


# ---- 規則 3(B・D):順位と分け方 ----


def rank_descending(scores):
    """大きいほど上位の順位(A)。同じ値は同じ順位で、上の順位にそろえる(D。例:10・10・8 → 1・1・3)。"""
    return [1 + sum(1 for other in scores if other > s) for s in scores]


def split_thirds(rank, group_size):
    """規則 3(B):k = モデル数 // 3。上位 k が強、下位 k が弱、残りが中。
    同点は `rank_descending` が上の順位にそろえるので、ここでは順位だけで分ける(D)。"""
    k = group_size // 3
    if rank <= k:
        return STRONG
    if rank > group_size - k:
        return WEAK
    return MIDDLE


# ---- 規則 4(E):領域の判定 ----


def majority_vote(judgments):
    """規則 4(E):判定が付いたベンチマークの判定(強・中・弱の並び)から、領域の判定と、その件数を返す。

    - 1 件:その判定(`cell_text` で「強（1/1 件）」のように件数を添える。I)
    - 2 件以上:過半数(件数の半分より多い)が同じ判定ならその判定、割れたら MIXED(件数は None)
    空の並びは呼ばない(呼ぶ側が 判定不可・未公表 にする)。
    """
    if not judgments:
        raise ValueError("判定が 1 件もない(呼ぶ側で 判定不可・未公表 にする)")
    top, top_count = Counter(judgments).most_common(1)[0]
    if top_count * 2 > len(judgments):
        return top, top_count
    return MIXED, None


# ---- 本体 ----


def judge_values(
    records,
    *,
    model_key,
    directions,
    min_group_size=MIN_GROUP_SIZE,
    rank=rank_descending,
    rank_lower=None,
    split=split_thirds,
    condition_key=None,
    null_condition_comparable=True,
):
    """規則 1〜3:値ごとの判定。検査を通した records と同じ順の `ValueJudgment` のリストを返す。

    グループ(規則 1)は (ベンチマーク, 版, 単位, condition_key(測定条件)) が同じ値。`condition_key` が None なら
    測定条件の文字列をそのまま比べ、`None`(null)どうしは同じ条件とみなす(F)。
    `null_condition_comparable=False` なら、測定条件が null の値は比べずに判定不可にする。

    向き(A):`directions` で `HIGHER_IS_BETTER` のベンチマークは `rank` で順位を付ける。`LOWER_IS_BETTER` のものは、
    `rank_lower` が None なら判定不可(水戸の意見)。関数を渡すと、それで順位を付ける(逆の順位で判定するかは未決で、
    その切り替えの余地として置く)。`directions` に無いベンチマークは判定不可。

    判定不可にするもの(理由は `reason`):
    - 向きを確かめていない・小さいほど良いベンチマークの値(A。`group_size` は None)
    - グループのモデル数が `min_group_size` 未満(規則 2)
    - 同じモデル(`model_key` が同じ)の値がグループに 2 件以上(G が未決なので、どれを使うか決めず、グループ全体を判定不可)
    """
    _check_directions(directions)
    records = _checked_records(records)
    to_condition = condition_key if condition_key is not None else (lambda c: c)

    keys = []
    skipped = {}  # グループに入れない値の位置 → 理由
    groups = {}
    for i, record in enumerate(records):
        key = GroupKey(
            benchmark=record.benchmark,
            benchmark_version=record.benchmark_version,
            unit=record.unit,
            condition=to_condition(record.condition),
        )
        keys.append(key)
        direction = directions.get(record.benchmark)
        if direction is None:
            skipped[i] = REASON_DIRECTION_UNKNOWN
        elif direction == LOWER_IS_BETTER and rank_lower is None:
            skipped[i] = REASON_LOWER_IS_BETTER
        elif record.condition is None and not null_condition_comparable:
            skipped[i] = REASON_NULL_CONDITION
        else:
            groups.setdefault(key, []).append(i)

    results = [None] * len(keys)
    for i, reason in skipped.items():
        results[i] = ValueJudgment(records[i], keys[i], None, None, None, reason)
    for key, indexes in groups.items():
        members = [model_key(records[i]) for i in indexes]
        size = len(set(members))
        if size != len(members):
            reason = REASON_DUPLICATE_MODEL
        elif size < min_group_size:
            reason = REASON_FEW_MODELS.format(min=min_group_size)
        else:
            reason = None
        if reason is not None:
            for i in indexes:
                results[i] = ValueJudgment(records[i], key, size, None, None, reason)
            continue
        ranker = rank_lower if directions[key.benchmark] == LOWER_IS_BETTER else rank
        ranks = ranker([records[i].score for i in indexes])
        for i, r in zip(indexes, ranks):
            results[i] = ValueJudgment(records[i], key, size, r, split(r, size), None)
    return results


def _vote(benchmark, values, benchmark_versions, pick_version):
    """H:1 つのモデル・1 つのベンチマーク名の 1 票。

    - ベンチマーク全体で版が 1 つ:その版の値で票を決める
    - ベンチマーク全体で版が複数:`pick_version` が None なら判定不可(「最新」の決め方と、どの範囲の版から選ぶかが
      未決のため。そのモデルが版を 1 つしか持たなくても判定不可にする。そのモデルの版で選ぶ読みを黙って採らないため)。
      関数なら `pick_version(model_versions, benchmark_versions)` を呼ぶ。
      `model_versions` はそのモデルが値を持つ版、`benchmark_versions` は渡された records 全体でそのベンチマーク名に
      出てくる版(どちらもタプルで、None を含みうる。records に出てくる順)。返った版の値だけで票を決める。
      `benchmark_versions` に無い版を返したら ValueError。そのモデルの値が無い版なら判定不可(`REASON_NO_VALUE_IN_VERSION`)
    - 使う版の中に、測定条件の違う値(別のグループ)が複数あるとき:判定が付いたものがすべて同じならその判定、
      食い違えば判定不可(暫定。モジュールの docstring)。判定が付かない値は票に数えない
    """
    model_versions = tuple(dict.fromkeys(v.group.benchmark_version for v in values))
    if len(benchmark_versions) == 1:
        version = benchmark_versions[0]
    elif pick_version is None:
        return BenchmarkVote(benchmark, None, None, REASON_VERSIONS_UNDECIDED, values)
    else:
        version = pick_version(model_versions, benchmark_versions)
        if version not in benchmark_versions:
            raise ValueError(f"pick_version が、どのモデルにも値の無い版を返した: {version!r}(候補: {benchmark_versions!r})")
        if version not in model_versions:
            return BenchmarkVote(benchmark, version, None, REASON_NO_VALUE_IN_VERSION, values)
    chosen = [v for v in values if v.group.benchmark_version == version]
    judged = {v.judgment for v in chosen if v.judgment is not None}
    if len(judged) == 1:
        return BenchmarkVote(benchmark, version, judged.pop(), None, values)
    if judged:
        return BenchmarkVote(benchmark, version, None, REASON_CONDITIONS_DISAGREE, values)
    reasons = "; ".join(dict.fromkeys(v.reason for v in chosen if v.reason)) or REASON_NO_JUDGED_VALUE
    return BenchmarkVote(benchmark, version, None, reasons, values)


def judge_domains(
    records,
    domains,
    *,
    model_key,
    directions,
    min_group_size=MIN_GROUP_SIZE,
    rank=rank_descending,
    rank_lower=None,
    split=split_thirds,
    condition_key=None,
    null_condition_comparable=True,
    pick_version=None,
    decide=majority_vote,
):
    """モデル×領域の判定の表(`DomainTable`)を返す。規則 1〜6 と、未決の点 A〜I の切り替え(モジュールの docstring の表)。

    `model_key`(G)と `directions`(A)は必ず渡す(未決のため既定値を置かない。理由はモジュールの docstring)。
    例:`model_key=model_key_name_type_mode, directions={"Bench-P": HIGHER_IS_BETTER}`。
    モデルは records に出てくるすべて(対応表に無いベンチマークだけのモデルも、全領域が「未公表」の行になる)。

    セル(規則 4・5):
    - そのモデルが領域内のベンチマークの値を 1 つも持たない → NOT_PUBLISHED
    - 値はあるが、判定が付いたベンチマークが 0 件 → NOT_JUDGEABLE
    - 判定が付いたベンチマークが 1 件以上 → `decide`(既定 `majority_vote`)の結果
    """
    if not isinstance(domains, Mapping):
        raise TypeError("domains は「ベンチマーク名 → 領域名」の対応表(dict など)で渡す")
    domain_names = tuple(dict.fromkeys(domains.values()))
    values = judge_values(
        records,
        model_key=model_key,
        directions=directions,
        min_group_size=min_group_size,
        rank=rank,
        rank_lower=rank_lower,
        split=split,
        condition_key=condition_key,
        null_condition_comparable=null_condition_comparable,
    )

    models = []
    unclassified = []
    versions_of = {}  # ベンチマーク名 → records 全体に出てくる版
    by_cell = {}  # (モデル, 領域) → {ベンチマーク名: [ValueJudgment]}
    for value in values:
        model = model_key(value.record)
        models.append(model)
        benchmark = value.group.benchmark
        versions_of.setdefault(benchmark, {})[value.group.benchmark_version] = None
        domain = domains.get(benchmark)
        if domain is None:  # 対応表に無いベンチマーク(R-4 §3 の「未分類」)
            unclassified.append(value.record)
            continue
        by_cell.setdefault((model, domain), {}).setdefault(benchmark, []).append(value)
    models = tuple(dict.fromkeys(models))

    cells = {}
    for model in models:
        for domain in domain_names:
            benchmarks = by_cell.get((model, domain))
            if not benchmarks:
                cells[(model, domain)] = DomainCell(model, domain, NOT_PUBLISHED, None, 0, ())
                continue
            votes = tuple(
                _vote(name, tuple(vs), tuple(versions_of[name]), pick_version) for name, vs in benchmarks.items()
            )
            judgments = [v.judgment for v in votes if v.judgment is not None]
            if not judgments:
                cells[(model, domain)] = DomainCell(
                    model, domain, NOT_JUDGEABLE, None, 0, votes, REASON_NO_JUDGED_BENCHMARK
                )
                continue
            label, count = decide(tuple(judgments))
            cells[(model, domain)] = DomainCell(model, domain, label, count, len(judgments), votes)
    return DomainTable(models, domain_names, cells, tuple(unclassified))


# ---- 表示用の文字列(画面の文言の組み立ての手前まで) ----


def cell_text(cell):
    """セルの短い文字列(I)。強・中・弱は「強（2/3 件）」、混在は「混在（強 1・中 1・弱 1）」(暫定)、
    判定不可・未公表はその言葉だけ。理由や内訳は `cell.votes` から画面が出す。"""
    if cell.label in (STRONG, MIDDLE, WEAK):
        return f"{cell.label}（{cell.count}/{cell.judged} 件）"
    if cell.label == MIXED:
        counts = Counter(v.judgment for v in cell.votes if v.judgment is not None)
        parts = "・".join(f"{j} {counts[j]}" for j in (STRONG, MIDDLE, WEAK) if counts[j])
        return f"{MIXED}（{parts}）"
    return cell.label

"""ベンチマーク→領域の対応表(`data/domains.json`。企画書 §3-3)の読み込み・検査と、領域の引き当て。

対応表の中身は R-4(docs/research/r4-benchmark-domains.md)§2 の写しで、**全体が【案】**(R-4 の冒頭の注意)。
ファイルの `status` が `proposal` であることを検査し、画面はそれを前提に「分類は案」と出す。
領域の名前・数・分類の理由と確認状況の正は R-4 で、このファイルは形と引き当ての決まりだけを持つ。

引き当ての決まり:
- 正式データの `benchmark` の文字列と、対応表の行の `benchmark`・`aliases` との**完全一致だけ**
  (大文字小文字の無視・空白の無視・部分一致・あいまいな一致はしない)
- 版(`benchmark_version`)は見ない。対応表のキーは、版を除いたベンチマーク名(R-4 §3 の【案】)
- 対応表に無いベンチマークは「未分類」(R-4 §3)
- 領域ごとの「強・中・弱」・総合スコア・平均・順位は、ここでは扱わない(企画書 §8 Q-6 で【未決】)

ロジック層なので `streamlit`・`requests`・`pandas` は import しない(tests/test_viewer_records.py で確かめる)。
"""

import json
from dataclasses import dataclass
from pathlib import Path

# 対応表に無いベンチマークの領域(R-4 §3)。表の並びでは、どの領域よりも後ろに置く
UNCLASSIFIED = "未分類"

# ファイルの外形のキーと、`benchmarks` の 1 行のキー。これ以外のキーは誤り(正式データの検査と同じ流儀)
TOP_KEYS = ("status", "source", "note", "domains", "benchmarks")
ROW_KEYS = ("benchmark", "domain", "aliases")
# 対応表の状態。画面は「分類は案」と固定の文で出すので、案(proposal)以外は受け付けない。
# 案でなくなったら、画面の文(viewer/app.py)と一緒にここを直す
STATUS = "proposal"


class DomainError(ValueError):
    """対応表を読めない。`problems` に、何が読めないかを 1 件ずつ持つ(`records.RecordError` と同じ形)。"""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


@dataclass(frozen=True)
class DomainMap:
    """読み込んだ対応表。`domains` は対応表の順(R-4 §2 の順)。`_lookup` は「名前・別名 → 領域」。"""

    domains: tuple[str, ...]
    _lookup: dict

    @property
    def choices(self):
        """絞り込みの選択肢。対応表の領域の順で、最後に「未分類」。"""
        return self.domains + (UNCLASSIFIED,)

    def domain_of(self, benchmark):
        """ベンチマーク名(版を除いたもの)の領域。完全一致で引き、無ければ「未分類」。"""
        return self._lookup.get(benchmark, UNCLASSIFIED)

    def order(self, domain):
        """表で並べるときの領域の順番(0 から)。「未分類」は最後。"""
        return self.choices.index(domain)


# 対応表を渡さないときの既定(すべて「未分類」)
EMPTY = DomainMap((), {})


def _is_name(value):
    """名前として使える文字列か。前後の空白は、正式データ側で落とされるので、付いていると決して一致しない。"""
    return isinstance(value, str) and value != "" and value == value.strip()


def _key_problems(raw, keys, where):
    problems = []
    missing = [k for k in keys if k not in raw]
    if missing:
        problems.append(f"{where}キーが足りない: " + "・".join(f"`{k}`" for k in missing))
    extra = [k for k in raw if k not in keys]
    if extra:
        problems.append(f"{where}知らないキーがある: " + "・".join(f"`{k}`" for k in extra))
    return problems


def domain_map_from_dict(data):
    """JSON(dict)を `DomainMap` にする。読めないところがあれば、全部を集めてから `DomainError` で止める。"""
    if not isinstance(data, dict):
        raise DomainError(["オブジェクトでない"])
    problems = _key_problems(data, TOP_KEYS, "")
    if problems:
        raise DomainError(problems)

    if data["status"] != STATUS:
        problems.append(f"`status` が {STATUS} でない(画面は、対応表が案であることを前提に文を出す): {data['status']!r}")
    for key in ("source", "note"):
        if not isinstance(data[key], str) or not data[key].strip():
            problems.append(f"`{key}` が空でない文字列でない")

    domains = data["domains"]
    if not isinstance(domains, list) or not domains:
        problems.append("`domains` が空か、配列でない")
        domains = []
    seen_domains = []
    for name in domains:
        if not _is_name(name):
            problems.append(f"`domains` の名前が、前後に空白の無い文字列でない: {name!r}")
        elif name == UNCLASSIFIED:
            problems.append(f"`domains` に「{UNCLASSIFIED}」は置けない(対応表に無いベンチマークの領域の名前)")
        elif name in seen_domains:
            problems.append(f"`domains` に同じ名前が 2 回ある: {name}")
        else:
            seen_domains.append(name)

    rows = data["benchmarks"]
    if not isinstance(rows, list):
        problems.append("`benchmarks` が配列でない")
        rows = []
    lookup = {}
    first_seen = {}  # 名前・別名 → "N 件目"
    for i, row in enumerate(rows):
        where = f"`benchmarks` の {i + 1} 件目"
        if not isinstance(row, dict):
            problems.append(f"{where}: オブジェクトでない")
            continue
        row_problems = _key_problems(row, ROW_KEYS, f"{where}: ")
        if row_problems:
            problems.extend(row_problems)
            continue
        names = [row["benchmark"]]
        if not _is_name(row["benchmark"]):
            problems.append(f"{where}: `benchmark` が、前後に空白の無い文字列でない: {row['benchmark']!r}")
        aliases = row["aliases"]
        if not isinstance(aliases, list) or not all(_is_name(a) for a in aliases):
            problems.append(f"{where}: `aliases` が、前後に空白の無い文字列の配列でない: {aliases!r}")
        else:
            names += aliases
        domain = row["domain"]
        if domain not in seen_domains:
            problems.append(f"{where}: `domains` に無い領域を指している: {domain!r}")
        for name in names:
            if not isinstance(name, str):
                continue
            if name in first_seen:
                problems.append(f"{where}: 名前・別名の重複({name}。{first_seen[name]}と同じ)")
                continue
            first_seen[name] = f"{i + 1} 件目"
            lookup[name] = domain
    if problems:
        raise DomainError(problems)
    return DomainMap(tuple(seen_domains), lookup)


def load_domains(path):
    """対応表のファイルを読む。ファイルが無いときは `FileNotFoundError`(ディレクトリなら `IsADirectoryError`)。
    対応表が無いことを「全部が未分類」に見せないため。読めないときは `DomainError`(理由にファイル名を付ける)。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"領域の対応表が無い: {path}")
    if path.is_dir():
        raise IsADirectoryError(f"領域の対応表のパスがディレクトリ: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    # RecursionError：深い入れ子の JSON(records.load_official の注と同じ)
    except (OSError, ValueError, RecursionError) as e:
        raise DomainError([f"{path.name}: 読み込めない: {e}"]) from None
    try:
        return domain_map_from_dict(data)
    except DomainError as e:
        raise DomainError([f"{path.name}: {p}" for p in e.problems]) from None

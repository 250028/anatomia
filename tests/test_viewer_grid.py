import unittest
from dataclasses import replace
from pathlib import Path

import viewer.grid
from viewer.domains import UNCLASSIFIED, load_domains
from viewer.grid import (
    CONDITION_MARK,
    DOMAIN_LABEL,
    NOT_PUBLISHED,
    build_grid,
    cell_position,
    companies,
    count_by_domain,
    detail_items,
    filter_by_company,
    format_score,
    PROVIDER_ROW,
    TRANSPOSED_FIRST_COLUMN,
    label_conflicts,
    last_retrieved_by_company,
    pair_at,
    prefers_transposed,
    table_header,
    table_rows,
    transposed_header,
    transposed_rows,
)

from viewer.records import load_official

# ダミー社A・Bの合成データ(実在しない会社・モデル。出典は example.com)
FIXTURES = Path(__file__).parent / "fixtures" / "official"
# ダミーの対応表(ダミー領域1：Bench-V・Bench-W、ダミー領域2：Bench-X・Bench-Y(別名)、ダミー領域3：値なし、Bench-Z は未分類)
DOMAINS = Path(__file__).parent / "fixtures" / "domains.json"


def find_row(grid, model, model_type=None, mode=None):
    return next(
        i for i, r in enumerate(grid.rows) if (r.model, r.model_type, r.mode) == (model, model_type, mode)
    )


def find_col(grid, benchmark, version=None):
    return next(
        j for j, c in enumerate(grid.columns) if (c.benchmark, c.benchmark_version) == (benchmark, version)
    )


class GridTest(unittest.TestCase):
    def setUp(self):
        self.records = load_official(FIXTURES)
        self.grid = build_grid(self.records)

    def test_行は_モデル_種類_推論モードの組で区別される(self):
        a1 = [r for r in self.grid.rows if r.model == "Model-A1"]
        self.assertEqual(
            {(r.model_type, r.mode) for r in a1},
            {("Reasoning", "High"), ("Reasoning", "Non-Think"), ("Instruct", None)},
        )

    def test_列はベンチマークと版の組で区別される(self):
        self.assertEqual(
            [c.label for c in self.grid.columns],
            ["Bench-V 2.1", "Bench-W", "Bench-X", "Bench-Y", "Bench-Z"],
        )

    def test_値の無い組は未公表になる(self):
        cell = self.grid.cell(find_row(self.grid, "Model-A2"), find_col(self.grid, "Bench-Y"))
        self.assertFalse(cell.is_published)
        self.assertEqual(cell.text, NOT_PUBLISHED)
        self.assertEqual(detail_items(cell), [])

    def test_未公表は_値が_0_のセルと区別される(self):
        records = [r for r in self.records if r.model == "Model-A2"]
        records = [replace(records[0], score=0.0)]
        cell = build_grid(records).cell(0, 0)
        self.assertTrue(cell.is_published)
        self.assertEqual(cell.text, "0%")

    def test_スコアの表示は単位に従う(self):
        g = self.grid
        row = find_row(g, "Model-A1", "Reasoning", "High")
        self.assertEqual(g.cell(row, find_col(g, "Bench-X")).text, "81.5%")
        self.assertEqual(g.cell(row, find_col(g, "Bench-Y")).text, "1650 Elo")
        self.assertEqual(g.cell(row, find_col(g, "Bench-Z")).text, "0.82")

    def test_推論モードの違う同じモデルは別の行になる(self):
        g = self.grid
        col = find_col(g, "Bench-X")
        high = g.cell(find_row(g, "Model-A1", "Reasoning", "High"), col).text
        non_think = g.cell(find_row(g, "Model-A1", "Reasoning", "Non-Think"), col).text
        self.assertEqual((high, non_think), ("81.5%", "70.2%"))

    def test_測定条件だけが違う値は同じセルに入り_印が付く(self):
        g = self.grid
        cell = g.cell(find_row(g, "Model-A1", "Reasoning", "High"), find_col(g, "Bench-W"))
        self.assertEqual(len(cell.records), 2)
        self.assertEqual(cell.text, "55.1% / 63.4%" + CONDITION_MARK)

    def test_行の並びはスコアで変わらない(self):
        rows = [(r.provider, r.model, r.model_type or "", r.mode or "") for r in self.grid.rows]
        self.assertEqual(rows, sorted(rows))
        self.assertEqual(build_grid(list(reversed(self.records))).rows, self.grid.rows)

    def test_セルの中の値の並びは入力の順に依らず測定条件の文字列順(self):
        g = self.grid
        row, col = find_row(g, "Model-A1", "Reasoning", "High"), find_col(g, "Bench-W")
        expected = g.cell(row, col).text
        self.assertEqual(expected, "55.1% / 63.4%" + CONDITION_MARK)
        for records in (list(reversed(self.records)), sorted(self.records, key=lambda r: -r.score)):
            other = build_grid(records)
            self.assertEqual(other.cell(find_row(other, "Model-A1", "Reasoning", "High"), find_col(other, "Bench-W")).text, expected)

    def test_条件なしの値が先_条件ありは条件の文字列順(self):
        base = self.records[0]
        records = [replace(base, condition=c, score=s) for c, s in (("b", 3.0), (None, 9.0), ("a", 1.0))]
        for rs in (records, list(reversed(records))):
            self.assertEqual([r.condition for r in build_grid(rs).cell(0, 0).records], [None, "a", "b"])

    def test_位置でなく行と列の値でセルを引ける(self):
        g = self.grid
        row, col = find_row(g, "Model-A1", "Reasoning", "High"), find_col(g, "Bench-X")
        self.assertIs(g.cell_at(g.rows[row], g.columns[col]), g.cell(row, col))
        self.assertEqual(g.cell_at(g.rows[row], g.columns[col]).text, "81.5%")

    def test_絞り込みで消えた行や列を_cell_at_で引くと_KeyError(self):
        only_b = build_grid(filter_by_company(self.records, ["ダミー社B"]))
        gone_row = self.grid.rows[find_row(self.grid, "Model-A2")]
        gone_col = self.grid.columns[find_col(self.grid, "Bench-V", "2.1")]
        with self.assertRaises(KeyError):
            only_b.cell_at(gone_row, only_b.columns[0])
        with self.assertRaises(KeyError):
            only_b.cell_at(only_b.rows[0], gone_col)

    def test_合計_平均_順位の列が無い(self):
        header = table_header(self.grid)
        self.assertEqual(header[:4], ["提供企業", "モデル", "種類", "推論モード"])
        self.assertEqual(len(header), 4 + len(self.grid.columns))
        for word in ("合計", "平均", "順位", "総合", "Total", "Average", "Rank"):
            with self.subTest(word=word):
                self.assertFalse(any(word.lower() in h.lower() for h in header))
        for row in table_rows(self.grid):
            self.assertEqual(len(row), len(header))

    def test_表の行の文字列にスコア以外の数値の列が混ざらない(self):
        rows = table_rows(self.grid)
        r = rows[1 + find_row(self.grid, "Model-A2")]  # 1 行目は領域の行
        self.assertEqual(r[:4], ["ダミー社A", "Model-A2", "（なし）", "（なし）"])
        self.assertEqual(r[4:], ["72.5%", NOT_PUBLISHED, "58%", NOT_PUBLISHED, NOT_PUBLISHED])

    def test_データの無いときは空の表になる(self):
        g = build_grid([])
        self.assertEqual((g.rows, g.columns), ((), ()))
        self.assertEqual(table_rows(g), [[DOMAIN_LABEL, "", "", ""]])  # 領域の行(見出しだけ)が残り、モデルの行は無い


class CompanyTest(unittest.TestCase):
    def setUp(self):
        self.records = load_official(FIXTURES)

    def test_企業の一覧(self):
        self.assertEqual(companies(self.records), ["ダミー社A", "ダミー社B"])

    def test_企業で絞り込む(self):
        only_b = filter_by_company(self.records, ["ダミー社B"])
        self.assertEqual({r.provider for r in only_b}, {"ダミー社B"})
        self.assertEqual({r.provider for r in build_grid(only_b).rows}, {"ダミー社B"})

    def test_絞り込みなしは全件_空の選択は0件(self):
        self.assertEqual(len(filter_by_company(self.records, None)), len(self.records))
        self.assertEqual(filter_by_company(self.records, []), [])

    def test_企業名の文字列を_1_つ渡すと_TypeError(self):
        for bad in ("ダミー社A", b"x"):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    filter_by_company(self.records, bad)

    def test_集合やタプルでも絞り込める(self):
        for selected in ({"ダミー社A"}, ("ダミー社A",), iter(["ダミー社A"])):
            with self.subTest(selected=type(selected).__name__):
                self.assertEqual({r.provider for r in filter_by_company(self.records, selected)}, {"ダミー社A"})

    def test_絞り込むと他社だけにあるベンチマークの列は消える(self):
        only_b = build_grid(filter_by_company(self.records, ["ダミー社B"]))
        self.assertEqual([c.label for c in only_b.columns], ["Bench-X", "Bench-Y", "Bench-Z"])


class DetailTest(unittest.TestCase):
    def setUp(self):
        self.grid = build_grid(load_official(FIXTURES))

    def test_詳細に出典_取得日_取得者_取得方法_測定条件が出る(self):
        g = self.grid
        cell = g.cell(find_row(g, "Model-A1", "Reasoning", "High"), find_col(g, "Bench-W"))
        details = detail_items(cell)
        self.assertEqual(len(details), 2)
        d = dict(details[0])
        self.assertEqual(d["出典 URL"], "https://example.com/dummy-a/modelcard")
        self.assertEqual(d["取得日"], "2026-10-01")
        self.assertEqual(d["取得者"], "ダミー")
        self.assertEqual(d["取得方法"], "スクリプト")
        self.assertEqual(d["測定条件"], "Pass@1")
        self.assertEqual(dict(details[1])["測定条件"], "Pass@5")
        self.assertNotIn("sha", d)

    def test_測定条件が無いときは記載なしと出す(self):
        g = self.grid
        cell = g.cell(find_row(g, "Model-A2"), find_col(g, "Bench-X"))
        self.assertEqual(dict(detail_items(cell)[0])["測定条件"], "記載なし")

    def test_sha_は付いている値にだけ出る(self):
        g = self.grid
        cell = g.cell(find_row(g, "Model-B1"), find_col(g, "Bench-X"))
        self.assertEqual(dict(detail_items(cell)[0])["sha"], "0123456789abcdef0123456789abcdef01234567")

    def test_手入力の取得方法は表示名に訳される(self):
        g = self.grid
        cell = g.cell(find_row(g, "Model-A2"), find_col(g, "Bench-V", "2.1"))
        self.assertEqual(dict(detail_items(cell)[0])["取得方法"], "手入力")

    def test_詳細に説明文_生の表記_順位は出ない(self):
        # 領域は、ベンチマークの領域の絞り込みと並びを足したときに、ベンチマークの次に足した(対応表を渡さなければ未分類)。
        # 説明文・生の表記(raw_value)・順位・強中弱は、今も出さない
        g = self.grid
        cell = g.cell(find_row(g, "Model-A1", "Reasoning", "High"), find_col(g, "Bench-X"))
        items = detail_items(cell)[0]
        labels = [k for k, _ in items]
        self.assertEqual(
            labels, ["モデル", "ベンチマーク", "領域", "スコア", "測定条件", "出典 URL", "取得日", "取得者", "取得方法"]
        )
        self.assertEqual(dict(items)["領域"], UNCLASSIFIED)


class LastRetrievedTest(unittest.TestCase):
    def test_企業ごとの最終取得日(self):
        self.assertEqual(
            last_retrieved_by_company(load_official(FIXTURES)),
            {"ダミー社A": "2026-10-01", "ダミー社B": "2026-10-15"},
        )

    def test_企業の中では新しいほうを取る(self):
        records = load_official(FIXTURES)
        newer = replace(records[0], retrieved_at="2026-10-28")
        self.assertEqual(last_retrieved_by_company(records + [newer])["ダミー社A"], "2026-10-28")

    def test_新しい日付のレコードが先頭にあっても新しい日付が残る(self):
        records = load_official(FIXTURES)
        newer = replace(records[0], retrieved_at="2026-10-28")
        self.assertEqual(last_retrieved_by_company([newer] + records)["ダミー社A"], "2026-10-28")

    def test_絞り込んだ企業だけを数えれば他社は出ない(self):
        only_a = filter_by_company(load_official(FIXTURES), ["ダミー社A"])
        self.assertEqual(list(last_retrieved_by_company(only_a)), ["ダミー社A"])


class FormatScoreTest(unittest.TestCase):
    def test_整数の浮動小数は小数点を付けない(self):
        r = load_official(FIXTURES)[0]
        self.assertEqual(format_score(replace(r, score=65.0, unit="%")), "65%")
        self.assertEqual(format_score(replace(r, score=0.5, unit=None)), "0.5")


class TransposeTest(unittest.TestCase):
    """ベンチマークを行にした向き(transposed_header・transposed_rows・pair_at)。"""

    def setUp(self):
        self.records = load_official(FIXTURES)
        self.grid = build_grid(self.records)

    def test_見出しは_ベンチマークの列とモデルの数だけの列(self):
        g = self.grid
        header = transposed_header(g)
        self.assertEqual(header[:2], [TRANSPOSED_FIRST_COLUMN, DOMAIN_LABEL])  # 2 列目は領域の列
        self.assertEqual(header[2:], [row.label for row in g.rows])
        self.assertEqual(len(header), 2 + len(g.rows))

    def test_行は_提供企業の行とベンチマークの数だけの行(self):
        g = self.grid
        rows = transposed_rows(g)
        self.assertEqual(len(rows), 1 + len(g.columns))
        self.assertEqual(rows[0], [PROVIDER_ROW, ""] + [row.provider for row in g.rows])  # 領域の列は空
        self.assertEqual([r[0] for r in rows[1:]], [c.label for c in g.columns])
        self.assertTrue(all(len(r) == len(transposed_header(g)) for r in rows))

    def test_入れ替えても_同じモデルとベンチマークの組のセルは同じ中身(self):
        # もう一度入れ替えると元の表のスコアの部分に戻る、に当たる確認
        g = self.grid
        # 位置は、元の向きは 1 行目が領域の行、入れ替えた向きは 1 行目が提供企業の行・1〜2 列目がベンチマーク名と領域
        normal = table_rows(g)[1:]
        transposed = transposed_rows(g)
        fixed = len(table_header(g)) - len(g.columns)
        for i in range(len(g.rows)):
            for j in range(len(g.columns)):
                with self.subTest(row=g.rows[i].label, column=g.columns[j].label):
                    self.assertEqual(transposed[1 + j][2 + i], normal[i][fixed + j])
                    self.assertEqual(transposed[1 + j][2 + i], g.cell(i, j).text)
        back = [[transposed[1 + j][2 + i] for j in range(len(g.columns))] for i in range(len(g.rows))]
        self.assertEqual(back, [r[fixed:] for r in normal])

    def test_入れ替えても_未公表と印の数は変わらない(self):
        g = self.grid
        normal = [c for r in table_rows(g)[1:] for c in r[4:]]  # 領域の行を除く
        transposed = [c for r in transposed_rows(g)[1:] for c in r[2:]]  # 領域の列を除く
        self.assertEqual(len(normal), len(transposed))
        self.assertEqual(normal.count(NOT_PUBLISHED), transposed.count(NOT_PUBLISHED))
        self.assertEqual(sum(CONDITION_MARK in c for c in normal), sum(CONDITION_MARK in c for c in transposed))
        self.assertGreater(normal.count(NOT_PUBLISHED), 0)

    def test_名指しのセル_未公表と印付き(self):
        g = self.grid
        rows = transposed_rows(g)
        i = find_row(g, "Model-A1", "Reasoning", "High")
        self.assertEqual(rows[1 + find_col(g, "Bench-W")][2 + i], "55.1% / 63.4%" + CONDITION_MARK)
        b2 = find_row(g, "Model-B2", None, "Max")
        self.assertEqual(rows[1 + find_col(g, "Bench-X")][2 + b2], NOT_PUBLISHED)

    def test_選んだセルは_どちらの向きでも同じ組になる(self):
        g = self.grid
        for i, row in enumerate(g.rows):
            for j, column in enumerate(g.columns):
                with self.subTest(row=row.label, column=column.label):
                    self.assertEqual(pair_at(g, 1 + i, column.label), (row, column))  # 1 行目は領域の行
                    self.assertEqual(pair_at(g, 1 + j, row.label, transposed=True), (row, column))

    def test_スコアのセルでないときは_None(self):
        g = self.grid
        self.assertIsNone(pair_at(g, 1, "モデル"))
        self.assertIsNone(pair_at(g, 0, g.columns[0].label))  # 領域の行
        self.assertIsNone(pair_at(g, 1 + len(g.rows), g.columns[0].label))
        self.assertIsNone(pair_at(g, -1, g.columns[0].label))
        self.assertIsNone(pair_at(g, 1, "存在しない列"))
        label = g.rows[0].label
        self.assertIsNone(pair_at(g, 0, label, transposed=True))  # 提供企業の行
        self.assertIsNone(pair_at(g, 1, TRANSPOSED_FIRST_COLUMN, transposed=True))
        self.assertIsNone(pair_at(g, 1, DOMAIN_LABEL, transposed=True))  # 領域の列
        self.assertIsNone(pair_at(g, 1 + len(g.columns), label, transposed=True))
        self.assertIsNone(pair_at(g, 1, "存在しない列", transposed=True))

    def test_未公表のセルの表示は引数で変えられ_意味と値のセルは変わらない(self):
        g = self.grid
        default, marked = table_rows(g), table_rows(g, not_published="—")
        t_default, t_marked = transposed_rows(g), transposed_rows(g, not_published="—")
        for before, after in ((default, marked), (t_default, t_marked)):
            for row_before, row_after in zip(before, after):
                for x, y in zip(row_before, row_after):
                    self.assertEqual(y, "—" if x == NOT_PUBLISHED else x)
        self.assertEqual(sum(r.count("—") for r in marked), sum(r.count("—") for r in t_marked))
        self.assertEqual(g.cell(find_row(g, "Model-B2", None, "Max"), find_col(g, "Bench-X")).text, NOT_PUBLISHED)

    def test_セルの位置は_pair_at_の逆(self):
        g = self.grid
        for transposed in (False, True):
            rows = transposed_rows(g) if transposed else table_rows(g)
            header = transposed_header(g) if transposed else table_header(g)
            for row in g.rows:
                for column in g.columns:
                    r, c = cell_position(g, row, column, transposed)
                    with self.subTest(transposed=transposed, row=row.label, column=column.label):
                        self.assertEqual(pair_at(g, r, header[c], transposed=transposed), (row, column))
                        self.assertEqual(rows[r][c], g.cell_at(row, column).text)

    def test_ダミーでは見出しは重ならない(self):
        self.assertEqual(label_conflicts(self.grid), [])
        self.assertEqual(label_conflicts(self.grid, transposed=True), [])

    def test_別の企業に同じ名前のモデルがあると_入れ替えた向きだけ重なる(self):
        r = self.records[0]
        g = build_grid([r, replace(r, provider="ダミー社Z")])
        self.assertEqual(label_conflicts(g), [])
        self.assertEqual(label_conflicts(g, transposed=True), [g.rows[0].label])

    def test_版の書き方が混ざると_どちらの向きでも重なる(self):
        r = self.records[0]
        g = build_grid([replace(r, benchmark="Bench A 2.1"), replace(r, benchmark="Bench A", benchmark_version="2.1")])
        self.assertEqual(label_conflicts(g), ["Bench A 2.1"])
        self.assertEqual(label_conflicts(g, transposed=True), ["Bench A 2.1"])

    def test_既定の向きは_ベンチマークのほうが多いときだけ入れ替える(self):
        self.assertFalse(prefers_transposed(self.grid))  # モデル 6・ベンチマーク 5
        only_b = build_grid(filter_by_company(self.records, ["ダミー社B"]))  # モデル 2・ベンチマーク 3
        self.assertTrue(prefers_transposed(only_b))
        r = self.records[0]
        same = build_grid([r, replace(r, model="Model-Z", benchmark="Bench-Q")])  # 2 と 2
        self.assertEqual((len(same.rows), len(same.columns)), (2, 2))
        self.assertFalse(prefers_transposed(same))


class DomainTest(unittest.TestCase):
    """領域での絞り込みと並び(build_grid の domains・selected_domains)、領域の行・列、詳細の領域。"""

    def setUp(self):
        self.records = load_official(FIXTURES)
        self.domains = load_domains(DOMAINS)
        self.grid = build_grid(self.records, self.domains)

    def labels(self, grid):
        return [c.label for c in grid.columns]

    def test_列の領域は_版を見ず_別名でも引き_無ければ未分類(self):
        g = self.grid
        found = {c.label: g.domain_of(c) for c in g.columns}
        self.assertEqual(
            found,
            {
                "Bench-V 2.1": "ダミー領域1",  # 版が付いていても、版を除いた名前で引く
                "Bench-W": "ダミー領域1",
                "Bench-X": "ダミー領域2",
                "Bench-Y": "ダミー領域2",  # 対応表の行の名前は「Bench Y」で、Bench-Y は別名
                "Bench-Z": UNCLASSIFIED,
            },
        )

    def test_対応表を渡さなければ全部が未分類で_並びは名前順のまま(self):
        g = build_grid(self.records)
        self.assertEqual({g.domain_of(c) for c in g.columns}, {UNCLASSIFIED})
        self.assertEqual(self.labels(g), ["Bench-V 2.1", "Bench-W", "Bench-X", "Bench-Y", "Bench-Z"])

    def test_列は領域の順_領域の中は名前順_未分類は最後(self):
        # 名前順と領域の順が食い違う対応表で、領域の順が先に効くことを確かめる
        from viewer.domains import domain_map_from_dict

        domains = domain_map_from_dict({
            "status": "proposal", "source": "x", "note": "x",
            "domains": ["後の名前の領域", "先の名前の領域"],
            "benchmarks": [
                {"benchmark": "Bench-Y", "domain": "後の名前の領域", "aliases": []},
                {"benchmark": "Bench-X", "domain": "後の名前の領域", "aliases": []},
                {"benchmark": "Bench-V", "domain": "先の名前の領域", "aliases": []},
            ],
        })
        g = build_grid(self.records, domains)
        self.assertEqual(self.labels(g), ["Bench-X", "Bench-Y", "Bench-V 2.1", "Bench-W", "Bench-Z"])
        self.assertEqual(
            [g.domain_of(c) for c in g.columns],
            ["後の名前の領域", "後の名前の領域", "先の名前の領域", UNCLASSIFIED, UNCLASSIFIED],
        )

    def test_並びはスコアで変わらない(self):
        reordered = build_grid(sorted(self.records, key=lambda r: -r.score), self.domains)
        self.assertEqual(reordered.columns, self.grid.columns)
        self.assertEqual(reordered.rows, self.grid.rows)

    def test_領域で絞ると_その領域の列だけになり_モデルの行は残る(self):
        g = build_grid(self.records, self.domains, ["ダミー領域2"])
        self.assertEqual(self.labels(g), ["Bench-X", "Bench-Y"])
        # 絞った領域に値が無いモデル(Model-A2 は Bench-X だけ、など)も行に残す。未公表を「行ごと消す」と見えなくなるため
        self.assertEqual(g.rows, self.grid.rows)

    def test_未分類で絞る(self):
        g = build_grid(self.records, self.domains, [UNCLASSIFIED])
        self.assertEqual(self.labels(g), ["Bench-Z"])

    def test_複数の領域で絞っても並びは領域の順(self):
        g = build_grid(self.records, self.domains, [UNCLASSIFIED, "ダミー領域1"])
        self.assertEqual(self.labels(g), ["Bench-V 2.1", "Bench-W", "Bench-Z"])

    def test_値の無い領域は列が_0_個(self):
        for selected in (["ダミー領域3"], []):
            with self.subTest(selected=selected):
                g = build_grid(self.records, self.domains, selected)
                self.assertEqual(g.columns, ())
                self.assertEqual(g.rows, self.grid.rows)

    def test_領域の名前の文字列を_1_つ渡すと_TypeError(self):
        with self.assertRaises(TypeError):
            build_grid(self.records, self.domains, "ダミー領域1")

    def test_領域ごとの件数(self):
        self.assertEqual(
            count_by_domain(self.records, self.domains),
            {"ダミー領域1": 3, "ダミー領域2": 7, "ダミー領域3": 0, UNCLASSIFIED: 2},
        )
        self.assertEqual(list(count_by_domain(self.records, self.domains)), list(self.domains.choices))

    def test_元の向きは_1_行目が領域の行(self):
        rows = table_rows(self.grid)
        self.assertEqual(rows[0], [DOMAIN_LABEL, "", "", ""] + [self.grid.domain_of(c) for c in self.grid.columns])
        self.assertEqual(len(rows), 1 + len(self.grid.rows))

    def test_入れ替えた向きは_2_列目が領域の列(self):
        rows = transposed_rows(self.grid)
        self.assertEqual([r[:2] for r in rows[1:]], [[c.label, self.grid.domain_of(c)] for c in self.grid.columns])

    def test_領域で絞った表でも_どちらの向きでも選んだセルは同じ組(self):
        g = build_grid(self.records, self.domains, ["ダミー領域2", UNCLASSIFIED])
        for transposed in (False, True):
            rows = transposed_rows(g) if transposed else table_rows(g)
            header = transposed_header(g) if transposed else table_header(g)
            for row in g.rows:
                for column in g.columns:
                    r, c = cell_position(g, row, column, transposed)
                    with self.subTest(transposed=transposed, row=row.label, column=column.label):
                        self.assertEqual(pair_at(g, r, header[c], transposed=transposed), (row, column))
                        self.assertEqual(rows[r][c], g.cell_at(row, column).text)

    def test_詳細に領域が出る(self):
        g = self.grid
        a1 = find_row(g, "Model-A1", "Reasoning", "High")
        a2 = find_row(g, "Model-A2")
        cases = [
            (a1, "Bench-Y", None, "ダミー領域2"),  # 別名
            (a2, "Bench-V", "2.1", "ダミー領域1"),  # 版つき
            (a1, "Bench-Z", None, UNCLASSIFIED),
        ]
        for row, benchmark, version, expected in cases:
            cell = g.cell(row, find_col(g, benchmark, version))
            with self.subTest(benchmark=benchmark):
                self.assertTrue(cell.is_published)
                self.assertEqual(dict(detail_items(cell, self.domains)[0])["領域"], expected)

    def test_領域の行と列に_強中弱や順位を入れない(self):
        for row in [table_rows(self.grid)[0]] + [r[:2] for r in transposed_rows(self.grid)]:
            for word in ("強", "中", "弱", "順位", "平均", "合計", "総合"):
                with self.subTest(row=row, word=word):
                    self.assertFalse(any(word in str(x) for x in row))


class NoHighestEmphasisTest(unittest.TestCase):
    """列ごとの最大の値の強調(以前の highest_cells)は MVP から外した。
    測定条件の違う値を同じ土俵で比べ(§2-4 原則 1・3)、値の向きのキーも無いまま「最大」を示すため。
    入れ直すのは、§8 Q-6 と値の向きのキーが決まってから、§3-4 の規則に沿って行う。"""

    def test_最大の値を選ぶ関数と定数を持たない(self):
        for name in ("highest_cells", "MIN_MODELS_FOR_HIGHEST"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(viewer.grid, name))


if __name__ == "__main__":
    unittest.main()

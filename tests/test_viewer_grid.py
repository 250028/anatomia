import unittest
from dataclasses import replace
from pathlib import Path

from viewer.grid import (
    CONDITION_MARK,
    NOT_PUBLISHED,
    build_grid,
    cell_position,
    companies,
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
        r = rows[find_row(self.grid, "Model-A2")]
        self.assertEqual(r[:4], ["ダミー社A", "Model-A2", "（なし）", "（なし）"])
        self.assertEqual(r[4:], ["72.5%", NOT_PUBLISHED, "58%", NOT_PUBLISHED, NOT_PUBLISHED])

    def test_データの無いときは空の表になる(self):
        g = build_grid([])
        self.assertEqual((g.rows, g.columns), ((), ()))
        self.assertEqual(table_rows(g), [])


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

    def test_詳細に説明文_生の表記_領域_順位は出ない(self):
        g = self.grid
        cell = g.cell(find_row(g, "Model-A1", "Reasoning", "High"), find_col(g, "Bench-X"))
        labels = [k for k, _ in detail_items(cell)[0]]
        self.assertEqual(
            labels, ["モデル", "ベンチマーク", "スコア", "測定条件", "出典 URL", "取得日", "取得者", "取得方法"]
        )


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
        self.assertEqual(header[0], TRANSPOSED_FIRST_COLUMN)
        self.assertEqual(header[1:], [row.label for row in g.rows])
        self.assertEqual(len(header), 1 + len(g.rows))

    def test_行は_提供企業の行とベンチマークの数だけの行(self):
        g = self.grid
        rows = transposed_rows(g)
        self.assertEqual(len(rows), 1 + len(g.columns))
        self.assertEqual(rows[0], [PROVIDER_ROW] + [row.provider for row in g.rows])
        self.assertEqual([r[0] for r in rows[1:]], [c.label for c in g.columns])
        self.assertTrue(all(len(r) == len(transposed_header(g)) for r in rows))

    def test_入れ替えても_同じモデルとベンチマークの組のセルは同じ中身(self):
        # もう一度入れ替えると元の表のスコアの部分に戻る、に当たる確認
        g = self.grid
        normal = table_rows(g)
        transposed = transposed_rows(g)
        fixed = len(table_header(g)) - len(g.columns)
        for i in range(len(g.rows)):
            for j in range(len(g.columns)):
                with self.subTest(row=g.rows[i].label, column=g.columns[j].label):
                    self.assertEqual(transposed[1 + j][1 + i], normal[i][fixed + j])
                    self.assertEqual(transposed[1 + j][1 + i], g.cell(i, j).text)
        back = [[transposed[1 + j][1 + i] for j in range(len(g.columns))] for i in range(len(g.rows))]
        self.assertEqual(back, [r[fixed:] for r in normal])

    def test_入れ替えても_未公表と印の数は変わらない(self):
        g = self.grid
        normal = [c for r in table_rows(g) for c in r[4:]]
        transposed = [c for r in transposed_rows(g)[1:] for c in r[1:]]
        self.assertEqual(len(normal), len(transposed))
        self.assertEqual(normal.count(NOT_PUBLISHED), transposed.count(NOT_PUBLISHED))
        self.assertEqual(sum(CONDITION_MARK in c for c in normal), sum(CONDITION_MARK in c for c in transposed))
        self.assertGreater(normal.count(NOT_PUBLISHED), 0)

    def test_名指しのセル_未公表と印付き(self):
        g = self.grid
        rows = transposed_rows(g)
        i = find_row(g, "Model-A1", "Reasoning", "High")
        self.assertEqual(rows[1 + find_col(g, "Bench-W")][1 + i], "55.1% / 63.4%" + CONDITION_MARK)
        b2 = find_row(g, "Model-B2", None, "Max")
        self.assertEqual(rows[1 + find_col(g, "Bench-X")][1 + b2], NOT_PUBLISHED)

    def test_選んだセルは_どちらの向きでも同じ組になる(self):
        g = self.grid
        for i, row in enumerate(g.rows):
            for j, column in enumerate(g.columns):
                with self.subTest(row=row.label, column=column.label):
                    self.assertEqual(pair_at(g, i, column.label), (row, column))
                    self.assertEqual(pair_at(g, 1 + j, row.label, transposed=True), (row, column))

    def test_スコアのセルでないときは_None(self):
        g = self.grid
        self.assertIsNone(pair_at(g, 0, "モデル"))
        self.assertIsNone(pair_at(g, len(g.rows), g.columns[0].label))
        self.assertIsNone(pair_at(g, -1, g.columns[0].label))
        self.assertIsNone(pair_at(g, 0, "存在しない列"))
        label = g.rows[0].label
        self.assertIsNone(pair_at(g, 0, label, transposed=True))  # 提供企業の行
        self.assertIsNone(pair_at(g, 1, TRANSPOSED_FIRST_COLUMN, transposed=True))
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


if __name__ == "__main__":
    unittest.main()

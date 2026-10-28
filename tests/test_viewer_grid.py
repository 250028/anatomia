import unittest
from dataclasses import replace
from pathlib import Path

from viewer.grid import (
    CONDITION_MARK,
    NOT_PUBLISHED,
    build_grid,
    companies,
    detail_items,
    filter_by_company,
    format_score,
    last_retrieved_by_company,
    load_official,
    table_header,
    table_rows,
)

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
        self.assertEqual(d["取得方法"], "ダミー")
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

    def test_絞り込んだ企業だけを数えれば他社は出ない(self):
        only_a = filter_by_company(load_official(FIXTURES), ["ダミー社A"])
        self.assertEqual(list(last_retrieved_by_company(only_a)), ["ダミー社A"])


class FormatScoreTest(unittest.TestCase):
    def test_整数の浮動小数は小数点を付けない(self):
        r = load_official(FIXTURES)[0]
        self.assertEqual(format_score(replace(r, score=65.0, unit="%")), "65%")
        self.assertEqual(format_score(replace(r, score=0.5, unit=None)), "0.5")


if __name__ == "__main__":
    unittest.main()

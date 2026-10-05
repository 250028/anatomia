import unittest

from scraper.google_modelcard import parse_modelcard

# 実ページの文面は写さず、表の構造（rowspan・条件・他社の列・料金の行）だけを似せた HTML
CATEGORY_LAYOUT = """
<p>Results as of May, 2026 are listed below:</p>
<table>
<thead><tr><th></th><th>Benchmark</th><th></th><th>Gemini T1</th><th>Gemini T0</th><th>Other Co M</th></tr></thead>
<tbody>
<tr><th rowspan=2 scope=row>Coding</th><td>Bench A 2.1 <small>desc a</small></td><td><small>Harness X</small></td><td><strong>76.2%</strong></td><td>58.0%</td><td>78.2%</td></tr>
<tr><td>Bench B <small>desc b</small></td><td></td><td>55.1%</td><td>—</td><td>64.3%</td></tr>
<tr><th rowspan=2 scope=row>Long context</th><td rowspan=2>Bench C <small>desc c</small></td><td><small>128k</small></td><td>77.3%</td><td>67.2%</td><td>84.9%</td></tr>
<tr><td><small>1M</small></td><td>26.6%</td><td>22.1%</td><td>—</td></tr>
<tr><th>Rating</th><td>Bench D <small>desc d</small></td><td><small>Elo</small></td><td>1656</td><td>1204</td><td>1769</td></tr>
</tbody></table>
"""

BENCH_IN_TH_LAYOUT = """
<table>
<thead><tr><th>Benchmark</th><th>Notes</th><th>Gemini T2</th><th>Gemini T1</th><th>Other Co M</th></tr></thead>
<tbody>
<tr><th>Input price <small>$/1M tokens</small></th><td></td><td>$0.75 <small>($1.50 regular)</small></td><td>$0.75</td><td>$5.00</td></tr>
<tr><th>Bench E <small>desc e</small></th><td><small>All pass rate</small></td><td>10.0%</td><td>8.8%</td><td>6.7%</td></tr>
<tr><th rowspan=2>Bench F <small>desc f</small></th><td rowspan=2></td><td>87.8% <small>(agentic)</small></td><td rowspan=2>85.4%</td><td rowspan=2>75.4%</td></tr>
<tr><td>87.1% <small>(static)</small></td></tr>
</tbody></table>
"""


def parse(html):
    return parse_modelcard(html, "https://example.test/card", "tester", "2026-10-05")


def pick(records, model, benchmark):
    return [r for r in records if r["model"] == model and r["benchmark"] == benchmark]


class CategoryLayoutTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped = parse(CATEGORY_LAYOUT)

    def test_他社モデルの列は取り込まない(self):
        self.assertEqual({r["model"] for r in self.records}, {"Gemini T1", "Gemini T0"})
        self.assertEqual(self.skipped["他社モデルの列"], 1)

    def test_値なしは取り込まない(self):
        self.assertEqual(pick(self.records, "Gemini T0", "Bench B"), [])
        self.assertEqual(self.skipped["値なし（—・空欄）"], 1)

    def test_名前_説明_カテゴリ_条件を分ける(self):
        (r,) = pick(self.records, "Gemini T1", "Bench A 2.1")
        self.assertEqual(r["benchmark_description"], "desc a")
        self.assertEqual(r["source_category"], "Coding")
        self.assertEqual(r["condition"], "Harness X")
        self.assertEqual((r["score"], r["unit"]), (76.2, "%"))

    def test_rowspan_のベンチマークは条件ごとに別のレコードになる(self):
        recs = pick(self.records, "Gemini T1", "Bench C")
        self.assertEqual([(r["condition"], r["score"]) for r in recs], [("128k", 77.3), ("1M", 26.6)])
        self.assertEqual({r["source_category"] for r in recs}, {"Long context"})

    def test_Elo_は単位にして条件には入れない(self):
        (r,) = pick(self.records, "Gemini T1", "Bench D")
        self.assertEqual((r["score"], r["unit"], r["condition"]), (1656.0, "Elo", None))

    def test_出典と取得の情報を付ける(self):
        r = self.records[0]
        self.assertEqual(r["source_url"], "https://example.test/card")
        self.assertEqual(r["as_of"], "May, 2026")
        self.assertEqual((r["retrieved_by"], r["retrieved_at"], r["retrieval_method"]), ("tester", "2026-10-05", "script"))


class BenchInThLayoutTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped = parse(BENCH_IN_TH_LAYOUT)

    def test_料金の行は取り込まない(self):
        self.assertEqual([r for r in self.records if r["benchmark"].startswith("Input price")], [])
        self.assertEqual(self.skipped["料金の行（R-6 で扱う）"], 2)

    def test_Notes_の列を条件にする(self):
        (r,) = pick(self.records, "Gemini T2", "Bench E")
        self.assertEqual(r["condition"], "All pass rate")

    def test_セル内の条件を持ち_rowspan_の値は重複させない(self):
        t2 = pick(self.records, "Gemini T2", "Bench F")
        self.assertEqual([(r["condition"], r["score"]) for r in t2], [("(agentic)", 87.8), ("(static)", 87.1)])
        self.assertEqual(len(pick(self.records, "Gemini T1", "Bench F")), 1)


class NoTableTest(unittest.TestCase):
    def test_表がなければ例外にする(self):
        with self.assertRaises(ValueError):
            parse("<p>no table</p>")


if __name__ == "__main__":
    unittest.main()

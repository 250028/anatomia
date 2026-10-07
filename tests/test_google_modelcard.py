import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scraper import google_modelcard
from scraper.google_modelcard import FetchStopped, parse_modelcard

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


VALUE_FORMS = """
<table>
<thead><tr><th>Benchmark</th><th>Notes</th><th>Gemini T1</th></tr></thead>
<tbody>
<tr><th>Bench G</th><td></td><td>1,656</td></tr>
<tr><th>Bench H</th><td></td><td>76.2%*</td></tr>
<tr><th>Bench I</th><td></td><td>2.1x faster</td></tr>
<tr><th>Bench J</th><td></td><td>Not supported</td></tr>
<tr><th>Bench K</th><td></td><td>—</td></tr>
<tr><th>Bench L</th><td></td><td>1,2345</td></tr>
</tbody></table>
"""


def pick(records, model, benchmark):
    return [r for r in records if r["model"] == model and r["benchmark"] == benchmark]


class CategoryLayoutTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse(CATEGORY_LAYOUT)

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
        self.records, self.skipped, self.unreadable = parse(BENCH_IN_TH_LAYOUT)

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


class ValueFormsTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse(VALUE_FORMS)

    def test_カンマと脚注の記号は除いて読む(self):
        self.assertEqual([(r["benchmark"], r["score"], r["unit"]) for r in self.records],
                         [("Bench G", 1656.0, None), ("Bench H", 76.2, "%")])

    def test_読めない値は黙って丸めず_別に数える(self):
        self.assertEqual([(u["benchmark"], u["raw_value"]) for u in self.unreadable],
                         [("Bench I", "2.1x faster"), ("Bench J", "Not supported"), ("Bench L", "1,2345")])

    def test_ダッシュは値なしに数える(self):
        self.assertEqual(self.skipped["値なし（—・空欄）"], 1)


def response(status, text=""):
    return mock.Mock(status_code=status, text=text)


class FetchTest(unittest.TestCase):
    def test_200_なら本文を返す(self):
        with mock.patch.object(google_modelcard.requests, "get", return_value=response(200, "ok")):
            self.assertEqual(google_modelcard.fetch("https://example.test/"), "ok")

    def test_200_以外は止まり_再試行しない(self):
        for status in (403, 429, 301, 302, 500):
            with self.subTest(status=status):
                with mock.patch.object(google_modelcard.requests, "get", return_value=response(status)) as get:
                    with self.assertRaises(FetchStopped):
                        google_modelcard.fetch("https://example.test/")
                    self.assertEqual(get.call_count, 1)

    def test_リダイレクトは追わない(self):
        with mock.patch.object(google_modelcard.requests, "get", return_value=response(200, "ok")) as get:
            google_modelcard.fetch("https://example.test/")
        self.assertIs(get.call_args.kwargs["allow_redirects"], False)


class MainTest(unittest.TestCase):
    ROBOTS_OK = "User-agent: *\nAllow: /\n"

    def run_main(self, pages):
        """pages: URL → 返す response。ネットワークには出ない。呼ばれた URL と sleep の秒数を返す。"""
        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            return pages[url]

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.json"
            argv = ["prog", "--by", "tester", "--out", str(out)]
            with mock.patch("sys.argv", argv), \
                    mock.patch.object(google_modelcard.requests, "get", side_effect=fake_get), \
                    mock.patch.object(google_modelcard.time, "sleep") as sleep:
                try:
                    google_modelcard.main()
                except SystemExit as e:
                    return calls, sleep.call_args_list, e, None
                return calls, sleep.call_args_list, None, json.loads(out.read_text(encoding="utf-8"))

    def pages(self, robots=None):
        pages = {google_modelcard.ROBOTS_URL: robots or response(200, self.ROBOTS_OK)}
        pages.update({u: response(200, CATEGORY_LAYOUT) for u in google_modelcard.MODEL_CARD_URLS})
        return pages

    def test_robots_を先に取り_すべてのページの前に3秒空ける(self):
        calls, sleeps, exit_, data = self.run_main(self.pages())
        self.assertIsNone(exit_)
        self.assertEqual(calls, [google_modelcard.ROBOTS_URL, *google_modelcard.MODEL_CARD_URLS])
        self.assertEqual([c.args[0] for c in sleeps], [3, 3])
        self.assertTrue(data["records"])

    def test_robots_で禁止されていたらページを取らずに止まる(self):
        calls, _, exit_, _ = self.run_main(self.pages(robots=response(200, "User-agent: *\nDisallow: /models/\n")))
        self.assertIn("robots.txt", str(exit_))
        self.assertEqual(calls, [google_modelcard.ROBOTS_URL])

    def test_robots_の禁止を_Allow_や記法に惑わされず見つける(self):
        # 標準ライブラリの RobotFileParser は、このうち、Allow の後の Disallow・ワイルドカード・HTML を取得可と判定する（PR #9 のレビューで確認）
        cases = {
            "Allow の後の Disallow": "User-agent: *\nAllow: /\nDisallow: /models/\n",
            "ワイルドカード": "User-agent: *\nDisallow: /models/*\n",
            "途中のワイルドカード": "User-agent: *\nDisallow: /*/model-cards/\n",
            "単純な Disallow": "User-agent: *\nDisallow: /models/\n",
            "末尾の $": "User-agent: *\nDisallow: /models/model-cards/gemini-3-5-flash/$\n",
            "自分の User-agent": "User-agent: Anatomia-class-project\nDisallow: /\n",
            "HTML が 200 で返った": "<html><body>Enable JavaScript and cookies</body></html>",
        }
        for name, body in cases.items():
            with self.subTest(name):
                calls, _, exit_, data = self.run_main(self.pages(robots=response(200, body)))
                self.assertIsNotNone(exit_)
                self.assertIsNone(data)
                self.assertEqual(calls, [google_modelcard.ROBOTS_URL])

    def test_当てはまらない_Disallow_では止まらない(self):
        body = "User-agent: *\nAllow: /\nDisallow: /search\nDisallow:\n\nUser-agent: OtherBot\nDisallow: /\n"
        _, _, exit_, data = self.run_main(self.pages(robots=response(200, body)))
        self.assertIsNone(exit_)
        self.assertTrue(data["records"])

    def test_robots_が200以外ならページを取らずに止まる(self):
        calls, _, exit_, _ = self.run_main(self.pages(robots=response(404)))
        self.assertIn("404", str(exit_))
        self.assertEqual(calls, [google_modelcard.ROBOTS_URL])

    def test_ページが403なら止まり_出力は書かない(self):
        pages = self.pages()
        pages[google_modelcard.MODEL_CARD_URLS[1]] = response(403)
        calls, _, exit_, data = self.run_main(pages)
        self.assertIn("403", str(exit_))
        self.assertIsNone(data)


class NoTableTest(unittest.TestCase):
    def test_表がなければ例外にする(self):
        with self.assertRaises(ValueError):
            parse("<p>no table</p>")


if __name__ == "__main__":
    unittest.main()

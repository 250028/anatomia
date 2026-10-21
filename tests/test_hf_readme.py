from scraper import hf_readme
from scraper.google_modelcard import FetchStopped
from scraper.hf_readme import parse_readme
from huggingface_hub.errors import HfHubHTTPError
from pathlib import Path
from unittest import mock
import json
import tempfile
import unittest

LAYOUT = """
| | DeepSeek-V4-Pro High | Opus-X Max |
| --- | --- | --- |
| Bench A | 80.0 | 85.0 |
"""

DASH_LAYOUT = """
| | DeepSeek-V4-Pro High | Opus-X Max |
| --- | --- | --- |
| Bench A | 80.0 | 85.0 |
| Bench B | — | 90.0 |
"""

NOTE_LAYOUT = """
| | DeepSeek-V4-Pro High | Opus-X Max |
| --- | --- | --- |
| Bench C | 37.7* | 40.0 |
| Bench D | 3,100 | 2,900 |
"""

HEADING_LAYOUT = """
| | DeepSeek-V4-Pro High | Opus-X Max |
| --- | --- | --- |
| **Coding** | | |
| Bench E | 70.0 | 75.0 |
"""

MODE_LAYOUT = """
| | DeepSeek-V4-Pro Non-Think | DeepSeek-V4-Pro High | DeepSeek-V4-Pro Max | DeepSeek-V4-Flash Max | DeepSeek-V4-Base |
| --- | --- | --- | --- | --- | --- |
| Bench F | 60.0 | 68.0 | 72.0 | 65.0 | 50.0 |
"""

UNREADABLE_LAYOUT = """
| | DeepSeek-V4-Pro High | Opus-X Max |
| --- | --- | --- |
| Bench G | **94.3** | 90.0 |
| Bench H | 66.4% | 60.0 |
| Bench I | 66.4%¹ | 60.0 |
| Bench J | -- | 60.0 |
| Bench K | 1,2345 | 60.0 |
| Bench L | —* | 60.0 |
| Bench M | 80.0 | 60.0 |
"""

TWO_TABLES_LAYOUT = """
| | Opus-X Max |
| --- | --- |
| Bench N | 85.0 |

text

| | DeepSeek-V4-Pro High | Opus-X Max |
| --- | --- | --- |
| Bench O | 80.0 | 85.0 |

| | DeepSeek-V4-Pro Max |
| --- | --- |
| Bench P | 90.0 |
"""

SHORT_ROW_LAYOUT = """
| | DeepSeek-V4-Pro High | Opus-X Max |
| --- | --- | --- |
| Bench Q | 80.0 |
"""


class OtherCompanyColumnTest(unittest.TestCase):
    def test_他社モデルの列は取り込まない(self):
        records, skipped, unreadable = parse_readme(LAYOUT, "https://example.test/card", "tester", "2026-10-21", "abc123")
        self.assertEqual({r["model"] for r in records}, {"DeepSeek-V4-Pro"})


class MissingScoreTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(DASH_LAYOUT, "https://example.test/card", "tester", "2026-10-21", "abc123")

    def test_値なしは取り込まない(self):
        self.assertEqual([r["benchmark"] for r in self.records], ["Bench A"])

    def test_値なしの数を数える(self):
        self.assertEqual(self.skipped["値なし（—・空欄）"], 1)


class ValueFormTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(NOTE_LAYOUT, "https://example.test/card", "tester", "2026-10-21", "abc123")

    def test_脚注の記号は除いて読む(self):
        (r,) = [r for r in self.records if r["benchmark"] == "Bench C"]
        self.assertEqual(r["score"], 37.7)

    def test_カンマ区切りの数値は除いて読む(self):
        (r,) = [r for r in self.records if r["benchmark"] == "Bench D"]
        self.assertEqual(r["score"], 3100.0)


class HeadingTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(HEADING_LAYOUT, "https://example.test/card", "tester", "2026-10-21", "abc123")

    def test_見出し行は取り込まない(self):
        self.assertEqual([r["benchmark"] for r in self.records], ["Bench E"])

    def test_見出し行は値なしに数を変えず_別に数える(self):
        self.assertEqual(self.skipped["見出し行"], 1)
        self.assertEqual(self.skipped["値なし（—・空欄）"], 0)


class ReadmeModeTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(MODE_LAYOUT, "https://example.test/card", "tester", "2026-10-21", "abc123")

    def test_モデル名と推論モードに分ける(self):
        got = [(r["model"], r["mode"], r["score"]) for r in self.records[:4]]
        self.assertEqual(got, [
            ("DeepSeek-V4-Pro", "Non-Think", 60.0),
            ("DeepSeek-V4-Pro", "High", 68.0),
            ("DeepSeek-V4-Pro", "Max", 72.0),
            ("DeepSeek-V4-Flash", "Max", 65.0),
        ])

    def test_モードのない列は名前をそのまま持ち_モードは_None(self):
        (r,) = [r for r in self.records if r["model"] == "DeepSeek-V4-Base"]
        self.assertIsNone(r["mode"])


class UnreadableTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(
            UNREADABLE_LAYOUT, "https://example.test/card", "tester", "2026-10-21", "abc123"
        )

    def test_太字は外して読む(self):
        (r,) = [r for r in self.records if r["benchmark"] == "Bench G"]
        self.assertEqual(r["score"], 94.3)

    def test_パーセントは外して読む(self):
        (r,) = [r for r in self.records if r["benchmark"] == "Bench H"]
        self.assertEqual(r["score"], 66.4)

    def test_読めない値は黙って丸めず_別に出す(self):
        self.assertEqual(
            [(u["benchmark"], u["raw_value"]) for u in self.unreadable],
            [("Bench I", "66.4%¹"), ("Bench J", "--"), ("Bench K", "1,2345")],
        )

    def test_記号付きの値なしは値なしに数える(self):
        self.assertEqual(self.skipped["値なし（—・空欄）"], 1)

    def test_読めない値があっても残りは出る(self):
        self.assertIn("Bench M", [r["benchmark"] for r in self.records])

RECORD_LAYOUT = """
| | DeepSeek-V4-Pro High | Opus-X Max |
| --- | --- | --- |
| Bench S (Pass@1) | **80.5%** | 85.0 |
| Bench T (Rating) | 2,100 | 2,000 |
"""


class RecordFieldTest(unittest.TestCase):
    def setUp(self):
        self.records, _, _ = parse_readme(RECORD_LAYOUT, "https://example.test/card", "tester", "2026-10-22", "abc123")

    def test_出典と版と取得者を持つ(self):
        r = self.records[0]
        self.assertEqual(
            (r["provider"], r["source_url"], r["sha"], r["retrieved_by"], r["retrieved_at"], r["retrieval_method"]),
            ("DeepSeek", "https://example.test/card", "abc123", "tester", "2026-10-22", "script"),
        )

    def test_括弧は測定条件に分け_値の_を単位に入れる(self):
        r = self.records[0]
        self.assertEqual((r["benchmark"], r["condition"], r["unit"], r["raw_value"]), ("Bench S", "Pass@1", "%", "**80.5%**"))

    def test_Rating_は単位に入れる(self):
        r = self.records[1]
        self.assertEqual((r["benchmark"], r["condition"], r["unit"], r["score"]), ("Bench T", None, "Rating", 2100.0))


class TableBoundaryTest(unittest.TestCase):
    def test_最初の自社の列を持つ表だけを読む(self):
        records, _, _ = parse_readme(TWO_TABLES_LAYOUT, "https://example.test/card", "tester", "2026-10-22", "abc123")
        self.assertEqual([r["benchmark"] for r in records], ["Bench O"])

    def test_表がないときは止める(self):
        with self.assertRaises(ValueError):
            parse_readme("no table here", "https://example.test/card", "tester", "2026-10-22", "abc123")

    def test_自社の列がないときは止める(self):
        with self.assertRaises(ValueError):
            parse_readme("| | Opus-X Max |\n| --- | --- |\n| Bench R | 1.0 |", "https://example.test/card", "tester", "2026-10-22", "abc123")

    def test_列の数が見出しと違う行があるときは止める(self):
        with self.assertRaises(ValueError):
            parse_readme(SHORT_ROW_LAYOUT, "https://example.test/card", "tester", "2026-10-22", "abc123")

REPO_ROOT = Path(__file__).resolve().parent.parent


class FetchReadmeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.readme = Path(self.tmp.name) / "README.md"
        self.readme.write_text(LAYOUT, encoding="utf-8")

    def patches(self, author="deepseek-ai"):
        info = mock.Mock(author=author, sha="abc123")
        api = mock.patch.object(hf_readme, "HfApi", return_value=mock.Mock(model_info=mock.Mock(return_value=info)))
        dl = mock.patch.object(hf_readme, "hf_hub_download", return_value=str(self.readme))
        return api, dl

    def test_本文と_sha_を返す(self):
        api, dl = self.patches()
        with api, dl:
            self.assertEqual(hf_readme.fetch_readme("deepseek-ai/X"), (LAYOUT, "abc123"))

    def test_版を固定し_保存先はリポジトリの外(self):
        api, dl = self.patches()
        with api, dl as download:
            hf_readme.fetch_readme("deepseek-ai/X")
        kw = download.call_args.kwargs
        self.assertEqual(kw["revision"], "abc123")
        for d in (kw["local_dir"], kw["cache_dir"]):
            self.assertFalse(Path(d).resolve().is_relative_to(REPO_ROOT))

    def test_公式組織以外のリポジトリは止める(self):
        api, dl = self.patches(author="someone")
        with api, dl as download:
            with self.assertRaises(FetchStopped):
                hf_readme.fetch_readme("someone/X")
        download.assert_not_called()

    def test_エラーが返ったら止まり_再試行しない(self):
        err = HfHubHTTPError("429", response=mock.Mock(status_code=429, headers={}))
        api, dl = self.patches()
        with api, mock.patch.object(hf_readme, "hf_hub_download", side_effect=err) as download:
            with self.assertRaises(FetchStopped):
                hf_readme.fetch_readme("deepseek-ai/X")
        self.assertEqual(download.call_count, 1)


class MainTest(unittest.TestCase):
    def run_main(self, repo_ids, out):
        argv = ["hf_readme", "--by", "tester", "--out", str(out)]
        with mock.patch.object(hf_readme, "REPO_IDS", repo_ids), mock.patch.object(hf_readme.time, "sleep") as sleep, \
                mock.patch.object(hf_readme, "fetch_readme", return_value=(LAYOUT, "abc123")) as fetch, \
                mock.patch("sys.argv", argv):
            hf_readme.main()
        return sleep, fetch

    def test_一覧が空なら止まり_取得しない(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(hf_readme, "REPO_IDS", []), mock.patch("sys.argv", ["x", "--by", "t", "--out", d + "/o.json"]):
                with self.assertRaises(SystemExit):
                    hf_readme.main()

    def test_間隔を空けて取得し_候補データを書く(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.json"
            sleep, fetch = self.run_main(["deepseek-ai/X", "deepseek-ai/Y"], out)
            records = json.loads(out.read_text(encoding="utf-8"))["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual({r["sha"] for r in records}, {"abc123"})
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(hf_readme.MIN_INTERVAL_SEC)


if __name__ == "__main__":
    unittest.main()

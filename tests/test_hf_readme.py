from scraper.hf_readme import parse_readme
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
        records, skipped, unreadable = parse_readme(LAYOUT,"https://example.test/card", "tester", "2026-10-21")
        self.assertEqual({r["model"] for r in records}, {"DeepSeek-V4-Pro"})

class MissingScoreTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(DASH_LAYOUT,"https://example.test/card", "tester", "2026-10-21")

    def test_値なしは取り込まない(self):
        self.assertEqual([r["benchmark"] for r in self.records], ["Bench A"])

    def test_値なしの数を数える(self):
        self.assertEqual(self.skipped["値なし（—・空欄）"], 1) 

class ValueFormTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(NOTE_LAYOUT,"https://example.test/card", "tester", "2026-10-21")

    def test_脚注の記号は除いて読む(self):
        (r,) = [r for r in self.records if r["benchmark"] == "Bench C"]
        self.assertEqual(r["score"], 37.7)

    def test_カンマ区切りの数値は除いて読む(self):
        (r,) = [r for r in self.records if r["benchmark"] == "Bench D"]
        self.assertEqual(r["score"], 3100.0)

class HeadingTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(HEADING_LAYOUT,"https://example.test/card", "tester", "2026-10-21")

    def test_見出し行は取り込まない(self):
        self.assertEqual([r["benchmark"] for r in self.records], ["Bench E"])

    def test_見出し行は値なしに数を変えず_別に数える(self):
        self.assertEqual(self.skipped["見出し行"], 1)
        self.assertEqual(self.skipped["値なし（—・空欄）"], 0)

class ReadmeModeTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(MODE_LAYOUT,"https://example.test/card", "tester", "2026-10-21")

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
            UNREADABLE_LAYOUT, "https://example.test/card", "tester", "2026-10-21"
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

class TableBoundaryTest(unittest.TestCase):
    def test_最初の自社の列を持つ表だけを読む(self):
        records, _, _ = parse_readme(TWO_TABLES_LAYOUT, "https://example.test/card", "tester", "2026-10-22")
        self.assertEqual([r["benchmark"] for r in records], ["Bench O"])

    def test_表がないときは止める(self):
        with self.assertRaises(ValueError):
            parse_readme("no table here", "https://example.test/card", "tester", "2026-10-22")

    def test_自社の列がないときは止める(self):
        with self.assertRaises(ValueError):
            parse_readme("| | Opus-X Max |\n| --- | --- |\n| Bench R | 1.0 |", "https://example.test/card", "tester", "2026-10-22")

    def test_列の数が見出しと違う行があるときは止める(self):
        with self.assertRaises(ValueError):
            parse_readme(SHORT_ROW_LAYOUT, "https://example.test/card", "tester", "2026-10-22")

if __name__ == "__main__":
    unittest.main()
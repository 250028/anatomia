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


class OtherCompanyColumnTest(unittest.TestCase):
    def test_他社モデルの列は取り込まない(self):
        records, skipped, unreadable = parse_readme(LAYOUT,"https://example.test/card", "tester", "2026-10-21")
        self.assertEqual({r["model"] for r in records}, {"DeepSeek-V4-Pro High"})

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




if __name__ == "__main__":
    unittest.main()
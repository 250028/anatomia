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



if __name__ == "__main__":
    unittest.main()
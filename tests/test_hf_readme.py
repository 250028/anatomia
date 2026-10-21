from scraper.hf_readme import parse_readme
import unittest

LAYOUT = """
| | DeepSeek-V4-Pro High | Opus-X Max |
| --- | --- | --- |
| Bench A | 80.0 | 85.0 |
"""




class OtherCompanyColumnTest(unittest.TestCase):
    def test_他社モデルの列は取り込まない(self):
        records, skipped, unreadable = parse_readme(LAYOUT,"https://example.test/card", "tester", "2026-10-21")
        self.assertEqual({r["model"] for r in records}, {"DeepSeek-V4-Pro High"})


if __name__ == "__main__":
    unittest.main()
import unittest

from scraper.values import NO_VALUE, clean_value


class CleanValueTest(unittest.TestCase):
    def test_桁区切りと前後の太字と末尾の脚注を除く(self):
        for raw, want in [("3,100", "3100"), ("**94.3**", "94.3"), ("37.7*", "37.7"), ("66.4†", "66.4")]:
            with self.subTest(raw=raw):
                self.assertEqual(clean_value(raw), want)

    def test_桁区切りでないカンマは残す(self):
        self.assertEqual(clean_value("1,2345"), "1,2345")

    def test_記号付きの値なしも値なしになる(self):
        self.assertIn(clean_value("—*"), NO_VALUE)


if __name__ == "__main__":
    unittest.main()

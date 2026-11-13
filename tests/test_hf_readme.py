from scraper import hf_readme
from scraper.google_modelcard import FetchStopped
from scraper.hf_readme import parse_readme
from pathlib import Path
from unittest import mock
import json
import tempfile
import unittest

REAL_TAKEN_MODELS = hf_readme.TAKEN_MODELS
# 取る一覧は本物の名前なので、以下の自作の表(架空の名前)でも取れるよう、このファイルの間だけ架空の名前に差し替える。
# 本物の一覧での動きは RealTakenModelsTest で確かめる
_FICTIONAL_TAKEN = frozenset({
    "DeepSeek-V4-Pro", "DeepSeek-V4-Mini", "DeepSeek-V4-Lite", "DeepSeek-X-0813", "DeepSeek-X-Pro",
    "DeepSeek-X", "DeepSeek-Y", "DeepSeek-V4.1-Flash",
})
_patcher = mock.patch.object(hf_readme, "TAKEN_MODELS", _FICTIONAL_TAKEN)


def setUpModule():
    _patcher.start()


def tearDownModule():
    _patcher.stop()


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
| | DeepSeek-V4-Pro Non-Think | DeepSeek-V4-Pro High | DeepSeek-V4-Pro Max | DeepSeek-V4-Mini Max | DeepSeek-V4-Lite |
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

SAME_UNREADABLE_LAYOUT = """
| | DeepSeek-V4-Pro Non-Think | DeepSeek-V4-Pro High | DeepSeek-V4-Pro Max |
| --- | --- | --- | --- |
| Bench U | -- | -- | -- |
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
            ("DeepSeek-V4-Mini", "Max", 65.0),
        ])

    def test_モードのない列は名前をそのまま持ち_モードは_None(self):
        (r,) = [r for r in self.records if r["model"] == "DeepSeek-V4-Lite"]
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

    def test_読めない値にはモードを入れ_同じ行の列を区別できる(self):
        _, _, unreadable = parse_readme(
            SAME_UNREADABLE_LAYOUT, "https://example.test/card", "tester", "2026-10-28", "abc123"
        )
        self.assertEqual([u["mode"] for u in unreadable], ["Non-Think", "High", "Max"])

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

    def test_読まなかった自社の表の数を知らせる(self):
        _, skipped, _ = parse_readme(TWO_TABLES_LAYOUT, "https://example.test/card", "tester", "2026-10-28", "abc123")
        self.assertEqual(skipped["読まなかった表（自社の列あり）"], 1)

    def test_自社の表が1つなら読まなかった表は数えない(self):
        _, skipped, _ = parse_readme(LAYOUT, "https://example.test/card", "tester", "2026-10-28", "abc123")
        self.assertNotIn("読まなかった表（自社の列あり）", skipped)

    def test_表がないときは止める(self):
        with self.assertRaises(ValueError):
            parse_readme("no table here", "https://example.test/card", "tester", "2026-10-22", "abc123")

    def test_自社の列がないときは止める(self):
        with self.assertRaises(ValueError):
            parse_readme("| | Opus-X Max |\n| --- | --- |\n| Bench R | 1.0 |", "https://example.test/card", "tester", "2026-10-22", "abc123")

    def test_列の数が見出しと違う行があるときは止める(self):
        with self.assertRaises(ValueError):
            parse_readme(SHORT_ROW_LAYOUT, "https://example.test/card", "tester", "2026-10-22", "abc123")

EXCLUDED_COLUMNS_LAYOUT = """
| | DeepSeek-X-0813 | DeepSeek-X (Preview) | DeepSeek-Y-Base | Opus-X |
| --- | --- | --- | --- | --- |
| Bench V | 80.0 | 50.0 | 40.0 | 85.0 |
"""

BASE_FIRST_LAYOUT = """
| | DeepSeek-Y-Base | DeepSeek-X-Base |
| --- | --- | --- |
| Bench W | 40.0 | 45.0 |

| | Opus-X | DS-Y | DS-X |
| --- | --- | --- | --- |
| Bench W | 85.0 | 60.0 | 70.0 |
"""

ONLY_EXCLUDED_LAYOUT = """
| | DeepSeek-Y-Base | DeepSeek-X (Preview) |
| --- | --- | --- |
| Bench W | 40.0 | 45.0 |
"""

NOT_TAKEN_LAYOUT = """
| | DeepSeek-X-0813 | DeepSeek-V4-Flash-0731 |
| --- | --- | --- |
| Bench W | 70.0 | 60.0 |
"""

TWO_VALUES_LAYOUT = """
| | DeepSeek-X-0813 | Opus-X |
| --- | --- | --- |
| Bench Z (wo / w tools) | 12.5 / 33.5 | 4.0 / 8.0 |
| Bench Z2 (Pass@1) | 10.0 / 20.0 | 1.0 / 2.0 |
| Bench Z3 (wo / w tools) | 5.0 | 6.0 |
| Bench Z4 (wo / w tools) | 5.0 / — | 6.0 / 7.0 |
"""

DAGGER_LAYOUT = """
| | DeepSeek-X-0813 | Opus-X |
| --- | --- | --- |
| Bench Y | 70.0 | 60.0 |
| Internal Bench † | 71.1 | - |
| Bench Y2 | 80.0† | 60.0 |
| Internal † (Pass@1) | 72.0 | - |
| Internal2† (wo / w tools) | 5.0 / 6.0 | - |
| **Internal3 †** | 73.0 | - |
| Internal4<sup>†</sup> | 74.0 | - |
"""


class ColumnSelectionTest(unittest.TestCase):
    def parse(self, layout):
        return parse_readme(layout, "https://example.test/card", "tester", "2026-11-04", "abc123")

    def test_取る一覧にない_Preview_と_Base_の列は取り込まない(self):
        records, _, _ = self.parse(EXCLUDED_COLUMNS_LAYOUT)
        self.assertEqual([(r["model"], r["score"]) for r in records], [("DeepSeek-X-0813", 80.0)])

    def test_除いた列の数を数える(self):
        _, skipped, _ = self.parse(EXCLUDED_COLUMNS_LAYOUT)
        self.assertEqual(skipped["除いた列（取る一覧にない）"], 2)

    def test_Base_の表が先にあっても_取りたい表を読む(self):
        records, _, _ = self.parse(BASE_FIRST_LAYOUT)
        self.assertEqual([(r["model"], r["score"]) for r in records], [("DeepSeek-Y", 60.0), ("DeepSeek-X", 70.0)])

    def test_略称_DS_は_DeepSeek_に直す(self):
        records, _, _ = self.parse(BASE_FIRST_LAYOUT)
        self.assertEqual({r["model"] for r in records}, {"DeepSeek-Y", "DeepSeek-X"})

    def test_取る一覧の列がない表は読まず_数える(self):
        _, skipped, _ = self.parse(BASE_FIRST_LAYOUT)
        self.assertEqual(skipped["読まなかった表（取る一覧の列がない）"], 1)

    def test_取る列がない表だけのときは止める(self):
        with self.assertRaises(ValueError):
            self.parse(ONLY_EXCLUDED_LAYOUT)

    def test_対象外のモデルの列は取り込まず_数える(self):
        records, skipped, _ = self.parse(NOT_TAKEN_LAYOUT)
        self.assertEqual({r["model"] for r in records}, {"DeepSeek-X-0813"})
        self.assertEqual(skipped["除いた列（取る一覧にない）"], 1)


ALIAS_NOT_TAKEN_LAYOUT = """
| | Opus-X | DS-X-Pro | DS-V4-Flash | DS-V4.1-Flash |
| --- | --- | --- | --- | --- |
| Bench W | 85.0 | 60.0 | 55.0 | 70.0 |
"""

MODE_EXCLUDED_LAYOUT = """
| | DeepSeek-X-0813 High | DeepSeek-V4-Flash-0731 Max | DeepSeek-Y-Base High | DeepSeek-X (Preview) Max |
| --- | --- | --- | --- | --- |
| Bench W | 70.0 | 60.0 | 40.0 | 50.0 |
"""

SPELLING_LAYOUT = """
| | DeepSeek-X-0813 | DeepSeek-X Preview | DeepSeek-X preview | DeepSeek-Y base | DeepSeek-Y Base | DeepSeek-Y (Base) |
| --- | --- | --- | --- | --- | --- | --- |
| Bench W | 70.0 | 1.0 | 2.0 | 3.0 | 4.0 | 5.0 |
"""


class NotTakenColumnTest(unittest.TestCase):
    def parse(self, layout):
        return parse_readme(layout, "https://example.test/card", "tester", "2026-11-04", "abc123")

    def test_略称で書かれた取らないモデルの列も取り込まない(self):
        records, skipped, _ = self.parse(ALIAS_NOT_TAKEN_LAYOUT)
        self.assertEqual({r["model"] for r in records}, {"DeepSeek-X-Pro", "DeepSeek-V4.1-Flash"})
        self.assertEqual(skipped["除いた列（取る一覧にない）"], 1)

    def test_推論モードが付いた列名でも除く(self):
        records, skipped, _ = self.parse(MODE_EXCLUDED_LAYOUT)
        self.assertEqual([(r["model"], r["mode"]) for r in records], [("DeepSeek-X-0813", "High")])
        self.assertEqual(skipped["除いた列（取る一覧にない）"], 3)

    def test_Preview_と_Base_の表記ゆれも除く(self):
        records, skipped, _ = self.parse(SPELLING_LAYOUT)
        self.assertEqual([r["model"] for r in records], ["DeepSeek-X-0813"])
        self.assertEqual(skipped["除いた列（取る一覧にない）"], 5)


UNLISTED_LAYOUT = """
| | DeepSeek-V4-Pro-0813 High | DS-V3.2 | DeepSeek-R2 | DeepSeek-X-Base-0813 | DeepSeek-Y-Base* | DeepSeek-V4-Flash-0731* | DS-V4.1-Flash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Bench W | 70.0 | 1.0 | 2.0 | 3.0 | 4.0 | 5.0 | 6.0 |
"""


class RealTakenModelsTest(unittest.TestCase):
    def test_取る一覧は_R3_の対象の2つ(self):
        self.assertEqual(REAL_TAKEN_MODELS, {"DeepSeek-V4-Pro-0813", "DeepSeek-V4.1-Flash"})

    def test_一覧にない列は綴りによらず取り込まず_数える(self):
        with mock.patch.object(hf_readme, "TAKEN_MODELS", REAL_TAKEN_MODELS):
            records, skipped, _ = parse_readme(UNLISTED_LAYOUT, "https://example.test/card", "tester", "2026-11-10", "abc123")
        self.assertEqual([(r["model"], r["mode"]) for r in records], [("DeepSeek-V4-Pro-0813", "High"), ("DeepSeek-V4.1-Flash", None)])
        self.assertEqual(skipped["除いた列（取る一覧にない）"], 5)


class TwoValuesCellTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(
            TWO_VALUES_LAYOUT, "https://example.test/card", "tester", "2026-11-04", "abc123"
        )

    def test_見出しの括弧と値が同じ数なら_条件ごとの行に分ける(self):
        got = [(r["benchmark"], r["condition"], r["score"]) for r in self.records if r["benchmark"] == "Bench Z"]
        self.assertEqual(got, [("Bench Z", "wo", 12.5), ("Bench Z", "w tools", 33.5)])

    def test_分けても元のセルを_raw_value_に残す(self):
        rows = [r for r in self.records if r["benchmark"] == "Bench Z"]
        self.assertEqual({r["raw_value"] for r in rows}, {"12.5 / 33.5"})

    def test_括弧が値の数と対応しないときは_黙って分けず_別に出す(self):
        got = [(u["benchmark"], u["raw_value"]) for u in self.unreadable]
        self.assertIn(("Bench Z2 (Pass@1)", "10.0 / 20.0"), got)
        self.assertNotIn("Bench Z2", [r["benchmark"] for r in self.records])

    def test_値が1つなら_括弧に_スラッシュがあっても分けない(self):
        (r,) = [r for r in self.records if r["benchmark"] == "Bench Z3"]
        self.assertEqual((r["condition"], r["score"]), ("wo / w tools", 5.0))

    def test_分けた片方が値なしなら_その片方だけ取らず数える(self):
        rows = [r for r in self.records if r["benchmark"] == "Bench Z4"]
        self.assertEqual([(r["condition"], r["score"]) for r in rows], [("wo", 5.0)])
        self.assertEqual(self.skipped["値なし（—・空欄）"], 1)


class DaggerLabelTest(unittest.TestCase):
    def setUp(self):
        self.records, self.skipped, self.unreadable = parse_readme(
            DAGGER_LAYOUT, "https://example.test/card", "tester", "2026-11-04", "abc123"
        )

    def test_名前に_が付いた行は取り込まず_数える(self):
        self.assertNotIn("Internal Bench †", [r["benchmark"] for r in self.records])

    def test_括弧の前や太字の中に_が付いた行も取り込まない(self):
        self.assertEqual([r["benchmark"] for r in self.records], ["Bench Y"])
        self.assertEqual(self.skipped["名前に † が付いた行（社内テストなど。要確認）"], 5)

    def test_値に付いた_は取り込まず_要確認に元のセルごと出す(self):
        self.assertNotIn("Bench Y2", [r["benchmark"] for r in self.records])
        got = [(u["benchmark"], u["raw_value"]) for u in self.unreadable]
        self.assertEqual(got, [("Bench Y2", "80.0†")])


SHA = "a" * 40
README_URL = "https://huggingface.co/deepseek-ai/X/resolve/main/README.md"


def readme_response(status=200, sha=SHA):
    headers = {} if sha is None else {"X-Repo-Commit": sha}
    return mock.Mock(status_code=status, headers=headers, content=LAYOUT.encode("utf-8"))


class FetchReadmeTest(unittest.TestCase):
    def patch_get(self, *responses):
        return mock.patch.object(hf_readme.requests, "get", side_effect=list(responses))

    def test_本文と_sha_を返す(self):
        with self.patch_get(readme_response()):
            self.assertEqual(hf_readme.fetch_readme("deepseek-ai/X"), (LAYOUT, SHA))

    def test_README_を_1_回だけ取る(self):
        with self.patch_get(readme_response()) as get:
            hf_readme.fetch_readme("deepseek-ai/X")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.args[0], README_URL)

    def test_個人の_token_を付けず_リダイレクトも追わない(self):
        with self.patch_get(readme_response()) as get:
            hf_readme.fetch_readme("deepseek-ai/X")
        self.assertNotIn("Authorization", get.call_args.kwargs["headers"])
        self.assertIs(get.call_args.kwargs["allow_redirects"], False)

    def test_公式組織以外のリポジトリは止める(self):
        with self.patch_get() as get:
            with self.assertRaises(FetchStopped):
                hf_readme.fetch_readme("someone/X")
        get.assert_not_called()

    def test_200_以外が返ったら止まり_再試行しない(self):
        for status in (403, 429, 500):
            with self.subTest(status=status):
                with self.patch_get(readme_response(status=status)) as get:
                    with self.assertRaises(FetchStopped):
                        hf_readme.fetch_readme("deepseek-ai/X")
                self.assertEqual(get.call_count, 1)

    def test_版のヘッダーが無いか読めないときは止める(self):
        for sha in (None, "main", "A" * 40, "a" * 39):
            with self.subTest(sha=sha):
                with self.patch_get(readme_response(sha=sha)) as get:
                    with self.assertRaises(FetchStopped):
                        hf_readme.fetch_readme("deepseek-ai/X")
                self.assertEqual(get.call_count, 1)


CACHE_PATH = "/api/resolve-cache/models/deepseek-ai/X/" + SHA + "/README.md"
CACHE_URL = "https://huggingface.co" + CACHE_PATH + "?%2Fdeepseek-ai%2FX%2Fresolve%2Fmain%2FREADME.md=&etag=%22e%22"


def redirect_response(location=CACHE_URL, sha=None):
    headers = {} if location is None else {"Location": location}
    if sha is not None:
        headers["X-Repo-Commit"] = sha
    return mock.Mock(status_code=307, headers=headers, content=b"")


class FetchReadmeRedirectTest(unittest.TestCase):
    def fetch(self, *responses):
        with mock.patch.object(hf_readme.requests, "get", side_effect=list(responses)) as get, \
                mock.patch.object(hf_readme.time, "sleep") as sleep:
            try:
                return hf_readme.fetch_readme("deepseek-ai/X"), get, sleep
            except FetchStopped as e:
                return e, get, sleep

    def test_307_の移動先が_resolve_cache_なら_1_回だけ追い_URL_の_sha_を版にする(self):
        result, get, sleep = self.fetch(redirect_response(), readme_response(sha=None))
        self.assertEqual(result, (LAYOUT, SHA))
        self.assertEqual([c.args[0] for c in get.call_args_list], [README_URL, CACHE_URL])
        for call in get.call_args_list:
            self.assertIs(call.kwargs["allow_redirects"], False)
            self.assertNotIn("Authorization", call.kwargs["headers"])
        sleep.assert_called_once_with(hf_readme.MIN_INTERVAL_SEC)

    def test_相対の_Location_でも_同じ形なら追う(self):
        result, get, _ = self.fetch(redirect_response(location=CACHE_PATH + "?etag=e"), readme_response(sha=None))
        self.assertEqual(result, (LAYOUT, SHA))
        self.assertEqual(get.call_args_list[1].args[0], "https://huggingface.co" + CACHE_PATH + "?etag=e")

    def test_追ってよくない移動先は_追わずに止める(self):
        bad = {
            "別のドメイン": "https://cdn.example.com" + CACHE_PATH,
            "http": "http://huggingface.co" + CACHE_PATH,
            "ポート番号つき": "https://huggingface.co:8443" + CACHE_PATH,
            "ユーザー情報つき": "https://user@huggingface.co" + CACHE_PATH,
            "別の組織のドメイン": "https://huggingface.co.evil.test" + CACHE_PATH,
            "resolve-cache でない": "https://huggingface.co/deepseek-ai/X/resolve/" + SHA + "/README.md",
            "別のリポジトリ": "https://huggingface.co/api/resolve-cache/models/deepseek-ai/Y/" + SHA + "/README.md",
            "sha が短い": "https://huggingface.co/api/resolve-cache/models/deepseek-ai/X/" + "a" * 39 + "/README.md",
            "README でない": "https://huggingface.co/api/resolve-cache/models/deepseek-ai/X/" + SHA + "/config.json",
            "Location なし": None,
        }
        for name, location in bad.items():
            with self.subTest(name=name):
                result, get, sleep = self.fetch(redirect_response(location=location))
                self.assertIsInstance(result, FetchStopped)
                self.assertEqual(get.call_count, 1)
                sleep.assert_not_called()

    def test_追った先が_200_以外なら止まり_さらには追わない(self):
        for status in (403, 429, 500, 307):
            with self.subTest(status=status):
                result, get, _ = self.fetch(redirect_response(), readme_response(status=status, sha=None))
                self.assertIsInstance(result, FetchStopped)
                self.assertEqual(get.call_count, 2)

    def test_版のヘッダーがあれば_URL_の_sha_と一致を確かめる(self):
        for first, second in ((SHA, None), (None, SHA)):
            with self.subTest(first=first, second=second):
                result, _, _ = self.fetch(redirect_response(sha=first), readme_response(sha=second))
                self.assertEqual(result, (LAYOUT, SHA))
        for first, second in (("b" * 40, None), (None, "b" * 40), (SHA, "b" * 40), ("main", None)):
            with self.subTest(first=first, second=second):
                result, _, _ = self.fetch(redirect_response(sha=first), readme_response(sha=second))
                self.assertIsInstance(result, FetchStopped)


class RepoIdsTest(unittest.TestCase):
    def test_取得先は公式組織のリポジトリだけ(self):
        self.assertTrue(hf_readme.REPO_IDS)
        for repo_id in hf_readme.REPO_IDS:
            self.assertEqual(repo_id.split("/")[0], hf_readme.OFFICIAL_ORG)


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

    def test_出典URLは取得した版の_README_のページにする(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.json"
            self.run_main(["deepseek-ai/X"], out)
            records = json.loads(out.read_text(encoding="utf-8"))["records"]
        self.assertEqual({r["source_url"] for r in records}, {"https://huggingface.co/deepseek-ai/X/blob/abc123/README.md"})

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

from scraper import hf_qwen
from scraper.google_modelcard import FetchStopped
from pathlib import Path
from unittest import mock
import json
import tempfile
import unittest

# 取得と書き出しの骨組みだけを確かめる。README の本文は、形を確かめていないので作らない(中身は読まない文字列で足りる)
TEXT = "(README の本文。テストでは読まない)"
SHA = "0123456789abcdef0123456789abcdef01234567"
README_URL = "https://huggingface.co/Qwen/X/resolve/main/README.md"


def readme_response(status=200, sha=SHA):
    headers = {} if sha is None else {"X-Repo-Commit": sha}
    return mock.Mock(status_code=status, headers=headers, content=TEXT.encode("utf-8"))


class FetchReadmeTest(unittest.TestCase):
    def patch_get(self, *responses):
        # hf_qwen は hf_readme の _get を使うので、ネットワークに出ないよう requests.get を差し替える
        return mock.patch("scraper.hf_readme.requests.get", side_effect=list(responses))

    def test_本文と_sha_を返す(self):
        with self.patch_get(readme_response()):
            self.assertEqual(hf_qwen.fetch_readme("Qwen/X"), (TEXT, SHA))

    def test_README_を_1_回だけ取る(self):
        with self.patch_get(readme_response()) as get:
            hf_qwen.fetch_readme("Qwen/X")
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.args[0], README_URL)

    def test_個人の_token_を付けず_リダイレクトも追わない(self):
        with self.patch_get(readme_response()) as get:
            hf_qwen.fetch_readme("Qwen/X")
        self.assertNotIn("Authorization", get.call_args.kwargs["headers"])
        self.assertIs(get.call_args.kwargs["allow_redirects"], False)

    def test_公式組織以外のリポジトリは止める(self):
        for repo_id in ("someone/X", "deepseek-ai/X", "qwen/X"):
            with self.subTest(repo_id=repo_id):
                with self.patch_get() as get:
                    with self.assertRaises(FetchStopped):
                        hf_qwen.fetch_readme(repo_id)
                get.assert_not_called()

    def test_200_以外が返ったら止まり_再試行しない(self):
        for status in (403, 429, 500, 307):
            with self.subTest(status=status):
                with self.patch_get(readme_response(status=status)) as get:
                    with self.assertRaises(FetchStopped):
                        hf_qwen.fetch_readme("Qwen/X")
                self.assertEqual(get.call_count, 1)

    def test_版のヘッダーが無いか読めないときは止める(self):
        for sha in (None, "main", "A" * 40, "a" * 39):
            with self.subTest(sha=sha):
                with self.patch_get(readme_response(sha=sha)) as get:
                    with self.assertRaises(FetchStopped):
                        hf_qwen.fetch_readme("Qwen/X")
                self.assertEqual(get.call_count, 1)


# 中間の形(行ごとのセル。セルは画面で上下に並ぶ文字列のリスト)の自作の表。形は、水戸が 2026-11-16 にブラウザで見た画面の画像に合わせた。
# 実物のマークアップから、この形が作れるかは確かめていない。モデル名は本物、ベンチマーク名・説明・値・ラベルの組み合わせは架空
H = [[], ["Qwen3.8-", "27B"], ["Qwen3.6-", "27B"], ["Qwen3.7-", "Plus"], ["Other", "Model-9B"], ["Rival5 Max"]]


def row(left, *cells):
    return [left] + [c if isinstance(c, list) else [c] for c in cells]


def build(*rows):
    return hf_qwen.records_from_rows([H, *rows], "u", "tester", "2026-11-16", SHA)


class RecordsFromRowsTest(unittest.TestCase):
    def test_取る一覧の列だけを取り_他社と取らない自社の列は数える(self):
        records, skipped, unreadable = build(
            [["Area One"]],
            row(["Doing things", "Bench A 1.0 (Harness X)"], "10.5", "20.5", "30.5", "40.5", "50.5"),
        )
        self.assertEqual([(r["model"], r["score"]) for r in records], [("Qwen3.8-27B", 10.5), ("Qwen3.6-27B", 20.5)])
        self.assertEqual(skipped["他社モデルの列"], 2)
        self.assertEqual(skipped["除いた列（取る一覧にない）"], 1)
        self.assertEqual(unreadable, [])

    def test_左端の_2_段は説明とベンチマーク名に分け_領域の行は分類にする(self):
        records, skipped, _ = build(
            [["Area One"]],
            row(["Doing things", "Bench A 1.0 (Harness X)"], "10.5", "20.5", "1", "2", "3"),
            [["Area Two"], [], [], [], [], []],
            row(["Other work", "Bench B v2"], "11", "12", "1", "2", "3"),
        )
        first, _, third, _ = records
        # ベンチマーク名は、括弧・版を分けずにページの表記のまま持つ(分けるかは決まっていない)
        self.assertEqual((first["benchmark"], first["benchmark_description"], first["source_category"]),
                         ("Bench A 1.0 (Harness X)", "Doing things", "Area One"))
        self.assertEqual((third["benchmark"], third["source_category"]), ("Bench B v2", "Area Two"))
        self.assertEqual(skipped["領域の見出しの行"], 2)

    def test_ラベルつきの_2_つの値は_ラベルを測定条件にして値ごとに_1_件にする(self):
        records, _, unreadable = build(
            row(["Doing things", "Bench C"], ["Pass@1", "**10.5**", "Score", "20.5"], ["Pass@1", "11.5", "Score", "21.5"], "--", "--", "--"),
        )
        self.assertEqual(
            [(r["model"], r["condition"], r["score"]) for r in records],
            [("Qwen3.8-27B", "Pass@1", 10.5), ("Qwen3.8-27B", "Score", 20.5), ("Qwen3.6-27B", "Pass@1", 11.5), ("Qwen3.6-27B", "Score", 21.5)],
        )
        # raw_value は、照合で突き合わせられるよう、セルの表記を全部持つ(太字の記号も残す)
        self.assertEqual(records[0]["raw_value"], "Pass@1 **10.5** Score 20.5")
        self.assertEqual(unreadable, [])

    def test_ラベルが_1_つだけのセルは_その_1_件だけを取る(self):
        records, _, _ = build(
            row(["Seeing things", "Bench D"], ["Without CI", "10.5", "With CI", "20.5"], ["Without CI", "30.5"], "1", "2", "3"),
        )
        self.assertEqual([(r["model"], r["condition"]) for r in records],
                         [("Qwen3.8-27B", "Without CI"), ("Qwen3.8-27B", "With CI"), ("Qwen3.6-27B", "Without CI")])

    def test_ラベルつきの行で_ラベルのない取る列のセルは取らず要確認に出す(self):
        records, _, unreadable = build(
            row(["Seeing things", "Bench D"], ["Without CI", "10.5", "With CI", "20.5"], "30.5", "1", "2", "3"),
        )
        self.assertEqual([r["model"] for r in records], ["Qwen3.8-27B", "Qwen3.8-27B"])
        self.assertEqual(unreadable, [{"model": "Qwen3.6-27B", "mode": None, "benchmark": "Bench D", "raw_value": "30.5"}])

    def test_値なしの記号はレコードを作らず数える(self):
        records, skipped, unreadable = build(
            row(["Doing things", "Bench E"], "--", "—", "1", "2", "3"),
        )
        self.assertEqual(records, [])
        self.assertEqual(skipped["値なし（--・空欄）"], 2)
        self.assertEqual(unreadable, [])

    def test_読めない値と脚注の記号つきの値は取らず要確認に出す(self):
        records, _, unreadable = build(
            row(["Doing things", "Bench F"], "N/A", "10.5†", "1", "2", "3"),
            row(["Doing things", "Bench G"], ["Pass@1", "1.0", "Score"], ["10.5", "Score", "11.5", "Pass@1"], "1", "2", "3"),
        )
        self.assertEqual(records, [])
        self.assertEqual([u["raw_value"] for u in unreadable], ["N/A", "10.5†", "Pass@1 1.0 Score", "10.5 Score 11.5 Pass@1"])

    def test_左端が_2_段でない行は取らず要確認に出す(self):
        records, _, unreadable = build(row(["Only one line"], "10.5", "20.5", "1", "2", "3"))
        self.assertEqual(records, [])
        self.assertEqual(len(unreadable), 2)

    def test_出力のキーは_hf_readme_と同じ形にする(self):
        records, _, _ = build(row(["Doing things", "Bench A"], "10.5%", "20.5", "1", "2", "3"))
        self.assertEqual(records[0], {
            "provider": "Qwen", "model": "Qwen3.8-27B", "mode": None, "benchmark": "Bench A",
            "benchmark_description": "Doing things", "source_category": None, "score": 10.5, "unit": "%",
            "condition": None, "raw_value": "10.5%", "source_url": "u", "sha": SHA,
            "retrieved_at": "2026-11-16", "retrieved_by": "tester", "retrieval_method": "script",
        })
        self.assertIsNone(records[1]["unit"])

    def test_形が想定と違えば止める(self):
        cases = {
            "見出しの左端が空でない": [[["Benchmark"], ["Qwen3.8-27B"]]],
            "取る列がない": [[[], ["Qwen9-1B"], ["Rival5 Max"]]],
            "列の数が違う": [H, row(["Doing things", "Bench A"], "1", "2")],
            "空": [],
        }
        for name, rows in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    hf_qwen.records_from_rows(rows, "u", "tester", "2026-11-16", SHA)


class RepoIdsTest(unittest.TestCase):
    def test_取得先は公式組織のリポジトリだけ(self):
        for repo_id in hf_qwen.REPO_IDS:
            self.assertEqual(repo_id.split("/")[0], hf_qwen.OFFICIAL_ORG)

    def test_HTML_を読む部分を書くまでは取得先を入れない(self):
        # HTML から中間の形を作る部分(parse_readme)ができたら、このテストを消して REPO_IDS を入れる
        self.assertEqual(hf_qwen.REPO_IDS, [])
        with self.assertRaises(NotImplementedError):
            hf_qwen.parse_readme(TEXT, "u", "tester", "2026-11-16", SHA)


class MainTest(unittest.TestCase):
    def test_一覧が空なら止まり_取得しない(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.json"
            with mock.patch.object(hf_qwen, "REPO_IDS", []), mock.patch("scraper.hf_readme.requests.get") as get, \
                    mock.patch("sys.argv", ["x", "--by", "t", "--out", str(out)]):
                with self.assertRaises(SystemExit):
                    hf_qwen.main()
            get.assert_not_called()
            self.assertFalse(out.exists())

    def test_間隔を空けて取得し_出典URLは取得した版の_README_のページにして書く(self):
        # 解析は差し替える(形を確かめていないので)。確かめるのは、取得・出典URL・書き出しのつなぎ方だけ
        def fake_parse(text, source_url, retrieved_by, retrieved_at, sha):
            return [{"source_url": source_url, "sha": sha, "retrieved_by": retrieved_by}], {}, []

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.json"
            argv = ["hf_qwen", "--by", "tester", "--out", str(out)]
            with mock.patch.object(hf_qwen, "REPO_IDS", ["Qwen/X", "Qwen/Y"]), \
                    mock.patch.object(hf_qwen.time, "sleep") as sleep, \
                    mock.patch.object(hf_qwen, "fetch_readme", return_value=(TEXT, "abc123")) as fetch, \
                    mock.patch.object(hf_qwen, "parse_readme", side_effect=fake_parse), \
                    mock.patch("sys.argv", argv):
                hf_qwen.main()
            records = json.loads(out.read_text(encoding="utf-8"))["records"]
        self.assertEqual([c.args[0] for c in fetch.call_args_list], ["Qwen/X", "Qwen/Y"])
        self.assertEqual(
            [r["source_url"] for r in records],
            ["https://huggingface.co/Qwen/X/blob/abc123/README.md", "https://huggingface.co/Qwen/Y/blob/abc123/README.md"],
        )
        self.assertEqual({r["retrieved_by"] for r in records}, {"tester"})
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_called_with(hf_qwen.MIN_INTERVAL_SEC)

    def test_取得が止まったら書き出さない(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.json"
            argv = ["hf_qwen", "--by", "tester", "--out", str(out)]
            with mock.patch.object(hf_qwen, "REPO_IDS", ["Qwen/X"]), mock.patch.object(hf_qwen.time, "sleep"), \
                    mock.patch.object(hf_qwen, "fetch_readme", side_effect=FetchStopped("429")), \
                    mock.patch("sys.argv", argv):
                with self.assertRaises(SystemExit):
                    hf_qwen.main()
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()

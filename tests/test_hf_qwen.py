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


class RepoIdsTest(unittest.TestCase):
    def test_取得先は公式組織のリポジトリだけ(self):
        for repo_id in hf_qwen.REPO_IDS:
            self.assertEqual(repo_id.split("/")[0], hf_qwen.OFFICIAL_ORG)

    def test_解析を書くまでは取得先を入れない(self):
        # 解析(parse_readme)ができたら、このテストを消して REPO_IDS を入れる
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

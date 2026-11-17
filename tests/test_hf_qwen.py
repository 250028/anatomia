from scraper import hf_qwen
from scraper.google_modelcard import FetchStopped
from pathlib import Path
from unittest import mock
import contextlib
import io
import json
import tempfile
import unittest

# 取得と書き出しのテストでは、README の本文は読まない(中身は読まない文字列で足りる)
TEXT = "(README の本文。取得のテストでは読まない)"
SHA = "0123456789abcdef0123456789abcdef01234567"
README_URL = "https://huggingface.co/Qwen/X/resolve/main/README.md"


def readme_response(status=200, sha=SHA):
    headers = {} if sha is None else {"X-Repo-Commit": sha}
    return mock.Mock(status_code=status, headers=headers, content=TEXT.encode("utf-8"))


class FetchReadmeTest(unittest.TestCase):
    def setUp(self):
        # hf_qwen は hf_readme.fetch_readme を使う。307 を追う前の間隔(time.sleep)で待たないよう差し替える
        patcher = mock.patch("scraper.hf_readme.time.sleep")
        self.sleep = patcher.start()
        self.addCleanup(patcher.stop)

    def patch_get(self, *responses):
        # ネットワークに出ないよう requests.get を差し替える
        return mock.patch("scraper.hf_readme.requests.get", side_effect=list(responses))

    def test_307_の移動先が_Qwen_の_resolve_cache_なら_1_回だけ追う(self):
        cache_url = "https://huggingface.co/api/resolve-cache/models/Qwen/X/" + SHA + "/README.md"
        redirect = mock.Mock(status_code=307, headers={"Location": cache_url})
        with self.patch_get(redirect, readme_response(sha=None)) as get:
            self.assertEqual(hf_qwen.fetch_readme("Qwen/X"), (TEXT, SHA))
        self.assertEqual([c.args[0] for c in get.call_args_list], [README_URL, cache_url])
        self.sleep.assert_called_once()

    def test_307_の移動先がほかのリポジトリなら止める(self):
        other = "https://huggingface.co/api/resolve-cache/models/deepseek-ai/X/" + SHA + "/README.md"
        with self.patch_get(mock.Mock(status_code=307, headers={"Location": other})) as get:
            with self.assertRaises(FetchStopped):
                hf_qwen.fetch_readme("Qwen/X")
        self.assertEqual(get.call_count, 1)

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
        # 307 は、移動先(Location)が無いので止まる
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


# 中間の形(行ごとのセル。セルは <div> で区切られた文字列のリスト)の自作の表。列見出しは 1 つの文字列(2026-11-16 の README の <th> と同じ)。
# モデル名は本物、ベンチマーク名・説明・値・ラベルの組み合わせは架空
H = [[], ["Qwen3.8-27B"], ["Qwen3.6-27B"], ["Qwen3.7-Plus"], ["Other Model-9B"], ["Rival5 Max"]]


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
            [["Area Two"]],
            row(["Other work", "Bench B v2"], "11", "12", "1", "2", "3"),
        )
        first, _, third, _ = records
        # 対応表(BENCHMARK_NAMES)にない名前は、括弧・版を分けずに README の表記のまま持つ
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
        self.assertEqual(skipped["値なし（-- などの記号）"], 2)
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

    def test_値のセルがすべて空の行は_領域の行とみなさず要確認に出す(self):
        records, skipped, unreadable = build(
            [["Area One"]],
            row(["Doing things", "Bench Empty"], [], [], [], [], []),
            row(["Doing things", "Bench A"], "10.5", "20.5", "1", "2", "3"),
        )
        # 後の行の分類が、空の行の名前に変わらない
        self.assertEqual([r["source_category"] for r in records], ["Area One", "Area One"])
        self.assertEqual(skipped["領域の見出しの行"], 1)
        self.assertEqual([(u["model"], u["benchmark"]) for u in unreadable], [("Qwen3.8-27B", "Bench Empty"), ("Qwen3.6-27B", "Bench Empty")])

    def test_空のセルは値なしとして数えず_要確認に出す(self):
        # 空のセル(lines が空)は README に無い形。値なしの記号(--)とは分けて、値なしの数に入れない
        records, skipped, unreadable = build(
            row(["Doing things", "Bench E"], [], "16.75", "1", "2", "3"),
        )
        self.assertEqual([(r["model"], r["score"]) for r in records], [("Qwen3.6-27B", 16.75)])
        self.assertEqual(unreadable, [{"model": "Qwen3.8-27B", "mode": None, "benchmark": "Bench E", "raw_value": ""}])
        self.assertEqual(skipped["値なし（-- などの記号）"], 0)

    def test_空のラベルか空の値がある組は_取らず要確認に出す(self):
        # 空の metric-label・metric-value の <div> は、_CellLinesParser が空の文字列として残す
        records, _, unreadable = build(
            row(["Doing things", "Bench C"], ["Pass@1", "", "", "20.5"], ["Pass@1", "11.5", "Score", ""], "1", "2", "3"),
            row(["Doing things", "Bench D"], [""], "12.5", "1", "2", "3"),
        )
        self.assertEqual([(r["model"], r["benchmark"]) for r in records], [("Qwen3.6-27B", "Bench D")])
        self.assertEqual([(u["model"], u["benchmark"]) for u in unreadable],
                         [("Qwen3.8-27B", "Bench C"), ("Qwen3.6-27B", "Bench C"), ("Qwen3.8-27B", "Bench D")])

    def test_想定外のタグの印のあるセルは取らず要確認に出す(self):
        rows = [H, row(["Doing things", "Bench A"], "10.5", "20.5", "1", "2", "3"), row(["Doing things", "Bench B"], "11.5", "21.5", "1", "2", "3")]
        records, _, unreadable = hf_qwen.records_from_rows(rows, "u", "tester", "2026-11-16", SHA, {(1, 1), (2, 0), (1, 3)})
        # 取らない列(3)の印は、取る列に響かない。左端の印は、左端が 2 段でない行と同じく、左端の文字をつないで出す
        self.assertEqual([(r["model"], r["benchmark"]) for r in records], [("Qwen3.6-27B", "Bench A")])
        self.assertEqual([(u["model"], u["benchmark"]) for u in unreadable],
                         [("Qwen3.8-27B", "Bench A"), ("Qwen3.8-27B", "Doing things Bench B"), ("Qwen3.6-27B", "Doing things Bench B")])

    def test_出力のキーは_google_modelcard_と同じ形にする(self):
        records, _, _ = build(row(["Doing things", "Bench A"], "10.5%", "20.5", "1", "2", "3"))
        self.assertEqual(records[0], {
            "provider": "Qwen", "model": "Qwen3.8-27B", "mode": None, "benchmark": "Bench A", "benchmark_version": None,
            "benchmark_description": "Doing things", "source_category": None, "score": 10.5, "unit": "%",
            "condition": None, "raw_value": "10.5%", "source_url": "u", "sha": SHA,
            "retrieved_at": "2026-11-16", "retrieved_by": "tester", "retrieval_method": "script",
        })
        self.assertIsNone(records[1]["unit"])

    def test_対応表の名前は名前と版に分け_ハーネスはラベルと一緒に測定条件にする(self):
        records, _, _ = build(
            row(["Doing things", "Terminal Bench 2.1 (Terminus)"], ["Pass@1", "10.5"], ["Score", "20.5"], "1", "2", "3"),
            row(["Doing things", "DeepSWE 1.1"], "11", "12", "1", "2", "3"),
        )
        self.assertEqual(
            [(r["benchmark"], r["benchmark_version"], r["condition"]) for r in records],
            [("Terminal-Bench", "2.1", "Terminus / Pass@1"), ("Terminal-Bench", "2.1", "Terminus / Score"),
             ("DeepSWE", "v1.1", None), ("DeepSWE", "v1.1", None)],
        )

    def test_ラベルつきの行の_ラベルのない値なしは値なしとして数える(self):
        records, skipped, unreadable = build(
            row(["Doing things", "Bench C"], ["Pass@1", "10.5", "Score", "20.5"], "--", "1", "2", "3"),
        )
        self.assertEqual(len(records), 2)
        self.assertEqual(skipped["値なし（-- などの記号）"], 1)
        self.assertEqual(unreadable, [])

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


# README の表の自作の写し。タグ・class・colspan・入れ子・ラベルの置き方だけを、2026-11-16 に水戸が開いた README のマークアップに合わせた
# (style 属性は省いた)。ベンチマーク名は README と同じものがあるが、説明・注・値は架空で、README の値とは関係がない
def _th(name):
    return f"<th>{name}</th>"


def _bench(name, desc="Desc"):
    return f'<td class="benchmark-cell"><div class="benchmark-capability">{desc}</div><div class="benchmark-name">{name}</div></td>'


def _stack(*pairs):
    inner = "".join(f'<div><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>' for label, value in pairs)
    return f'<td><div class="metric-stack">{inner}</div></td>'


HEAD = "<thead><tr>" + "".join(_th(n) for n in ["", "Qwen3.8-27B", "Qwen3.6-27B", "Qwen3.7-Plus", "Muse Glimmer-30B", "Opus4.6 Max"]) + "</tr></thead>"
README = "\n".join([
    "---", "license: apache-2.0", "---", "## Benchmark Results", "### Text Performance",
    '<div><table class="vl-table">', "<thead><tr>", HEAD[len("<thead><tr>"):], "<tbody>",
    '<tr><td colspan="6">Area A</td></tr>',
    "<tr>", _bench("Terminal Bench 2.1 (Terminus)"), "<td>11.1</td>", "<td><strong>22.2</strong></td>", "<td>33.3</td>", "<td>--</td>", "<td>44.4</td>", "</tr>",
    '<tr><td colspan="6">Area B</td></tr>',
    "<tr>", _bench("Bench Two"), _stack(("Pass@1", "<strong>1.5</strong>"), ("Score", "2.5")), _stack(("Pass@1", "3.5"), ("Score", "4.5")),
    _stack(("Pass@1", "5.5"), ("Score", "6.5")), "<td>--</td>", "<td>--</td>", "</tr>",
    "</tbody>", "</table>", "<div><ol><li>Bench Two: a made-up note.</li><li>A double dash marks a missing value in this made-up table.</li></ol></div></div>",
    "### VL Performance", "<div>",
    '<table class="vl-table">' + HEAD + "<tbody>",
    '<tr><td colspan="6">Area C</td></tr>',
    "<tr>" + _bench("CharXiv (RQ)") + _stack(("Without CI", "7.25"), ("With CI", "<strong>8.25</strong>")) + _stack(("Without CI", "9.25"))
    + _stack(("Without CI", "10.25")) + "<td>11.25</td>" + _stack(("Without CI", "12.25")) + "</tr>",
    "<tr>" + _bench("Bench Four") + "<td>--</td><td>13.75</td><td>14.75</td><td>--</td><td>15.75</td></tr>",
    "</tbody>", "</table>", "<ol><li>Bench Four and CharXiv (RQ): another invented remark.</li></ol>", "</div>",
])


class ParseReadmeTest(unittest.TestCase):
    def parse(self, text=README):
        return hf_qwen.parse_readme(text, "u", "tester", "2026-11-16", SHA)

    def test_2_つの表の取る列を読み_他の列と領域の行を数える(self):
        records, skipped, unreadable = self.parse()
        self.assertEqual(
            [(r["source_category"], r["model"], r["benchmark"], r["benchmark_version"], r["condition"], r["score"]) for r in records],
            [
                ("Area A", "Qwen3.8-27B", "Terminal-Bench", "2.1", "Terminus", 11.1),
                ("Area A", "Qwen3.6-27B", "Terminal-Bench", "2.1", "Terminus", 22.2),
                ("Area B", "Qwen3.8-27B", "Bench Two", None, "Pass@1", 1.5),
                ("Area B", "Qwen3.8-27B", "Bench Two", None, "Score", 2.5),
                ("Area B", "Qwen3.6-27B", "Bench Two", None, "Pass@1", 3.5),
                ("Area B", "Qwen3.6-27B", "Bench Two", None, "Score", 4.5),
                ("Area C", "Qwen3.8-27B", "CharXiv (RQ)", None, "Without CI", 7.25),
                ("Area C", "Qwen3.8-27B", "CharXiv (RQ)", None, "With CI", 8.25),
                ("Area C", "Qwen3.6-27B", "CharXiv (RQ)", None, "Without CI", 9.25),
                ("Area C", "Qwen3.6-27B", "Bench Four", None, None, 13.75),
            ],
        )
        self.assertEqual(unreadable, [])
        self.assertEqual(skipped["読んだ表"], 2)
        self.assertEqual(skipped["領域の見出しの行"], 3)
        self.assertEqual(skipped["他社モデルの列"], 4)
        self.assertEqual(skipped["除いた列（取る一覧にない）"], 2)
        self.assertEqual(skipped["値なし（-- などの記号）"], 1)

    def test_太字のタグは値に残らず_raw_value_はセルの文字をつなぐ(self):
        records, _, _ = self.parse()
        by = {(r["model"], r["benchmark"], r["condition"]): r for r in records}
        self.assertEqual(by[("Qwen3.6-27B", "Terminal-Bench", "Terminus")]["raw_value"], "22.2")
        self.assertEqual(by[("Qwen3.8-27B", "Bench Two", "Pass@1")]["raw_value"], "Pass@1 1.5 Score 2.5")
        self.assertEqual(by[("Qwen3.8-27B", "Bench Two", "Pass@1")]["benchmark_description"], "Desc")

    def test_取る列のない表は読まずに数える(self):
        extra = '<table><thead><tr><th></th><th>Rival5 Max</th></tr></thead><tbody><tr>' + _bench("Bench Five") + "<td>1.0</td></tr></tbody></table>"
        records, skipped, _ = self.parse(README + "\n" + extra)
        self.assertEqual(skipped["読まなかった表（取る一覧の列がない）"], 1)
        self.assertEqual(skipped["読んだ表"], 2)
        self.assertEqual(len(records), 10)

    def test_値のセルの中の_sup_や_span_は_値につなげず要確認に出す(self):
        cases = {
            "sup の脚注": ("<td>11.1</td>", "<td>11.1<sup>1</sup></td>", "11.1 1"),
            "span で区切った 2 つ": ("<td>11.1</td>", "<td><span>11.1</span><span>5</span></td>", "11.1 5"),
            "span 1 つ": ("<td>11.1</td>", "<td><span>11.1</span></td>", "11.1"),
            "ラベルつきの値の中の sup": ('<div class="metric-value"><strong>1.5</strong></div>',
                                       '<div class="metric-value"><strong>1.5</strong><sup>2</sup></div>', "Pass@1 1.5 2 Score 2.5"),
        }
        for name, (old, new, raw) in cases.items():
            with self.subTest(name):
                text = README.replace(old, new, 1)
                self.assertNotEqual(text, README)
                records, _, unreadable = self.parse(text)
                self.assertEqual([u["raw_value"] for u in unreadable], [raw])
                self.assertEqual(unreadable[0]["model"], "Qwen3.8-27B")
                self.assertEqual(len(records), 10 - (2 if name == "ラベルつきの値の中の sup" else 1))

    def test_左端のセルに想定外のタグがあれば_その行は要確認に出す(self):
        text = README.replace('<div class="benchmark-name">Bench Four</div>', '<div class="benchmark-name"><a>Bench Four</a></div>', 1)
        self.assertNotEqual(text, README)
        records, _, unreadable = self.parse(text)
        self.assertEqual([u["model"] for u in unreadable], ["Qwen3.8-27B", "Qwen3.6-27B"])
        self.assertNotIn("Bench Four", [r["benchmark"] for r in records])

    def test_空の_metric_の_div_が重なっても_ラベルと値がずれない(self):
        # 値の <div> と次のラベルの <div> が両方空だと、空を捨てる読み方では [Pass@1, 2.5] に詰まり、2.5 が Pass@1 の値になる
        old = '<div class="metric-value"><strong>1.5</strong></div></div><div><div class="metric-label">Score</div>'
        text = README.replace(old, '<div class="metric-value"></div></div><div><div class="metric-label"></div>', 1)
        self.assertNotEqual(text, README)
        records, _, unreadable = self.parse(text)
        self.assertEqual([(u["model"], u["benchmark"]) for u in unreadable], [("Qwen3.8-27B", "Bench Two")])
        self.assertNotIn(("Qwen3.8-27B", "Bench Two"), [(r["model"], r["benchmark"]) for r in records])

    def test_値のセルがすべて空の行の後も_分類は領域の行のまま(self):
        empty = "<tr>" + _bench("Bench Empty") + "<td></td>" * 5 + "</tr>"
        text = README.replace("<tr>" + _bench("Bench Four"), empty + "<tr>" + _bench("Bench Four"), 1)
        self.assertNotEqual(text, README)
        records, _, unreadable = self.parse(text)
        self.assertEqual({r["source_category"] for r in records if r["benchmark"] == "Bench Four"}, {"Area C"})
        self.assertEqual([u["benchmark"] for u in unreadable], ["Bench Empty", "Bench Empty"])

    def test_空の_td_は_値なしではなく要確認に出す(self):
        # 取る列でただ 1 つの値なし(Bench Four の Qwen3.8-27B の --)を、空の <td></td> に替える。値なしは 0 になり、空のセルは要確認に出る
        text = README.replace("<tr>" + _bench("Bench Four") + "<td>--</td>", "<tr>" + _bench("Bench Four") + "<td></td>", 1)
        self.assertNotEqual(text, README)
        records, skipped, unreadable = self.parse(text)
        self.assertEqual(unreadable, [{"model": "Qwen3.8-27B", "mode": None, "benchmark": "Bench Four", "raw_value": ""}])
        self.assertEqual(skipped["値なし（-- などの記号）"], 0)
        self.assertEqual(len(records), 10)

    def test_形が想定と違えば止める(self):
        cases = {
            "表がない": "## Benchmark Results\nno table",
            "取る列のある表がない": '<table><thead><tr><th></th><th>Rival5 Max</th></tr></thead></table>',
            "rowspan がある": README.replace('<td colspan="6">Area A</td>', '<td rowspan="2">Area A</td>'),
            "幅いっぱいでない colspan": README.replace('<td colspan="6">Area A</td>', '<td colspan="3">Area A</td><td></td><td></td><td></td>'),
            "見出しの左端が空でない": README.replace("<thead><tr><th></th>", "<thead><tr><th>Benchmark</th>", 1),
            "入れ子の表": README.replace("<td>11.1</td>", "<td><table><tr><td>99.9</td></tr></table></td>", 1),
            "colspan の無い 1 セルだけの行": README.replace('<td colspan="6">Area B</td>', "<td>Area B</td>", 1),
            "領域の行に想定外のタグ": README.replace('<td colspan="6">Area B</td>', '<td colspan="6">Area B<sup>1</sup></td>', 1),
            "見出しの行に想定外のタグ": README.replace("<th>Opus4.6 Max</th>", "<th>Opus4.6 Max<sup>1</sup></th>", 1),
        }
        for name, text in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    self.parse(text)


class ReadmeWarningsTest(unittest.TestCase):
    def test_表の直後の注の件数と_注の先頭に名前が出るベンチマークを出す(self):
        warnings = hf_qwen.readme_warnings(README)
        self.assertEqual(len(warnings), 2)
        self.assertIn("読んだ表 1 の下に注が 2 件ある（要確認", warnings[0])
        self.assertTrue(warnings[0].endswith("注の先頭に名前が出るベンチマーク: Bench Two"))
        # 名前は表の並びで出す
        self.assertIn("読んだ表 2 の下に注が 1 件ある（要確認", warnings[1])
        self.assertTrue(warnings[1].endswith("注の先頭に名前が出るベンチマーク: CharXiv (RQ), Bench Four"))

    def test_取る列が見出しから消えた表は_その列の名前を出す(self):
        # VL の表(2 つ目)の Qwen3.6-27B の列名だけを変える
        first, second = README.split('<table class="vl-table">' + HEAD, 1)
        text = first + '<table class="vl-table">' + HEAD.replace("<th>Qwen3.6-27B</th>", "<th>Qwen3.6-27B (new)</th>") + second
        self.assertNotEqual(text, README)
        warnings = hf_qwen.readme_warnings(text)
        self.assertIn("読んだ表 2 の見出しに、取る一覧の列が無い（要確認。列の名前が変わった可能性）: Qwen3.6-27B", warnings)
        self.assertFalse(any("読んだ表 1 の見出し" in w for w in warnings))

    def test_取る列がそろっていれば_列の要確認は出さない(self):
        self.assertFalse(any("見出しに、取る一覧の列が無い" in w for w in hf_qwen.readme_warnings(README)))

    def test_注の文は返さない(self):
        self.assertFalse(any("invented" in w or "made-up" in w for w in hf_qwen.readme_warnings(README)))

    def test_表のベンチマークに当たらない注だけなら_件数だけを出す(self):
        text = README.replace("<li>Bench Two: a made-up note.</li>", "<li>Bench Zero: a made-up note.</li>")
        self.assertTrue(hf_qwen.readme_warnings(text)[0].endswith("注の先頭に名前が出るベンチマーク: なし"))

    def test_名前の一部だけが一致しても数えない(self):
        text = README.replace("<li>Bench Two: a made-up note.</li>", "<li>Bench Twofold: a made-up note.</li>")
        self.assertTrue(hf_qwen.readme_warnings(text)[0].endswith("なし"))

    def test_表の後に文があってからの_ol_は表の注とみなさない(self):
        text = README.replace("</table>\n<div><ol>", "</table>\nSome text.\n<div><ol>", 1)
        self.assertNotEqual(text, README)
        warnings = hf_qwen.readme_warnings(text)
        self.assertEqual(len(warnings), 1)
        self.assertIn("読んだ表 2", warnings[0])

    def test_注が無ければ何も出さない(self):
        text = README.replace("<li>Bench Four and CharXiv (RQ): another invented remark.</li>", "")
        text = text.replace("<li>Bench Two: a made-up note.</li><li>A double dash marks a missing value in this made-up table.</li>", "")
        self.assertEqual(hf_qwen.readme_warnings(text), [])

    def test_注があってもレコードは変わらない(self):
        without = README.replace("<li>Bench Four and CharXiv (RQ): another invented remark.</li>", "")
        self.assertEqual(hf_qwen.parse_readme(README, "u", "t", "2026-11-16", SHA),
                         hf_qwen.parse_readme(without, "u", "t", "2026-11-16", SHA))


class RepoIdsTest(unittest.TestCase):
    def test_取得先は公式組織のリポジトリだけ(self):
        for repo_id in hf_qwen.REPO_IDS:
            self.assertEqual(repo_id.split("/")[0], hf_qwen.OFFICIAL_ORG)

    def test_取得先は_R_3_の_Qwen3_8_27B_のカード(self):
        self.assertEqual(hf_qwen.REPO_IDS, ["Qwen/Qwen3.8-27B"])


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
        # 解析は差し替える。確かめるのは、取得・出典URL・書き出しのつなぎ方だけ
        def fake_parse(text, source_url, retrieved_by, retrieved_at, sha):
            return [{"benchmark": "Bench A", "benchmark_version": None, "source_url": source_url, "sha": sha,
                     "retrieved_by": retrieved_by}], {}, []

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.json"
            argv = ["hf_qwen", "--by", "tester", "--out", str(out)]
            with mock.patch.object(hf_qwen, "REPO_IDS", ["Qwen/X", "Qwen/Y"]), \
                    mock.patch.object(hf_qwen.time, "sleep") as sleep, \
                    mock.patch.object(hf_qwen, "fetch_readme", return_value=(TEXT, "abc123")) as fetch, \
                    mock.patch.object(hf_qwen, "parse_readme", side_effect=fake_parse), \
                    mock.patch.object(hf_qwen, "readme_warnings", return_value=[]), \
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

    def test_表の下の注は_取得の終わりに要確認として標準エラーに出し_書き出す形は変えない(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "o.json"
            argv = ["hf_qwen", "--by", "tester", "--out", str(out)]
            err = io.StringIO()
            with mock.patch.object(hf_qwen, "REPO_IDS", ["Qwen/X"]), mock.patch.object(hf_qwen.time, "sleep"), \
                    mock.patch.object(hf_qwen, "fetch_readme", return_value=(README, SHA)), \
                    mock.patch("sys.argv", argv), contextlib.redirect_stderr(err):
                hf_qwen.main()
            data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(list(data), ["records"])
        self.assertEqual(len(data["records"]), 10)
        lines = err.getvalue().splitlines()
        self.assertTrue(lines[0].startswith("https://huggingface.co/Qwen/X/blob/"))
        self.assertEqual([line for line in lines if "注が" in line],
                         ["  " + w for w in hf_qwen.readme_warnings(README)])

    def test_help_に_実行の前にリーダーの判断が要ることを出す(self):
        out = io.StringIO()
        with mock.patch("sys.argv", ["hf_qwen", "--help"]), mock.patch("scraper.hf_readme.requests.get") as get, \
                contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                hf_qwen.main()
        get.assert_not_called()
        help_text = "".join(out.getvalue().split())
        self.assertIn("".join(hf_qwen.BEFORE_RUN.split()), help_text)
        self.assertIn("Qwenの実取得には、その実行についてのリーダーの判断が要る", help_text)
        self.assertIn("判断の範囲の外では実行しない。", help_text)

    def test_help_の判断の文は_docstring_の段落と同じ(self):
        self.assertIn(" ".join(hf_qwen.BEFORE_RUN.split()), " ".join(hf_qwen.__doc__.split()))

    def test_docstring_が無くても_help_は落ちない(self):
        # python3 -OO では docstring が None になる。そのときも --help が判断の文を出す
        out = io.StringIO()
        with mock.patch.object(hf_qwen, "__doc__", None), mock.patch("sys.argv", ["hf_qwen", "--help"]), \
                mock.patch("scraper.hf_readme.requests.get") as get, contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit):
                hf_qwen.main()
        get.assert_not_called()
        self.assertIn("".join(hf_qwen.BEFORE_RUN.split()), "".join(out.getvalue().split()))

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

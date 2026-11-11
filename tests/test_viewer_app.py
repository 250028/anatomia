"""画面(viewer/app.py)を、Streamlit の AppTest で動かして確かめる。

streamlit が入っていない環境(収集だけを担当して、画面のライブラリを入れていない PC など)では、
import で落とさずに、このファイルのテストを skip にする。ロジック層のテスト(test_viewer_records.py・
test_viewer_grid.py)は streamlit が無くても走る。

正式データ(data/official/)の側の表示は、リポジトリの data/official/ の有無に左右されないように、
一時ディレクトリに viewer/ を写し、その横に作った data/official/ を読ませて確かめる
(app.py は、自分の置き場所から 1 つ上をリポジトリのルートとみなすため。app.py の定数は書き換えない)。
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

REPO_ROOT = Path(__file__).resolve().parent.parent
APP = REPO_ROOT / "viewer" / "app.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "official"
# 最初の実行は streamlit の import で数秒かかることがあるので、待ち時間を長めにとる
TIMEOUT = 60
SKIP_REASON = "streamlit が入っていない(画面のテストは skip)"


def rerun(at, *args):
    """`streamlit run viewer/app.py -- <args>` と同じ引数で、画面をもう 1 回実行する。
    app.py は sys.path にリポジトリのルートを足すので、テストの後に残らないよう、実行の間だけ写しにする。"""
    with mock.patch.object(sys, "argv", ["viewer/app.py", *args]), mock.patch.object(sys, "path", list(sys.path)):
        at.run()
    return at


def start(app, *args):
    return rerun(AppTest.from_file(str(app), default_timeout=TIMEOUT), *args)


def tables(at, first_column):
    """先頭の列の見出しで、表を見分ける。モデル×ベンチマークは「提供企業」、最終取得日は「企業」、詳細は「モデル」。"""
    return [d.value for d in at.dataframe if list(d.value.columns)[:1] == [first_column]]


def main_table(at):
    found = tables(at, "提供企業")
    assert len(found) == 1, f"モデル×ベンチマークの表が {len(found)} 個ある"
    return found[0]


def markdown_texts(at):
    """Markdown として描かれる部品の文字列を、全部集める。"""
    elements = [*at.markdown, *at.info, *at.warning, *at.error, *at.caption, *at.title, *at.subheader, *at.success]
    return [e.value for e in elements]


def select_cell(at, row_index, column_label, *args):
    """表のセルを 1 つ選んだ状態にして、実行し直す(ブラウザでセルを押したときと同じ選択の形)。"""
    key = next(d.key for d in at.dataframe if d.key and d.key.startswith("表の選択:"))
    at.session_state[key] = {"selection": {"rows": [], "columns": [], "cells": [[row_index, column_label]]}}
    return rerun(at, *args)


def row_index_of(table, model, model_type, mode):
    """表(DataFrame)で、モデル・種類・推論モードが合う行の番号。"""
    for i, row in table.iterrows():
        if (row["モデル"], row["種類"], row["推論モード"]) == (model, model_type, mode):
            return i
    raise AssertionError(f"行が無い: {model} / {model_type} / {mode}")


def fixture_record(**overrides):
    """ダミー社B の 1 件目(§3-3 の 16 個のキーがそろった形)を元に、値を差し替えた 1 件。"""
    base = json.loads((FIXTURES / "ダミー社B.json").read_text(encoding="utf-8"))["records"][0]
    return {**base, **overrides}


class OfficialDirMixin:
    """一時ディレクトリに viewer/ を写し、`data/official/` を自分で作って app を動かす。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(REPO_ROOT / "viewer", self.root / "viewer", ignore=shutil.ignore_patterns("__pycache__"))
        self.app = self.root / "viewer" / "app.py"
        self.official = self.root / "data" / "official"

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, content):
        self.official.mkdir(parents=True, exist_ok=True)
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        (self.official / name).write_text(text, encoding="utf-8")

    def assert_no_table_and_no_dummy(self, at):
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.dataframe), 0)  # モデル×ベンチマークの表も、最終取得日も、詳細も出ない
        self.assertFalse(any("ダミーデータ" in t for t in markdown_texts(at) if "--dummy" not in t))


@unittest.skipIf(AppTest is None, SKIP_REASON)
class DummyDataTest(unittest.TestCase):
    def setUp(self):
        self.at = start(APP, "--dummy")

    def select(self, row_index, column_label):
        return select_cell(self.at, row_index, column_label, "--dummy")

    def details(self):
        return tables(self.at, "モデル")

    def test_例外なく描画される(self):
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(len(self.at.error), 0)

    def test_最上部にダミーデータの表示が出る(self):
        # ダミーの fixtures も取得方法は script／manual なので、表示は値ではなく `--dummy` の指定で出す
        first = self.at.main[0]
        self.assertEqual(first.type, "warning")
        self.assertIn("ダミーデータ", first.value)

    def test_読んだ件数は_12_件(self):
        self.assertTrue(any("12 件" in c.value for c in self.at.caption))

    def test_有効性の限界の_3_つがサイドバーに折りたたまずに出る(self):
        text = "\n".join(i.value for i in self.at.sidebar.info)
        self.assertEqual(len(self.at.expander), 0)  # 「常に出すもの」を折りたたみの中に隠さない
        for limit in (
            "公表値は各社の自己申告であり、第三者が検証した値ではない",
            "各社は得意なベンチマークを選んで公表する傾向があり、弱みは「未公表」として現れやすい",
            "手動更新のため、最新モデルの反映に遅れが出る",
        ):
            with self.subTest(limit=limit):
                self.assertIn(limit, text)

    def test_企業ごとの最終取得日がサイドバーに表で出る(self):
        (last,) = [d.value for d in self.at.sidebar.dataframe]
        self.assertEqual(list(last.columns), ["企業", "最終取得日"])
        self.assertEqual(last.values.tolist(), [["ダミー社A", "2026-10-01"], ["ダミー社B", "2026-10-15"]])

    def test_サイドバーの幅を固定する_CSS_は固定の文字列だけ(self):
        (html,) = self.at.html
        self.assertIn('[data-testid="stSidebarResizeHandle"]', html.proto.body)
        self.assertIn("340px", html.proto.body)
        for name in ("ダミー社A", "Model-A1", "Bench-X"):
            self.assertNotIn(name, html.proto.body)

    def test_絞り込みと向きの切り替えはサイドバーにある(self):
        self.assertEqual([m.key for m in self.at.sidebar.multiselect], ["企業"])
        self.assertEqual([r.key for r in self.at.sidebar.radio], ["表の向き"])

    def test_本文は_ダミーの表示_詳細の欄_表の順(self):
        types = [self.at.main[i].type for i in range(len(self.at.main.children))]  # 本文の直下の部品の並び
        self.assertEqual(types[0], "warning")
        self.assertEqual(types.index("flex_container") + 1, types.index("dataframe"))  # 詳細の欄は表のすぐ上

    def test_見出しの列は左に固定し_行の高さを詰める(self):
        (element,) = [d for d in self.at.dataframe if d.key and d.key.startswith("表の選択:")]
        config = json.loads(element.proto.columns)
        self.assertEqual(sorted(k for k, v in config.items() if v.get("pinned")), sorted(["提供企業", "モデル", "種類", "推論モード"]))
        self.assertEqual(element.proto.row_height, 28)

    def test_表は_6_行で_順位や平均の列が無い(self):
        table = main_table(self.at)
        self.assertEqual(len(table), 6)
        self.assertEqual(
            list(table.columns),
            ["提供企業", "モデル", "種類", "推論モード", "Bench-V 2.1", "Bench-W", "Bench-X", "Bench-Y", "Bench-Z"],
        )
        for word in ("順位", "平均", "合計", "総合", "強", "弱"):
            with self.subTest(word=word):
                self.assertFalse(any(word in c for c in table.columns))

    def test_値の無いセルは名指しで未公表_値のあるセルは値(self):
        table = main_table(self.at)
        cases = [
            (("Model-A1", "Instruct", "（なし）"), "Bench-Y", "未公表"),
            (("Model-A2", "（なし）", "（なし）"), "Bench-W", "未公表"),
            (("Model-B2", "（なし）", "Max"), "Bench-X", "未公表"),
            (("Model-B1", "（なし）", "（なし）"), "Bench-Y", "未公表"),
            (("Model-A1", "Reasoning", "High"), "Bench-Y", "1650 Elo"),
            (("Model-B1", "（なし）", "（なし）"), "Bench-Z", "0.91"),
        ]
        for row, column, expected in cases:
            with self.subTest(row=row, column=column):
                self.assertEqual(table.loc[row_index_of(table, *row), column], expected)

    def test_測定条件だけが違う値は_1_つのセルに並び_印が付く(self):
        table = main_table(self.at)
        i = row_index_of(table, "Model-A1", "Reasoning", "High")
        self.assertEqual(table.loc[i, "Bench-W"], "55.1% / 63.4%※")

    def test_企業で絞るとその企業だけになり_既定の向きは絞った後のデータで決まる(self):
        # ダミー社B はモデル 2・ベンチマーク 3。ベンチマークのほうが多いので、既定はベンチマークを行に
        self.at.multiselect(key="企業").set_value(["ダミー社B"])
        rerun(self.at, "--dummy")
        self.assertEqual(self.at.radio(key="表の向き").value, "ベンチマークを行に")
        (table,) = tables(self.at, "ベンチマーク")
        self.assertEqual(list(table.columns), ["ベンチマーク", "Model-B1", "Model-B2 (Max)"])
        self.assertEqual(list(table["ベンチマーク"]), ["提供企業", "Bench-X", "Bench-Y", "Bench-Z"])
        self.assertEqual(table.iloc[0].tolist(), ["提供企業", "ダミー社B", "ダミー社B"])
        (last,) = [d.value for d in self.at.sidebar.dataframe]
        self.assertEqual(last.values.tolist(), [["ダミー社B", "2026-10-15"]])
        # 全社に戻すと、モデル 6・ベンチマーク 5 なので、モデルを行にに戻る(自分で切り替えていないため)
        self.at.multiselect(key="企業").set_value(["ダミー社A", "ダミー社B"])
        rerun(self.at, "--dummy")
        self.assertEqual(self.at.radio(key="表の向き").value, "モデルを行に")
        self.assertEqual(len(main_table(self.at)), 6)

    def test_企業を全部外すと表を出さずに案内する(self):
        self.at.multiselect(key="企業").set_value([])
        rerun(self.at, "--dummy")
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(len(self.at.dataframe), 0)
        self.assertTrue(any("1 つ以上" in i.value for i in self.at.info))

    def test_セルを選ぶ前は詳細を出さず案内だけ出す(self):
        self.assertEqual(len(tables(self.at, "提供企業")), 1)
        self.assertEqual(self.details(), [])
        self.assertTrue(any("セルを 1 つ選ぶと" in c.value for c in self.at.caption))
        self.assertFalse(any("選んだセルは「未公表」" in i.value for i in self.at.info))

    def test_セルを選ぶと詳細に出典_URL_と取得日が出る(self):
        i = row_index_of(main_table(self.at), "Model-A1", "Reasoning", "High")
        self.select(i, "Bench-X")
        self.assertEqual(len(self.at.exception), 0)
        (detail,) = self.details()
        self.assertEqual(len(detail), 1)
        record = detail.iloc[0]
        self.assertEqual(record["スコア"], "81.5%")
        self.assertEqual(record["出典 URL"], "https://example.com/dummy-a/modelcard")
        self.assertEqual(record["取得日"], "2026-10-01")
        self.assertEqual(record["取得者"], "ダミー")
        self.assertEqual(record["取得方法"], "スクリプト")
        self.assertEqual(record["測定条件"], "記載なし")

    def test_詳細の出典_URL_はリンクの列になっている(self):
        i = row_index_of(main_table(self.at), "Model-A1", "Reasoning", "High")
        self.select(i, "Bench-X")
        (element,) = [d for d in self.at.dataframe if list(d.value.columns)[:1] == ["モデル"]]
        config = json.loads(element.proto.columns)
        self.assertEqual(config["出典 URL"]["type_config"]["type"], "link")

    def test_測定条件だけが違う値は詳細に_2_行出る(self):
        i = row_index_of(main_table(self.at), "Model-A1", "Reasoning", "High")
        self.select(i, "Bench-W")
        (detail,) = self.details()
        self.assertEqual(list(detail["測定条件"]), ["Pass@1", "Pass@5"])
        self.assertEqual(list(detail["スコア"]), ["55.1%", "63.4%"])

    def test_手入力の値は取得方法が手入力と出る(self):
        i = row_index_of(main_table(self.at), "Model-A2", "（なし）", "（なし）")
        self.select(i, "Bench-V 2.1")
        (detail,) = self.details()
        self.assertEqual(detail.iloc[0]["取得方法"], "手入力")
        self.assertEqual(detail.iloc[0]["出典 URL"], "https://example.com/dummy-a/blog")

    def test_未公表のセルを選ぶと未公表と出て_詳細の表は出ない(self):
        i = row_index_of(main_table(self.at), "Model-A1", "Instruct", "（なし）")
        self.select(i, "Bench-Y")
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(self.details(), [])
        self.assertTrue(any("選んだセルは「未公表」" in i.value for i in self.at.info))
        self.assertIn("Model-A1 (Instruct) × Bench-Y", [t.value for t in self.at.text])

    def test_ベンチマーク以外の列のセルを選んでも落ちず_詳細は出ない(self):
        self.select(0, "モデル")
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(len(tables(self.at, "提供企業")), 1)
        self.assertEqual(self.details(), [])
        self.assertTrue(any("スコアのセル" in c.value for c in self.at.caption))
        self.assertFalse(any("選んだセルは「未公表」" in i.value for i in self.at.info))

    def test_範囲外の行や存在しない列を選んでも落ちず_詳細は出ない(self):
        for row_index, column in ((99, "Bench-X"), (-1, "Bench-X"), (0, "存在しない列")):
            with self.subTest(row=row_index, column=column):
                self.select(row_index, column)
                self.assertEqual(len(self.at.exception), 0)
                self.assertEqual(len(tables(self.at, "提供企業")), 1)
                self.assertEqual(self.details(), [])
                self.assertEqual(len(self.at.text), 0)  # 未公表のときに出す「モデル × ベンチマーク」も出ない
                self.assertFalse(any("選んだセルは「未公表」" in i.value for i in self.at.info))

    def test_絞り込みを変えると選んでいたセルの詳細は消える(self):
        i = row_index_of(main_table(self.at), "Model-A1", "Reasoning", "High")
        self.select(i, "Bench-X")
        self.assertEqual(len(self.details()), 1)
        self.at.multiselect(key="企業").set_value(["ダミー社B"])
        rerun(self.at, "--dummy")
        self.assertEqual(len(self.at.exception), 0)
        (table,) = tables(self.at, "ベンチマーク")  # 絞った後の既定の向き
        self.assertEqual(table.iloc[0].tolist()[1:], ["ダミー社B", "ダミー社B"])
        self.assertEqual(self.details(), [])
        self.assertTrue(any("セルを 1 つ選ぶと" in c.value for c in self.at.caption))

    # ---- 表の向き ----
    def transpose(self):
        self.at.radio(key="表の向き").set_value("ベンチマークを行に")
        return rerun(self.at, "--dummy")

    def test_向きを入れ替えると_ベンチマークが行_モデルが列になる(self):
        normal = main_table(self.at)
        (first,) = [d for d in self.at.dataframe if d.key and d.key.startswith("表の選択:")]
        modes_before = list(first.proto.selection_mode)
        self.transpose()
        self.assertEqual(len(self.at.exception), 0)
        (table,) = tables(self.at, "ベンチマーク")
        self.assertEqual(list(table.columns)[1:], [
            "Model-A1 (Instruct)", "Model-A1 (Reasoning / High)", "Model-A1 (Reasoning / Non-Think)",
            "Model-A2", "Model-B1", "Model-B2 (Max)",
        ])
        self.assertEqual(list(table["ベンチマーク"]), ["提供企業", "Bench-V 2.1", "Bench-W", "Bench-X", "Bench-Y", "Bench-Z"])
        self.assertEqual(table.loc[2, "Model-A1 (Reasoning / High)"], "55.1% / 63.4%※")
        # セルの総数と、未公表・※ の数は、向きを変えても同じ
        before = normal.iloc[:, 4:].values.ravel().tolist()
        after = table.iloc[1:, 1:].values.ravel().tolist()
        self.assertEqual(len(before), len(after))
        self.assertEqual(before.count("未公表"), after.count("未公表"))
        self.assertEqual(sum("※" in c for c in before), sum("※" in c for c in after))
        (element,) = [d for d in self.at.dataframe if d.key and d.key.startswith("表の選択:")]
        config = json.loads(element.proto.columns)
        self.assertEqual([k for k, v in config.items() if v.get("pinned")], ["ベンチマーク"])
        # セルの選択と、並べ替えを止めるための列の選択は、どちらの向きでも同じ
        self.assertEqual(list(element.proto.selection_mode), modes_before)

    def test_入れ替えた向きでも_セルを選ぶと同じ詳細が出る(self):
        i = row_index_of(main_table(self.at), "Model-A1", "Reasoning", "High")
        self.select(i, "Bench-W")
        (normal,) = self.details()
        self.transpose()
        self.assertEqual(self.details(), [])  # 向きを変えると選択は外れる
        self.select(2, "Model-A1 (Reasoning / High)")  # 2 行目(提供企業の行の次から数えて 2 つ目)= Bench-W
        (transposed,) = self.details()
        self.assertEqual(transposed.values.tolist(), normal.values.tolist())

    def test_入れ替えた向きで提供企業の行やベンチマーク名の列を選んでも詳細は出ない(self):
        self.transpose()
        for row_index, column in ((0, "Model-A2"), (1, "ベンチマーク")):
            with self.subTest(row=row_index, column=column):
                self.select(row_index, column)
                self.assertEqual(len(self.at.exception), 0)
                self.assertEqual(self.details(), [])
                self.assertTrue(any("スコアのセル" in c.value for c in self.at.caption))

    def test_自分で選んだ向きは_絞り込みを変えても保つ(self):
        self.transpose()
        self.at.radio(key="表の向き").set_value("モデルを行に")
        rerun(self.at, "--dummy")
        # ダミー社B だけなら既定はベンチマークを行にだが、自分で選んだモデルを行にを保つ
        self.at.multiselect(key="企業").set_value(["ダミー社B"])
        rerun(self.at, "--dummy")
        self.assertEqual(self.at.radio(key="表の向き").value, "モデルを行に")
        self.assertEqual(set(main_table(self.at)["提供企業"]), {"ダミー社B"})


@unittest.skipIf(AppTest is None, SKIP_REASON)
class OfficialDataTest(OfficialDirMixin, unittest.TestCase):
    """`-- --dummy` を付けずに起動したとき(正式データを読むとき)の表示。"""

    def test_ディレクトリが無いと案内を出し_ダミーに切り替えない(self):
        at = start(self.app)
        self.assert_no_table_and_no_dummy(at)
        self.assertEqual(len(at.error), 1)
        self.assertIn("data/official", at.error[0].value)
        self.assertTrue(any("--dummy" in m.value for m in at.markdown))

    def test_空のディレクトリは_0_件の案内を出す(self):
        self.official.mkdir(parents=True)
        at = start(self.app)
        self.assert_no_table_and_no_dummy(at)
        self.assertEqual(len(at.error), 0)
        self.assertTrue(any("正式データがまだありません" in w.value for w in at.warning))

    def test_records_が空のファイルだけなら_0_件の案内を出す(self):
        self.write("ダミー社B.json", {"records": []})
        at = start(self.app)
        self.assert_no_table_and_no_dummy(at)
        self.assertTrue(any("正式データがまだありません" in w.value for w in at.warning))

    def assert_record_error(self, at, *reasons):
        self.assert_no_table_and_no_dummy(at)
        self.assertEqual(len(at.error), 1)
        self.assertIn("表を出しません", at.error[0].value)
        (code,) = at.code
        for reason in reasons:
            self.assertIn(reason, code.value)

    def test_壊れた_JSON_は理由を出して表を出さない(self):
        self.write("ダミー社B.json", "{壊れた JSON")
        self.assert_record_error(start(self.app), "ダミー社B.json: 読み込めない")

    def test_入れ子が深すぎる_JSON_も理由を出して表を出さない(self):
        self.write("ダミー社B.json", "[" * 100_000)
        self.assert_record_error(start(self.app), "ダミー社B.json: 読み込めない")

    def test_必須のキーが欠けたレコードは理由を出して表を出さない(self):
        record = fixture_record()
        del record["source_url"]
        self.write("ダミー社B.json", {"records": [fixture_record(benchmark="Bench-Q"), record]})
        self.assert_record_error(start(self.app), "ダミー社B.json の 2 件目", "source_url")

    def test_同じ値が_2_件あると理由を出して表を出さない(self):
        self.write("ダミー社B.json", {"records": [fixture_record(), fixture_record()]})
        self.assert_record_error(start(self.app), "ダミー社B.json の 2 件目", "重複か矛盾")

    def test_読める正式データは表を出し_ダミーの表示は出ない(self):
        shutil.copytree(FIXTURES, self.official)
        at = start(self.app)
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(main_table(at)), 6)
        self.assertNotEqual(at.main[0].type, "warning")
        self.assertFalse(any("ダミーデータ" in t for t in markdown_texts(at)))
        self.assertTrue(any("data/official" in c.value and "12 件" in c.value for c in at.caption))

    def test_名前の中の_Markdown_の記号はそのままの文字で出る(self):
        provider = "社*A_1|$x$"
        model = "Model_$y$|**B**"
        model2 = "Model\n# C"
        bench = "Bench|*Y*_[z](u)"
        self.write(
            f"{provider}.json",
            {
                "records": [
                    fixture_record(provider=provider, model=model, benchmark=bench, mode=None),
                    fixture_record(provider=provider, model=model2, benchmark="Bench-Z", mode=None),
                ]
            },
        )
        at = start(self.app)
        self.assertEqual(len(at.exception), 0)
        names = [provider, model, model2, bench]
        # Markdown として描かれる部品には、データ由来の名前が 1 つも入らない
        for text in markdown_texts(at):
            for name in names:
                with self.subTest(text=text, name=name):
                    self.assertNotIn(name, text)
        # 名前は、表の中にそのままの文字で入る
        table = main_table(at)
        self.assertEqual(set(list(table.columns)[4:]), {bench, "Bench-Z"})
        self.assertEqual(set(table["モデル"]), {model, model2})
        self.assertEqual(set(table["提供企業"]), {provider})
        (last,) = tables(at, "企業")
        self.assertEqual(last.values.tolist()[0][0], provider)
        # 未公表のセルを選んだときの名前も、Markdown ではなく st.text で出る
        select_cell(at, row_index_of(table, model, "（なし）", "（なし）"), "Bench-Z")
        self.assertEqual(len(at.exception), 0)
        self.assertIn(f"{model} × Bench-Z", [t.value for t in at.text])
        for text in markdown_texts(at):
            for name in names:
                with self.subTest(text=text, name=name):
                    self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()

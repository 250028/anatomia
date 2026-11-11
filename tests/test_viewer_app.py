"""画面(viewer/app.py)を、Streamlit の AppTest で動かして確かめる。

streamlit が入っていない環境(収集だけを担当して、画面のライブラリを入れていない PC など)では、
import で落とさずに、このファイルのテストを skip にする。ロジック層のテスト(test_viewer_records.py・
test_viewer_grid.py)は streamlit が無くても走る。
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

REPO_ROOT = Path(__file__).resolve().parent.parent
APP = REPO_ROOT / "viewer" / "app.py"
OFFICIAL_DIR = REPO_ROOT / "data" / "official"
# 最初の実行は streamlit の import で数秒かかることがあるので、待ち時間を長めにとる
TIMEOUT = 60


def run_app(*args):
    """`streamlit run viewer/app.py -- <args>` と同じ引数で、画面を 1 回実行する。"""
    at = AppTest.from_file(str(APP), default_timeout=TIMEOUT)
    with mock.patch.object(sys, "argv", [str(APP), *args]):
        at.run()
    return at


def select_cell(at, row_index, column_label):
    """表のセルを 1 つ選んだ状態にして、実行し直す(ブラウザでセルを押したときと同じ選択の形)。"""
    key = at.dataframe[0].key
    at.session_state[key] = {"selection": {"rows": [], "columns": [], "cells": [[row_index, column_label]]}}
    with mock.patch.object(sys, "argv", [str(APP), "--dummy"]):
        at.run()
    return at


def row_index_of(table, model, model_type, mode):
    """表(DataFrame)で、モデル・種類・推論モードが合う行の番号。"""
    for i, row in table.iterrows():
        if (row["モデル"], row["種類"], row["推論モード"]) == (model, model_type, mode):
            return i
    raise AssertionError(f"行が無い: {model} / {model_type} / {mode}")


@unittest.skipIf(AppTest is None, "streamlit が入っていない(画面のテストは skip)")
class DummyDataTest(unittest.TestCase):
    def setUp(self):
        self.at = run_app("--dummy")

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

    def test_有効性の限界の_3_つが出る(self):
        text = "\n".join(i.value for i in self.at.info)
        for limit in (
            "公表値は各社の自己申告であり、第三者が検証した値ではない",
            "各社は得意なベンチマークを選んで公表する傾向があり、弱みは「未公表」として現れやすい",
            "手動更新のため、最新モデルの反映に遅れが出る",
        ):
            with self.subTest(limit=limit):
                self.assertIn(limit, text)

    def test_企業ごとの最終取得日が出る(self):
        text = "\n".join(m.value for m in self.at.markdown)
        self.assertIn("ダミー社A：2026-10-01", text)
        self.assertIn("ダミー社B：2026-10-15", text)

    def test_表は_6_行で_未公表が出て_順位や平均の列が無い(self):
        table = self.at.dataframe[0].value
        self.assertEqual(len(table), 6)
        self.assertEqual(
            list(table.columns),
            ["提供企業", "モデル", "種類", "推論モード", "Bench-V 2.1", "Bench-W", "Bench-X", "Bench-Y", "Bench-Z"],
        )
        self.assertIn("未公表", table.values.tolist()[0])
        for word in ("順位", "平均", "合計", "総合", "強", "弱"):
            with self.subTest(word=word):
                self.assertFalse(any(word in c for c in table.columns))

    def test_企業で絞ると行が減り_最終取得日もその企業だけになる(self):
        self.at.multiselect(key="企業").set_value(["ダミー社B"])
        with mock.patch.object(sys, "argv", [str(APP), "--dummy"]):
            self.at.run()
        table = self.at.dataframe[0].value
        self.assertEqual(len(table), 2)
        self.assertEqual(set(table["提供企業"]), {"ダミー社B"})
        text = "\n".join(m.value for m in self.at.markdown)
        self.assertIn("ダミー社B：2026-10-15", text)
        self.assertNotIn("ダミー社A", text)

    def test_企業を全部外すと表を出さずに案内する(self):
        self.at.multiselect(key="企業").set_value([])
        with mock.patch.object(sys, "argv", [str(APP), "--dummy"]):
            self.at.run()
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(len(self.at.dataframe), 0)
        self.assertTrue(any("1 つ以上" in i.value for i in self.at.info))

    def test_セルを選ぶ前は詳細を出さない(self):
        self.assertEqual(len(self.at.dataframe), 1)

    def test_セルを選ぶと詳細に出典_URL_と取得日が出る(self):
        i = row_index_of(self.at.dataframe[0].value, "Model-A1", "Reasoning", "High")
        select_cell(self.at, i, "Bench-X")
        self.assertEqual(len(self.at.exception), 0)
        detail = self.at.dataframe[1].value
        self.assertEqual(len(detail), 1)
        record = detail.iloc[0]
        self.assertEqual(record["スコア"], "81.5%")
        self.assertEqual(record["出典 URL"], "https://example.com/dummy-a/modelcard")
        self.assertEqual(record["取得日"], "2026-10-01")
        self.assertEqual(record["取得者"], "ダミー")
        self.assertEqual(record["取得方法"], "スクリプト")
        self.assertEqual(record["測定条件"], "記載なし")

    def test_測定条件だけが違う値は詳細に_2_行出る(self):
        i = row_index_of(self.at.dataframe[0].value, "Model-A1", "Reasoning", "High")
        select_cell(self.at, i, "Bench-W")
        detail = self.at.dataframe[1].value
        self.assertEqual(list(detail["測定条件"]), ["Pass@1", "Pass@5"])

    def test_手入力の値は取得方法が手入力と出る(self):
        i = row_index_of(self.at.dataframe[0].value, "Model-A2", "（なし）", "（なし）")
        select_cell(self.at, i, "Bench-V 2.1")
        detail = self.at.dataframe[1].value
        self.assertEqual(detail.iloc[0]["取得方法"], "手入力")
        self.assertEqual(detail.iloc[0]["出典 URL"], "https://example.com/dummy-a/blog")

    def test_未公表のセルを選ぶと未公表と出る(self):
        i = row_index_of(self.at.dataframe[0].value, "Model-A1", "Instruct", "（なし）")
        select_cell(self.at, i, "Bench-Y")
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(len(self.at.dataframe), 1)
        self.assertTrue(any("未公表" in i.value for i in self.at.info))

    def test_ベンチマーク以外の列のセルを選んでも落ちない(self):
        select_cell(self.at, 0, "モデル")
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(len(self.at.dataframe), 1)

    def test_絞り込みを変えると選んでいたセルの詳細は消える(self):
        i = row_index_of(self.at.dataframe[0].value, "Model-A1", "Reasoning", "High")
        select_cell(self.at, i, "Bench-X")
        self.assertEqual(len(self.at.dataframe), 2)
        self.at.multiselect(key="企業").set_value(["ダミー社B"])
        with mock.patch.object(sys, "argv", [str(APP), "--dummy"]):
            self.at.run()
        self.assertEqual(len(self.at.exception), 0)
        self.assertEqual(len(self.at.dataframe), 1)


@unittest.skipIf(AppTest is None, "streamlit が入っていない(画面のテストは skip)")
@unittest.skipIf(OFFICIAL_DIR.exists(), "data/official/ があるので、「正式データが無いとき」は確かめられない")
class NoOfficialDataTest(unittest.TestCase):
    def test_正式データが無いと案内を出し_ダミーに切り替えない(self):
        at = run_app()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.error), 1)
        self.assertIn("data/official", at.error[0].value)
        self.assertTrue(any("--dummy" in m.value for m in at.markdown))
        # ダミーの表示も、表も出ない
        self.assertFalse(any("ダミーデータを表示" in w.value for w in at.warning))
        self.assertEqual(len(at.dataframe), 0)


if __name__ == "__main__":
    unittest.main()

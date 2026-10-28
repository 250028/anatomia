import ast
import json
import tempfile
import unittest
from pathlib import Path

from viewer import records
from viewer.records import RecordError, load_official, record_from_dict

# ダミー社A・Bの合成データ(実在しない会社・モデル。出典は example.com)
FIXTURES = Path(__file__).parent / "fixtures" / "official"
VIEWER = Path(__file__).parent.parent / "viewer"


def valid(**overrides):
    base = {
        "provider": "ダミー社C",
        "model": "Model-C1",
        "benchmark": "Bench-X",
        "score": 50.0,
        "unit": "%",
        "source_url": "https://example.com/dummy-c",
        "retrieved_at": "2026-10-20",
        "retrieved_by": "ダミー",
        "retrieval_method": "ダミー",
    }
    base.update(overrides)
    return base


def without(*keys, **overrides):
    d = valid(**overrides)
    for k in keys:
        d.pop(k, None)
    return d


class ImportBoundaryTest(unittest.TestCase):
    def test_ロジック層は_streamlit_requests_pandas_を_import_しない(self):
        for path in (VIEWER / "records.py", VIEWER / "grid.py"):
            imported = set()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    imported |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imported.add(node.module.split(".")[0])
            with self.subTest(file=path.name):
                self.assertFalse(imported & {"streamlit", "requests", "pandas"})


class RecordFromDictTest(unittest.TestCase):
    def test_必須のキーだけでも読める(self):
        r = record_from_dict(valid())
        self.assertEqual((r.provider, r.model, r.score, r.unit), ("ダミー社C", "Model-C1", 50.0, "%"))
        self.assertIsNone(r.mode)
        self.assertIsNone(r.condition)

    def test_出典のキーが無いと失敗する(self):
        for key in ("source_url", "retrieved_at", "retrieved_by"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError) as cm:
                    record_from_dict(without(key))
                self.assertIn(key, str(cm.exception))

    def test_出典が空や_null_でも失敗する(self):
        for key in ("source_url", "retrieved_at", "retrieved_by"):
            for bad in ("", "  ", None):
                with self.subTest(key=key, bad=bad):
                    with self.assertRaises(ValueError):
                        record_from_dict(valid(**{key: bad}))

    def test_取得日が日付でないと失敗する(self):
        with self.assertRaises(ValueError):
            record_from_dict(valid(retrieved_at="昨日"))

    def test_スコアが数値でないと失敗する(self):
        for bad in ("72.5", None, True, float("nan")):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    record_from_dict(valid(score=bad))

    def test_任意のキーは省いても_null_でも空文字でも_None_になる(self):
        for key in ("unit", "mode", "model_type", "benchmark_version", "condition", "sha", "as_of", "raw_value"):
            for form in ("省く", None, ""):
                with self.subTest(key=key, form=form):
                    raw = without(key) if form == "省く" else valid(**{key: form})
                    self.assertIsNone(getattr(record_from_dict(raw), key))

    def test_provider_はキーだけでもファイル名だけでもよい(self):
        self.assertEqual(record_from_dict(valid(), file_provider=None).provider, "ダミー社C")
        self.assertEqual(record_from_dict(without("provider"), file_provider="ダミー社C").provider, "ダミー社C")

    def test_provider_がキーとファイル名で食い違うと失敗する(self):
        with self.assertRaises(ValueError):
            record_from_dict(valid(), file_provider="ダミー社D")

    def test_provider_がどこにも無いと失敗する(self):
        with self.assertRaises(ValueError):
            record_from_dict(without("provider"))

    def test_取得方法は_script_manual_以外の表記も受け付ける(self):
        self.assertEqual(record_from_dict(valid(retrieval_method="手入力")).retrieval_method, "手入力")
        self.assertEqual(records.retrieval_method_label("script"), "スクリプト")
        self.assertEqual(records.retrieval_method_label("manual"), "手入力")
        self.assertEqual(records.retrieval_method_label("ダミー"), "ダミー")


class LoadOfficialTest(unittest.TestCase):
    def write(self, tmp, name, data):
        (Path(tmp) / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_ダミーのディレクトリを会社をまたいで全部読む(self):
        loaded = load_official(FIXTURES)
        self.assertEqual({r.provider for r in loaded}, {"ダミー社A", "ダミー社B"})
        self.assertEqual(len(loaded), 12)

    def test_ファイルの外形は_records_のオブジェクトでも配列でもよい(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", {"records": [valid()]})
            self.write(tmp, "ダミー社D.json", [valid(provider="ダミー社D")])
            self.assertEqual(len(load_official(tmp)), 2)

    def test_出典の無いレコードがあると読み込み全体が失敗する(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", [valid(), without("source_url")])
            with self.assertRaises(RecordError) as cm:
                load_official(tmp)
            self.assertEqual(len(cm.exception.problems), 1)
            self.assertIn("2 件目", cm.exception.problems[0])
            self.assertIn("source_url", cm.exception.problems[0])

    def test_問題は止める前に全件を集める(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", [without("source_url"), without("retrieved_by")])
            self.write(tmp, "ダミー社D.json", {"foo": 1})
            (Path(tmp) / "ダミー社E.json").write_text("{壊れた JSON", encoding="utf-8")
            with self.assertRaises(RecordError) as cm:
                load_official(tmp)
            self.assertEqual(len(cm.exception.problems), 4)

    def test_ファイル名とレコードの_provider_が食い違うと失敗する(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社D.json", [valid()])
            with self.assertRaises(RecordError):
                load_official(tmp)

    def test_ディレクトリが無い_空のときは空のリスト(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_official(tmp), [])
            self.assertEqual(load_official(Path(tmp) / "無い"), [])


if __name__ == "__main__":
    unittest.main()

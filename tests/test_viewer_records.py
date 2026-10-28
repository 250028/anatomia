import ast
import json
import sys
import tempfile
import unittest
from pathlib import Path

from viewer import records
from viewer.records import RecordError, load_official, record_from_dict

# ダミー社A・Bの合成データ(実在しない会社・モデル。出典は example.com)
FIXTURES = Path(__file__).parent / "fixtures" / "official"
VIEWER = Path(__file__).parent.parent / "viewer"
# ロジック層(viewer/*.py。画面の app.py を除く)が import してよいのは、標準ライブラリと viewer だけ
LOGIC_FILES = sorted(p for p in VIEWER.glob("*.py") if p.name != "app.py")
ALLOWED_IMPORTS = set(sys.stdlib_module_names) | {"viewer"}


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
    def test_ロジック層のファイルがある(self):
        self.assertTrue({"records.py", "grid.py"} <= {p.name for p in LOGIC_FILES})

    def test_ロジック層は標準ライブラリと_viewer_しか_import_しない(self):
        for path in LOGIC_FILES:
            imported = set()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    imported |= {a.name.split(".")[0] for a in node.names}
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imported.add(node.module.split(".")[0])
            with self.subTest(file=path.name):
                self.assertEqual(imported - ALLOWED_IMPORTS, set())


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
        # 20261020・2026-W43-2 は date.fromisoformat が通すので、形も確かめる。全角数字・時刻付きも誤り
        for bad in ("昨日", "2026-13-45", "20261020", "2026-W43-2", "2026-10-20T00:00:00", "２０２６-１０-２０", "2026-1-5"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    record_from_dict(valid(retrieved_at=bad))

    def test_取得日は元の文字列のまま保たれる(self):
        self.assertEqual(record_from_dict(valid(retrieved_at=" 2026-10-20 ")).retrieved_at, "2026-10-20")

    def test_出典_URL_は_http_か_https_で始まるものだけ(self):
        for bad in ("N/A", "なし", "javascript:alert(1)", "ftp://example.com/x", "example.com/x", "//example.com"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as cm:
                    record_from_dict(valid(source_url=bad))
                self.assertIn("source_url", str(cm.exception))
        for ok in ("http://example.com/x", "https://example.com/x", "HTTPS://example.com/x"):
            with self.subTest(ok=ok):
                self.assertEqual(record_from_dict(valid(source_url=ok)).source_url, ok)

    def test_必須の文字列は前後の空白を落とす(self):
        r = record_from_dict(valid(model="  M  ", benchmark=" B ", source_url=" https://example.com/x ", retrieved_by=" 人 "))
        self.assertEqual((r.model, r.benchmark, r.source_url, r.retrieved_by), ("M", "B", "https://example.com/x", "人"))

    def test_任意のキーが文字列でないと失敗する(self):
        for key in ("unit", "mode", "model_type", "benchmark_version", "condition", "sha", "as_of", "raw_value"):
            for bad in (5, ["x"], True):
                with self.subTest(key=key, bad=bad):
                    with self.assertRaises(ValueError) as cm:
                        record_from_dict(valid(**{key: bad}))
                    self.assertIn(key, str(cm.exception))

    def test_スコアが数値でないと失敗する(self):
        for bad in ("72.5", None, True, float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    record_from_dict(valid(score=bad))

    def test_桁数の大きい整数は_OverflowError_でなく_ValueError_になる(self):
        for bad in (10**400, -(10**400)):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as cm:
                    record_from_dict(valid(score=bad))
                self.assertNotIsInstance(cm.exception, OverflowError)

    def test_大きくても有限の整数は読める(self):
        self.assertEqual(record_from_dict(valid(score=10**300)).score, 10**300)

    def test_0_と負の数も読める(self):
        self.assertEqual(record_from_dict(valid(score=0)).score, 0)
        self.assertEqual(record_from_dict(valid(score=-1.5)).score, -1.5)

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

    def test_空のディレクトリは空のリスト(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_official(tmp), [])
            (Path(tmp) / "メモ.txt").write_text("json でない", encoding="utf-8")
            self.assertEqual(load_official(tmp), [])

    def test_存在しないパスはデータなしでなくエラー(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_official(Path(tmp) / "無い")
            file_path = Path(tmp) / "a.json"
            file_path.write_text("[]", encoding="utf-8")
            with self.assertRaises(NotADirectoryError):
                load_official(file_path)

    def test_同じ組のレコードが重なると失敗する(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", [valid(score=1.0), valid(score=2.0)])
            with self.assertRaises(RecordError) as cm:
                load_official(tmp)
            self.assertEqual(len(cm.exception.problems), 1)
            self.assertIn("2 件目", cm.exception.problems[0])
            self.assertIn("1 件目", cm.exception.problems[0])

    def test_完全に同じレコードの重複も失敗する(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", [valid(), valid()])
            with self.assertRaises(RecordError):
                load_official(tmp)

    def test_空白だけが違う組も重複とみなす(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", [valid(condition=None), valid(condition="  ")])
            with self.assertRaises(RecordError):
                load_official(tmp)

    def test_測定条件_版_モード_種類のどれかが違えば重複でない(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(
                tmp,
                "ダミー社C.json",
                [
                    valid(),
                    valid(condition="Pass@1"),
                    valid(condition="Pass@5"),
                    valid(benchmark_version="2.1"),
                    valid(mode="High"),
                    valid(model_type="Instruct"),
                    valid(benchmark="Bench-Y"),
                    valid(model="Model-C2"),
                ],
            )
            self.assertEqual(len(load_official(tmp)), 8)


if __name__ == "__main__":
    unittest.main()

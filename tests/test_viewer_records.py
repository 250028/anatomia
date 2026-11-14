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


# 企画書 §3-3 の表のキーのうち、必須のもの(null・空文字は誤り)と、任意のもの(null でよい)
REQUIRED_KEYS = ("model", "provider", "benchmark", "score", "raw_value", "source_url", "retrieved_at", "retrieved_by", "retrieval_method")
OPTIONAL_KEYS = ("model_type", "mode", "benchmark_version", "unit", "condition", "sha", "as_of")


def valid(**overrides):
    """§3-3 の 16 個のキーをすべて置いた 1 件(任意のキーは null)。"""
    base = {
        "model": "Model-C1",
        "provider": "ダミー社C",
        "model_type": None,
        "mode": None,
        "benchmark": "Bench-X",
        "benchmark_version": None,
        "score": 50.0,
        "unit": "%",
        "condition": None,
        "raw_value": "ダミー値 50.0",
        "source_url": "https://example.com/dummy-c",
        "retrieved_at": "2026-10-20",
        "retrieved_by": "ダミー",
        "retrieval_method": "script",
        "sha": None,
        "as_of": None,
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
    def test_すべてのキーを置いた正しい形は読める(self):
        r = record_from_dict(valid())
        self.assertEqual((r.provider, r.model, r.score, r.unit), ("ダミー社C", "Model-C1", 50.0, "%"))
        self.assertEqual((r.raw_value, r.retrieval_method), ("ダミー値 50.0", "script"))
        self.assertIsNone(r.mode)
        self.assertIsNone(r.condition)

    def test_任意のキーに値があれば読める(self):
        r = record_from_dict(
            valid(model_type="Reasoning", mode="High", benchmark_version="2.1", condition="Pass@1", sha="0" * 40, as_of="2026-10-05")
        )
        self.assertEqual((r.model_type, r.mode, r.benchmark_version, r.condition, r.sha, r.as_of), ("Reasoning", "High", "2.1", "Pass@1", "0" * 40, "2026-10-05"))

    def test_表のキーが一つでも無いと理由つきで失敗する(self):
        # §3-3「表のキーは常に置き、値がないときは null」。必須でも任意でも、キーを省くのは誤り
        for key in REQUIRED_KEYS + OPTIONAL_KEYS:
            with self.subTest(key=key):
                with self.assertRaises(ValueError) as cm:
                    record_from_dict(without(key))
                self.assertIn(f"`{key}`", str(cm.exception))
                self.assertIn("null", str(cm.exception))

    def test_キーが複数足りないときは全部を挙げる(self):
        with self.assertRaises(ValueError) as cm:
            record_from_dict(without("unit", "sha"))
        self.assertIn("`unit`", str(cm.exception))
        self.assertIn("`sha`", str(cm.exception))

    def test_表にないキーがあると理由つきで失敗する(self):
        # §3-3「正式データに入れるのは、下の表のキーだけ」(例: Google の benchmark_description)
        with self.assertRaises(ValueError) as cm:
            record_from_dict(valid(benchmark_description="説明文"))
        self.assertIn("`benchmark_description`", str(cm.exception))

    def test_必須のキーが_null_や空文字だと失敗する(self):
        for key in REQUIRED_KEYS:
            for bad in (None, "", "  "):
                with self.subTest(key=key, bad=bad):
                    with self.assertRaises(ValueError) as cm:
                        record_from_dict(valid(**{key: bad}))
                    self.assertIn(key, str(cm.exception))

    def test_取得元の表記は必須(self):
        # 以前は無くても読めた。§3-3 の表「取得元の表記 `raw_value` 必須」
        with self.assertRaises(ValueError) as cm:
            record_from_dict(valid(raw_value=None))
        self.assertIn("raw_value", str(cm.exception))

    def test_取得日が日付でないと失敗する(self):
        # 20261020・2026-W43-2 は date.fromisoformat が通すので、形も確かめる。全角数字・時刻付きも誤り
        for bad in ("昨日", "2026-13-45", "20261020", "2026-W43-2", "2026-10-20T00:00:00", "２０２６-１０-２０", "2026-1-5"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as cm:
                    record_from_dict(valid(retrieved_at=bad))
                self.assertIn("retrieved_at", str(cm.exception))

    def test_取得元ページの日付は_null_か_YYYY_MM_DD_だけ(self):
        # §3-3「日付(`retrieved_at`・`as_of`)は `YYYY-MM-DD`」。年月だけ(May, 2026)などは誤り
        self.assertIsNone(record_from_dict(valid(as_of=None)).as_of)
        self.assertEqual(record_from_dict(valid(as_of="2026-10-05")).as_of, "2026-10-05")
        for bad in ("May, 2026", "2026-05", "2026-13-45", "20261005", "２０２６-１０-０５", "2026-10-05T00:00:00"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as cm:
                    record_from_dict(valid(as_of=bad))
                self.assertIn("as_of", str(cm.exception))

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
        r = record_from_dict(valid(model="  M  ", benchmark=" B ", source_url=" https://example.com/x ", retrieved_by=" 人 ", raw_value=" 72.5% "))
        self.assertEqual((r.model, r.benchmark, r.source_url, r.retrieved_by, r.raw_value), ("M", "B", "https://example.com/x", "人", "72.5%"))

    def test_任意のキーが文字列でも_null_でもないと失敗する(self):
        for key in OPTIONAL_KEYS:
            for bad in (5, ["x"], True):
                with self.subTest(key=key, bad=bad):
                    with self.assertRaises(ValueError) as cm:
                        record_from_dict(valid(**{key: bad}))
                    self.assertIn(key, str(cm.exception))

    def test_必須の文字列が文字列でないと失敗する(self):
        for key in ("model", "provider", "benchmark", "raw_value", "source_url", "retrieved_by", "retrieval_method"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError) as cm:
                    record_from_dict(valid(**{key: 5}))
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

    def test_任意のキーは_null_でも空文字でも_None_になる(self):
        # 空文字の扱いは §3-3 に書いていないので、これまでどおり None にする(未決の点として報告)
        for key in OPTIONAL_KEYS:
            for form in (None, ""):
                with self.subTest(key=key, form=form):
                    self.assertIsNone(getattr(record_from_dict(valid(**{key: form})), key))

    def test_provider_はレコードの値が正でファイル名と同じなら読める(self):
        self.assertEqual(record_from_dict(valid(), file_provider=None).provider, "ダミー社C")
        self.assertEqual(record_from_dict(valid(), file_provider="ダミー社C").provider, "ダミー社C")

    def test_provider_がキーとファイル名で食い違うと失敗する(self):
        with self.assertRaises(ValueError) as cm:
            record_from_dict(valid(), file_provider="ダミー社D")
        self.assertIn("provider", str(cm.exception))

    def test_provider_がレコードに無いとファイル名があっても失敗する(self):
        # 以前はファイル名で代用していた。§3-3「レコードの `provider` を正とし、ファイル名は入れ物の名前」
        with self.assertRaises(ValueError) as cm:
            record_from_dict(without("provider"), file_provider="ダミー社C")
        self.assertIn("`provider`", str(cm.exception))
        with self.assertRaises(ValueError):
            record_from_dict(without("provider"))

    def test_取得方法は_script_か_manual_だけ(self):
        for ok in ("script", "manual"):
            with self.subTest(ok=ok):
                self.assertEqual(record_from_dict(valid(retrieval_method=ok)).retrieval_method, ok)
        for bad in ("手入力", "スクリプト", "ダミー", "Script", "MANUAL", "scripts"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as cm:
                    record_from_dict(valid(retrieval_method=bad))
                self.assertIn("retrieval_method", str(cm.exception))

    def test_取得方法の表示名(self):
        self.assertEqual(records.retrieval_method_label("script"), "スクリプト")
        self.assertEqual(records.retrieval_method_label("manual"), "手入力")


class LoadOfficialTest(unittest.TestCase):
    def write(self, tmp, name, data):
        (Path(tmp) / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_ダミーのディレクトリを会社をまたいで全部読む(self):
        loaded = load_official(FIXTURES)
        self.assertEqual({r.provider for r in loaded}, {"ダミー社A", "ダミー社B"})
        self.assertEqual(len(loaded), 12)

    def test_ダミーのファイルは_16_個のキーをそろえた_records_の形(self):
        for path in sorted(FIXTURES.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(file=path.name):
                self.assertEqual(list(data), ["records"])
                for raw in data["records"]:
                    self.assertEqual(list(raw), list(records.OFFICIAL_KEYS))

    def test_ファイルの外形は_records_のオブジェクト(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", {"records": [valid()]})
            self.write(tmp, "ダミー社D.json", {"records": [valid(provider="ダミー社D")]})
            self.assertEqual(len(load_official(tmp)), 2)

    def test_配列だけの外形は理由つきで失敗する(self):
        # 以前は受け付けていた。§3-3「ファイルの外形: `{"records": [...]}`」
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", [valid()])
            with self.assertRaises(RecordError) as cm:
                load_official(tmp)
            self.assertEqual(len(cm.exception.problems), 1)
            self.assertIn("ダミー社C.json", cm.exception.problems[0])
            self.assertIn("records", cm.exception.problems[0])

    def test_records_が配列でないオブジェクトも失敗する(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", {"records": valid()})
            with self.assertRaises(RecordError):
                load_official(tmp)

    def test_出典の無いレコードがあると読み込み全体が失敗する(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", {"records": [valid(), without("source_url")]})
            with self.assertRaises(RecordError) as cm:
                load_official(tmp)
            self.assertEqual(len(cm.exception.problems), 1)
            self.assertIn("2 件目", cm.exception.problems[0])
            self.assertIn("source_url", cm.exception.problems[0])

    def test_問題は止める前に全件を集める(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", {"records": [without("source_url"), without("retrieved_by")]})
            self.write(tmp, "ダミー社D.json", {"foo": 1})
            (Path(tmp) / "ダミー社E.json").write_text("{壊れた JSON", encoding="utf-8")
            with self.assertRaises(RecordError) as cm:
                load_official(tmp)
            self.assertEqual(len(cm.exception.problems), 4)

    def test_入れ子が深すぎる_JSON_も読めないファイルとして理由に入る(self):
        # json.loads は RecursionError(ValueError ではない)を出す。traceback にせず、ほかの壊れた JSON と同じに扱う
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "ダミー社C.json").write_text("[" * 100_000, encoding="utf-8")
            self.write(tmp, "ダミー社D.json", {"records": [valid(provider="ダミー社D")]})
            with self.assertRaises(RecordError) as cm:
                load_official(tmp)
            self.assertEqual(len(cm.exception.problems), 1)
            self.assertIn("ダミー社C.json: 読み込めない", cm.exception.problems[0])

    def test_ファイル名とレコードの_provider_が食い違うと失敗する(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社D.json", {"records": [valid()]})
            with self.assertRaises(RecordError):
                load_official(tmp)

    def test_キーの足りないレコードは何件目かと足りないキーを示して止まる(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", {"records": [valid(), without("as_of")]})
            with self.assertRaises(RecordError) as cm:
                load_official(tmp)
            self.assertEqual(len(cm.exception.problems), 1)
            self.assertIn("ダミー社C.json の 2 件目", cm.exception.problems[0])
            self.assertIn("`as_of`", cm.exception.problems[0])

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
            self.write(tmp, "ダミー社C.json", {"records": [valid(score=1.0), valid(score=2.0)]})
            with self.assertRaises(RecordError) as cm:
                load_official(tmp)
            self.assertEqual(len(cm.exception.problems), 1)
            self.assertIn("2 件目", cm.exception.problems[0])
            self.assertIn("1 件目", cm.exception.problems[0])

    def test_完全に同じレコードの重複も失敗する(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", {"records": [valid(), valid()]})
            with self.assertRaises(RecordError):
                load_official(tmp)

    def test_空白だけが違う組も重複とみなす(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(tmp, "ダミー社C.json", {"records": [valid(condition=None), valid(condition="  ")]})
            with self.assertRaises(RecordError):
                load_official(tmp)

    def test_測定条件_版_モード_種類のどれかが違えば重複でない(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.write(
                tmp,
                "ダミー社C.json",
                {"records": [
                    valid(),
                    valid(condition="Pass@1"),
                    valid(condition="Pass@5"),
                    valid(benchmark_version="2.1"),
                    valid(mode="High"),
                    valid(model_type="Instruct"),
                    valid(benchmark="Bench-Y"),
                    valid(model="Model-C2"),
                ]},
            )
            self.assertEqual(len(load_official(tmp)), 8)


if __name__ == "__main__":
    unittest.main()

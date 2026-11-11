import json
import tempfile
import unittest
import warnings
from pathlib import Path

from scraper.to_official import (
    OFFICIAL_KEYS,
    ConversionError,
    convert,
    read_manual_csv,
    read_scraper_json,
    write_official,
)

HEADER = "モデル名,モデルの種類,推論モード,ベンチマーク名,ベンチマークの版・種類,スコア,単位,測定条件,取得元の表記,出典URL,取得日,取得者,READMEの版(sha),備考"
ROW = "Model-X,Instruct,High,Bench A,v2,72.5,%,ツールなし,72.5%,https://example.test/card,2026-11-11,tester,{sha},メモ"
SHA = "a" * 40


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def write(self, name, text, encoding="utf-8"):
        path = self.dir / name
        path.write_bytes(text.encode(encoding))
        return path

    def csv(self, *rows, name="Acme.csv", header=HEADER, encoding="utf-8"):
        return self.write(name, "\n".join([header, *rows]) + "\n", encoding)


class ReadManualCsvTest(TempDirTestCase):
    def test_1行を_3_3_のキーに変換する(self):
        (r,) = read_manual_csv(self.csv(ROW.format(sha=SHA)))
        self.assertEqual(list(r), OFFICIAL_KEYS)
        self.assertEqual(
            r,
            {
                "model": "Model-X",
                "provider": "Acme",
                "model_type": "Instruct",
                "mode": "High",
                "benchmark": "Bench A",
                "benchmark_version": "v2",
                "score": 72.5,
                "unit": "%",
                "condition": "ツールなし",
                "raw_value": "72.5%",
                "source_url": "https://example.test/card",
                "retrieved_at": "2026-11-11",
                "retrieved_by": "tester",
                "retrieval_method": "manual",
                "sha": SHA,
                "as_of": None,
            },
        )

    def test_提供企業はファイル名から取る(self):
        (r,) = read_manual_csv(self.csv(ROW.format(sha=""), name="OpenAI.csv"))
        self.assertEqual(r["provider"], "OpenAI")

    def test_空欄の任意の列は_null_にする(self):
        row = "Model-X,,,Bench A,,72.5,,,72.5,https://example.test/card,2026-11-11,tester,,"
        (r,) = read_manual_csv(self.csv(row))
        for key in ["model_type", "mode", "benchmark_version", "unit", "condition", "sha", "as_of"]:
            with self.subTest(key=key):
                self.assertIsNone(r[key])

    def test_備考は正式データに入れない(self):
        (r,) = read_manual_csv(self.csv(ROW.format(sha="")))
        self.assertNotIn("備考", r)
        self.assertNotIn("メモ", r.values())

    def test_スコアは数値に直す(self):
        row = "Model-X,,,Bench A,,1657,,,\"1,657\",https://example.test/card,2026-11-11,tester,,"
        (r,) = read_manual_csv(self.csv(row))
        self.assertEqual((r["score"], r["raw_value"]), (1657.0, "1,657"))

    def test_BOM_付きでも読める(self):
        path = self.csv(ROW.format(sha=""), encoding="utf-8-sig")
        self.assertEqual(len(read_manual_csv(path)), 1)

    def test_空行は読み飛ばす(self):
        path = self.write("Acme.csv", HEADER + "\n" + ROW.format(sha="") + "\n\n,,,,,,,,,,,,,\n")
        self.assertEqual(len(read_manual_csv(path)), 1)

    def test_見出しが違うと止まる(self):
        path = self.csv(ROW.format(sha=""), header=HEADER.replace("スコア", "点数"))
        with self.assertRaisesRegex(ConversionError, "見出し"):
            read_manual_csv(path)

    def test_必須の列が空なら_行番号と列名を示して止まる(self):
        for column, row in [
            ("出典URL", "Model-X,,,Bench A,,72.5,,,72.5,,2026-11-11,tester,,"),
            ("取得日", "Model-X,,,Bench A,,72.5,,,72.5,https://example.test/card,,tester,,"),
            ("取得者", "Model-X,,,Bench A,,72.5,,,72.5,https://example.test/card,2026-11-11,,,"),
            ("取得元の表記", "Model-X,,,Bench A,,72.5,,,,https://example.test/card,2026-11-11,tester,,"),
            ("モデル名", ",,,Bench A,,72.5,,,72.5,https://example.test/card,2026-11-11,tester,,"),
            ("ベンチマーク名", "Model-X,,,,,72.5,,,72.5,https://example.test/card,2026-11-11,tester,,"),
        ]:
            with self.subTest(column=column):
                with self.assertRaisesRegex(ConversionError, rf"2 行目.*{column}"):
                    read_manual_csv(self.csv(row))

    def test_スコアが数字でなければ止まる(self):
        row = "Model-X,,,Bench A,,約72,,,約72,https://example.test/card,2026-11-11,tester,,"
        with self.assertRaisesRegex(ConversionError, "2 行目.*スコア"):
            read_manual_csv(self.csv(row))

    def test_取得日が_YYYY_MM_DD_でなければ止まる(self):
        for bad in ["2026/11/11", "2026-13-01", "11-11"]:
            with self.subTest(bad=bad):
                row = f"Model-X,,,Bench A,,72.5,,,72.5,https://example.test/card,{bad},tester,,"
                with self.assertRaisesRegex(ConversionError, "取得日"):
                    read_manual_csv(self.csv(row))

    def test_shaは40桁の16進数だけ(self):
        with self.assertRaisesRegex(ConversionError, "sha"):
            read_manual_csv(self.csv(ROW.format(sha="abc123")))

    def test_列の数が見出しと違う行は止まる(self):
        with self.assertRaisesRegex(ConversionError, "3 行目.*列の数"):
            read_manual_csv(self.csv(ROW.format(sha=""), "Model-X,,,Bench A"))


SCRAPER_RECORD = {
    "provider": "Google",
    "model": "Gemini-X",
    "benchmark": "Bench A",
    "benchmark_description": "説明文は正式データに入れない",
    "source_category": "Reasoning",
    "score": 80.0,
    "unit": "%",
    "condition": None,
    "raw_value": "80.0%",
    "source_url": "https://example.test/card",
    "as_of": "2026-10-05",
    "retrieved_at": "2026-11-11",
    "retrieved_by": "tester",
    "retrieval_method": "script",
}


class ReadScraperJsonTest(TempDirTestCase):
    def json(self, *records):
        return self.write("Google.json", json.dumps({"records": list(records)}, ensure_ascii=False))

    def test_表にないキーを落とし_足りないキーは_null_にする(self):
        (r,) = read_scraper_json(self.json(SCRAPER_RECORD))
        self.assertEqual(list(r), OFFICIAL_KEYS)
        self.assertNotIn("benchmark_description", r)
        self.assertNotIn("source_category", r)
        for key in ["model_type", "mode", "benchmark_version", "sha"]:
            with self.subTest(key=key):
                self.assertIsNone(r[key])

    def test_値はそのまま引き継ぐ(self):
        (r,) = read_scraper_json(self.json(SCRAPER_RECORD))
        self.assertEqual(
            (r["provider"], r["score"], r["as_of"], r["retrieval_method"]), ("Google", 80.0, "2026-10-05", "script")
        )

    def test_必須のキーがなければ止まる(self):
        broken = {k: v for k, v in SCRAPER_RECORD.items() if k != "source_url"}
        with self.assertRaisesRegex(ConversionError, "1 件目.*source_url"):
            read_scraper_json(self.json(broken))

    def test_records_がなければ止まる(self):
        path = self.write("Google.json", "[]")
        with self.assertRaisesRegex(ConversionError, "records"):
            read_scraper_json(path)

    def test_records_の要素がオブジェクトでなければ_件目を示して止まる(self):
        path = self.write("Google.json", json.dumps({"records": ["x"]}))
        with self.assertRaisesRegex(ConversionError, "1 件目.*オブジェクト"):
            read_scraper_json(path)

    def test_取得日が_YYYY_MM_DD_でなければ止まる(self):
        for bad in ["2026/11/11", "2026-13-01", 20261111]:
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ConversionError, "1 件目.*取得日"):
                    read_scraper_json(self.json({**SCRAPER_RECORD, "retrieved_at": bad}))

    def test_shaは40桁の16進数だけ(self):
        (r,) = read_scraper_json(self.json({**SCRAPER_RECORD, "sha": SHA}))
        self.assertEqual(r["sha"], SHA)
        for bad in ["abc123", 123]:
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ConversionError, "1 件目.*sha"):
                    read_scraper_json(self.json({**SCRAPER_RECORD, "sha": bad}))

    def test_取得方法が_script_か_manual_でなければ止まる(self):
        with self.assertRaisesRegex(ConversionError, "1 件目.*retrieval_method"):
            read_scraper_json(self.json({**SCRAPER_RECORD, "retrieval_method": "manual?"}))

    def test_as_of_が日付の形でなければ_null_にして警告する(self):
        # Google のモデルカードは「Results as of May, 2026」で、年月しかない。YYYY-MM-DD にできないので、日にちを作らず null にする
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            (r,) = read_scraper_json(self.json({**SCRAPER_RECORD, "as_of": "May, 2026"}))
        self.assertIsNone(r["as_of"])
        self.assertEqual(len(caught), 1)
        self.assertIn("May, 2026", str(caught[0].message))

    def test_as_of_の警告は_ファイルごとに_1回(self):
        records = [{**SCRAPER_RECORD, "as_of": "May, 2026"}, {**SCRAPER_RECORD, "as_of": "May, 2026", "benchmark": "Bench B"}]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            read_scraper_json(self.json(*records))
        self.assertEqual(len(caught), 1)
        self.assertIn("2 件", str(caught[0].message))

    def test_as_of_が日付の形か_null_なら警告しない(self):
        for ok in ["2026-10-05", None]:
            with self.subTest(as_of=ok):
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    (r,) = read_scraper_json(self.json({**SCRAPER_RECORD, "as_of": ok}))
                self.assertEqual((r["as_of"], len(caught)), (ok, 0))


class WriteOfficialTest(TempDirTestCase):
    def test_records_の形で_日本語をそのまま_末尾に改行を付けて書く(self):
        records = [{"model": "モデル", "score": 1.5}]
        out = self.dir / "sub" / "Acme.json"
        write_official(records, out)
        text = out.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertIn("モデル", text)
        self.assertEqual(json.loads(text), {"records": records})


GOOGLE_CSV_ROW = "Gemini-X,,,Bench B,,70.0,%,,70.0%,https://example.test/img,2026-11-11,tester,,画像から"


class ConvertTest(TempDirTestCase):
    def convert(self, *sources):
        return convert(list(sources), self.dir / "official")

    def records(self, out):
        return json.loads(out.read_text(encoding="utf-8"))["records"]

    def test_CSV_は会社名のファイルに書き出す(self):
        src = self.csv(ROW.format(sha=""), name="Acme.csv")
        (out,) = self.convert(src)
        self.assertEqual(out, self.dir / "official" / "Acme.json")
        self.assertEqual(len(self.records(out)), 1)

    def test_JSON_は提供企業の名前のファイルに書き出す(self):
        src = self.write("candidate.json", json.dumps({"records": [SCRAPER_RECORD]}))
        (out,) = self.convert(src)
        self.assertEqual(out.name, "Google.json")

    def test_JSON_に複数の会社が混ざっていたら止まる(self):
        other = {**SCRAPER_RECORD, "provider": "Other"}
        src = self.write("candidate.json", json.dumps({"records": [SCRAPER_RECORD, other]}))
        with self.assertRaisesRegex(ConversionError, "提供企業"):
            self.convert(src)

    def test_拡張子が違えば止まる(self):
        src = self.write("Acme.txt", "x")
        with self.assertRaisesRegex(ConversionError, "拡張子"):
            self.convert(src)

    def test_同じ会社の入力は_1つのファイルにまとめ_先に書いた分を消さない(self):
        csv_src = self.csv(GOOGLE_CSV_ROW, name="Google.csv")
        json_src = self.write("candidate.json", json.dumps({"records": [SCRAPER_RECORD]}))
        (out,) = self.convert(csv_src, json_src)
        self.assertEqual(
            [(r["benchmark"], r["retrieval_method"]) for r in self.records(out)],
            [("Bench B", "manual"), ("Bench A", "script")],
        )

    def test_会社が違えば別のファイルに書く(self):
        a = self.csv(ROW.format(sha=""), name="Acme.csv")
        b = self.csv(ROW.format(sha=""), name="Beta.csv")
        self.assertEqual([p.name for p in self.convert(a, b)], ["Acme.json", "Beta.json"])

    def test_どれか1つでも変換に失敗したら_何も書かない(self):
        ok = self.csv(ROW.format(sha=""), name="Acme.csv")
        broken = self.csv("Model-X,,,Bench A", name="Beta.csv")
        with self.assertRaises(ConversionError):
            self.convert(ok, broken)
        self.assertFalse((self.dir / "official").exists())

    def test_同じ組の値が複数あれば警告するが_件数は減らさない(self):
        # どの値を残すかは企画書 §8 Q-4 で未決なので、この部品では選ばない
        src = self.csv(ROW.format(sha=""), ROW.format(sha=""))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            (out,) = self.convert(src)
        self.assertEqual(len(self.records(out)), 2)
        self.assertEqual(len(caught), 1)
        self.assertIn("複数", str(caught[0].message))

    def test_同じ組でも_測定条件が違えば重複とみなさない(self):
        other = ROW.format(sha="").replace("ツールなし", "ツールあり")
        src = self.csv(ROW.format(sha=""), other)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.convert(src)
        self.assertEqual(len(caught), 0)


if __name__ == "__main__":
    unittest.main()

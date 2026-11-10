import json
import tempfile
import unittest
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


class WriteOfficialTest(TempDirTestCase):
    def test_records_の形で_日本語をそのまま_末尾に改行を付けて書く(self):
        records = [{"model": "モデル", "score": 1.5}]
        out = self.dir / "sub" / "Acme.json"
        write_official(records, out)
        text = out.read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertIn("モデル", text)
        self.assertEqual(json.loads(text), {"records": records})


class ConvertTest(TempDirTestCase):
    def test_CSV_は会社名のファイルに書き出す(self):
        src = self.csv(ROW.format(sha=""), name="Acme.csv")
        out = convert(src, self.dir / "official")
        self.assertEqual(out, self.dir / "official" / "Acme.json")
        self.assertEqual(len(json.loads(out.read_text(encoding="utf-8"))["records"]), 1)

    def test_JSON_は提供企業の名前のファイルに書き出す(self):
        src = self.write("candidate.json", json.dumps({"records": [SCRAPER_RECORD]}))
        out = convert(src, self.dir / "official")
        self.assertEqual(out.name, "Google.json")

    def test_JSON_に複数の会社が混ざっていたら止まる(self):
        other = {**SCRAPER_RECORD, "provider": "Other"}
        src = self.write("candidate.json", json.dumps({"records": [SCRAPER_RECORD, other]}))
        with self.assertRaisesRegex(ConversionError, "提供企業"):
            convert(src, self.dir / "official")

    def test_拡張子が違えば止まる(self):
        src = self.write("Acme.txt", "x")
        with self.assertRaisesRegex(ConversionError, "拡張子"):
            convert(src, self.dir / "official")


if __name__ == "__main__":
    unittest.main()

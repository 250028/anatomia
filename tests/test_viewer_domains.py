"""ベンチマーク→領域の対応表(viewer/domains.py)の読み込み・検査と、領域の引き当て。"""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from viewer.domains import UNCLASSIFIED, DomainError, domain_map_from_dict, load_domains

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "domains.json"
REAL = REPO_ROOT / "data" / "domains.json"


def valid():
    """正しい形の対応表(2 領域・3 行。1 行は別名つき)。"""
    return {
        "status": "proposal",
        "source": "docs/research/r4-benchmark-domains.md",
        "note": "案",
        "domains": ["領域1", "領域2"],
        "benchmarks": [
            {"benchmark": "Bench-A", "domain": "領域1", "aliases": []},
            {"benchmark": "Bench B", "domain": "領域1", "aliases": ["Bench-B"]},
            {"benchmark": "Bench-C", "domain": "領域2", "aliases": []},
        ],
    }


class DomainMapFromDictTest(unittest.TestCase):
    def problems(self, data):
        with self.assertRaises(DomainError) as cm:
            domain_map_from_dict(data)
        return "\n".join(cm.exception.problems)

    def test_正しい形は読め_領域の順は_domains_の順で未分類が最後(self):
        m = domain_map_from_dict(valid())
        self.assertEqual(m.domains, ("領域1", "領域2"))
        self.assertEqual(m.choices, ("領域1", "領域2", UNCLASSIFIED))
        self.assertEqual(UNCLASSIFIED, "未分類")

    def test_名前の完全一致で領域を引く(self):
        m = domain_map_from_dict(valid())
        self.assertEqual(m.domain_of("Bench-A"), "領域1")
        self.assertEqual(m.domain_of("Bench-C"), "領域2")

    def test_別名でも同じ行の領域を引く(self):
        m = domain_map_from_dict(valid())
        self.assertEqual(m.domain_of("Bench-B"), "領域1")
        self.assertEqual(m.domain_of("Bench B"), "領域1")

    def test_完全一致でなければ未分類_大文字小文字_空白_部分一致も見ない(self):
        m = domain_map_from_dict(valid())
        for name in ("bench-a", "BENCH-A", "Bench-A ", "Bench-A 2.1", "Bench", "Bench-Z", ""):
            with self.subTest(name=name):
                self.assertEqual(m.domain_of(name), UNCLASSIFIED)

    def test_最初に選ぶのは対応表の最初の領域_1_つだけ(self):
        # 全部の領域を最初から選ぶと、ベンチマークが多く(実データで 87 列)、どちらの向きでも表が横にはみ出すため
        self.assertEqual(domain_map_from_dict(valid()).initial_selection, ("領域1",))

    def test_対応表が空なら最初に選ぶのは未分類(self):
        from viewer.domains import EMPTY
        self.assertEqual(EMPTY.initial_selection, (UNCLASSIFIED,))

    def test_表の上の並び(self):
        m = domain_map_from_dict(valid())
        self.assertEqual([m.order(d) for d in m.choices], [0, 1, 2])

    def test_オブジェクトでなければ失敗(self):
        for bad in ([], "x", None, 1):
            with self.subTest(bad=bad):
                self.assertIn("オブジェクトでない", self.problems(bad))

    def test_キーの不足と_知らないキー(self):
        data = valid()
        del data["benchmarks"]
        self.assertIn("`benchmarks`", self.problems(data))
        data = valid()
        data["extra"] = 1
        self.assertIn("`extra`", self.problems(data))

    def test_status_が_proposal_でなければ失敗(self):
        # 画面の文は「分類は案」と出す。対応表が案でなくなったら、画面の文も直す必要があるので止める
        for status in ("decided", "", None):
            with self.subTest(status=status):
                data = valid()
                data["status"] = status
                self.assertIn("`status`", self.problems(data))

    def test_source_と_note_は空でない文字列(self):
        for key in ("source", "note"):
            for bad in ("", "  ", None, 1):
                with self.subTest(key=key, bad=bad):
                    data = valid()
                    data[key] = bad
                    self.assertIn(f"`{key}`", self.problems(data))

    def test_領域の一覧が空_重複_未分類と同じ名前なら失敗(self):
        cases = [
            ([], "空"),
            (["領域1", "領域1", "領域2"], "領域1"),
            (["領域1", "領域2", UNCLASSIFIED], UNCLASSIFIED),
            (["領域1", " 領域2"], "領域2"),
            (["領域1", 2], "domains"),
        ]
        for domains, reason in cases:
            with self.subTest(domains=domains):
                data = valid()
                data["domains"] = domains
                self.assertIn(reason, self.problems(data))

    def test_知らない領域を指す行は失敗(self):
        data = valid()
        data["benchmarks"][2]["domain"] = "領域9"
        text = self.problems(data)
        self.assertIn("3 件目", text)
        self.assertIn("領域9", text)

    def test_行のキーの不足と知らないキー(self):
        data = valid()
        del data["benchmarks"][0]["aliases"]
        self.assertIn("`aliases`", self.problems(data))
        data = valid()
        data["benchmarks"][0]["reason"] = "x"
        self.assertIn("`reason`", self.problems(data))

    def test_別名は文字列の配列(self):
        for aliases in ("Bench-B", [""], [1], None):
            with self.subTest(aliases=aliases):
                data = valid()
                data["benchmarks"][1]["aliases"] = aliases
                self.assertIn("aliases", self.problems(data))

    def test_名前の前後に空白があると失敗(self):
        # 正式データの benchmark は前後の空白を落とすので(viewer/records.py)、空白つきの名前はどれにも一致しない
        data = valid()
        data["benchmarks"][0]["benchmark"] = "Bench-A "
        self.assertIn("Bench-A ", self.problems(data))

    def test_名前と別名の重複は失敗(self):
        cases = {
            "行の名前どうし": lambda d: d["benchmarks"][2].update(benchmark="Bench-A"),
            "別名と別の行の名前": lambda d: d["benchmarks"][1].update(aliases=["Bench-C"]),
            "別名と自分の名前": lambda d: d["benchmarks"][1].update(aliases=["Bench B"]),
            "別名どうし": lambda d: d["benchmarks"][2].update(aliases=["Bench-B"]),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                data = valid()
                change(data)
                self.assertIn("重複", self.problems(data))

    def test_問題は止める前に全件を集める(self):
        data = valid()
        data["status"] = "decided"
        data["benchmarks"][0]["domain"] = "領域9"
        data["benchmarks"][2]["aliases"] = ["Bench-A"]
        self.assertEqual(len(self.problems(data).splitlines()), 3)

    def test_元の辞書を書き換えない(self):
        data = valid()
        before = copy.deepcopy(data)
        domain_map_from_dict(data)
        self.assertEqual(data, before)


class LoadDomainsTest(unittest.TestCase):
    def test_ダミーの対応表を読める(self):
        m = load_domains(FIXTURE)
        self.assertEqual(m.choices, ("ダミー領域1", "ダミー領域2", "ダミー領域3", UNCLASSIFIED))
        self.assertEqual(m.domain_of("Bench-Y"), "ダミー領域2")  # 別名
        self.assertEqual(m.domain_of("Bench-Z"), UNCLASSIFIED)

    def test_無いファイルはデータなしでなくエラー(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                load_domains(Path(d) / "domains.json")
            with self.assertRaises(IsADirectoryError):
                load_domains(Path(d))

    def test_壊れた_JSON_と深すぎる入れ子は_DomainError(self):
        for text in ("{壊れた", "[" * 100_000):
            with self.subTest(text=text[:5]):
                with tempfile.TemporaryDirectory() as d:
                    path = Path(d) / "domains.json"
                    path.write_text(text, encoding="utf-8")
                    with self.assertRaises(DomainError) as cm:
                        load_domains(path)
                    self.assertIn("domains.json: 読み込めない", cm.exception.problems[0])

    def test_形の誤りはファイル名を付けて返す(self):
        data = valid()
        data["benchmarks"][0]["domain"] = "領域9"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "domains.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(DomainError) as cm:
                load_domains(path)
        self.assertTrue(cm.exception.problems[0].startswith("domains.json: "))


class RealDomainsTest(unittest.TestCase):
    """data/domains.json(R-4 の写し)。中身の正は R-4 §2 で、ここでは形と、別名の範囲だけを確かめる。"""

    def setUp(self):
        self.map = load_domains(REAL)
        self.raw = json.loads(REAL.read_text(encoding="utf-8"))

    def test_R4_の_5_領域を_R4_の順で持ち_全体が案(self):
        self.assertEqual(self.map.domains, ("コーディング", "数学", "科学的推論・知識", "エージェント", "マルチモーダル"))
        self.assertEqual(self.raw["status"], "proposal")
        self.assertEqual(self.raw["source"], "docs/research/r4-benchmark-domains.md")
        self.assertTrue((REPO_ROOT / self.raw["source"]).is_file())

    def test_R4_の_12_行(self):
        self.assertEqual(len(self.raw["benchmarks"]), 12)

    def test_別名は_Terminal_Bench_と_HLE_の_2_つだけ(self):
        aliases = {a: row["benchmark"] for row in self.raw["benchmarks"] for a in row["aliases"]}
        self.assertEqual(aliases, {"Terminal-Bench": "Terminal-bench", "HLE": "Humanity's Last Exam"})

    def test_関係を確かめていない名前は未分類(self):
        for name in ("OSWorld-Verified", "MMMU-Pro", "HLE-Verified", "τ³-bench", "SWE-bench Pro", "Terminal-Bench-Science"):
            with self.subTest(name=name):
                self.assertEqual(self.map.domain_of(name), UNCLASSIFIED)


if __name__ == "__main__":
    unittest.main()

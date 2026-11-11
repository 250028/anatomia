"""viewer/judge.py(領域単位の強・中・弱の判定)のテスト。

規則の番号は、企画書 §3-4 の暫定ルール【案】(PR #39 の head 7a934bb の規則 1〜6)。記号 A〜I は viewer/judge.py で
付けた記号で、#39 のコメント 6783472128(水戸の意見。チームの決定ではない)の見出しとの対応は、judge.py の docstring の表にある。
期待値は、規則の文面から手で計算した値で、テスト名かコメントに根拠の規則を書く。
入力はすべて架空の会社・モデル・ベンチマーク・値(出典は example.com)。
"""

import math
import unittest

from viewer.judge import (
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    MIDDLE,
    MIXED,
    NOT_JUDGEABLE,
    NOT_PUBLISHED,
    REASON_CONDITIONS_DISAGREE,
    REASON_DIRECTION_UNKNOWN,
    REASON_DUPLICATE_MODEL,
    REASON_FEW_MODELS,
    REASON_LOWER_IS_BETTER,
    REASON_NO_JUDGED_BENCHMARK,
    REASON_NO_VALUE_IN_VERSION,
    REASON_NULL_CONDITION,
    REASON_VERSIONS_UNDECIDED,
    STRONG,
    WEAK,
    cell_text,
    judge_domains,
    judge_values,
    majority_vote,
    model_key_name,
    model_key_name_type_mode,
    rank_descending,
    split_thirds,
)
from viewer.records import RecordError, ScoreRecord

KEY = model_key_name_type_mode
DOMAIN = "架空領域1"
OTHER = "架空領域2"
DOMAINS = {"Bench-P": DOMAIN, "Bench-Q": DOMAIN, "Bench-R": DOMAIN, "Bench-S": OTHER}
# テストでは、架空のベンチマークをすべて「大きいほど良い」と確かめたことにする(A)
DIRS = {name: HIGHER_IS_BETTER for name in ("Bench-P", "Bench-Q", "Bench-R", "Bench-S", "Bench-Z")}


def rec(model, benchmark, score, *, version=None, unit="%", condition=None, model_type=None, mode=None):
    return ScoreRecord(
        provider="架空社",
        model=model,
        benchmark=benchmark,
        score=score,
        unit=unit,
        source_url="https://example.com/dummy",
        retrieved_at="2026-11-01",
        retrieved_by="ダミー",
        retrieval_method="script",
        mode=mode,
        model_type=model_type,
        benchmark_version=version,
        condition=condition,
    )


def raw(model, benchmark, score, **overrides):
    """正式データの 1 件の dict(企画書 §3-3 のキー)。"""
    d = {
        "model": model, "provider": "架空社", "model_type": None, "mode": None, "benchmark": benchmark,
        "benchmark_version": None, "score": score, "unit": "%", "condition": None, "raw_value": f"{score}%",
        "source_url": "https://example.com/dummy", "retrieved_at": "2026-11-01", "retrieved_by": "ダミー",
        "retrieval_method": "script", "sha": None, "as_of": None,
    }
    d.update(overrides)
    return d


def scores_for(benchmark, scores, **kw):
    """`scores` の i 番目を Model-i の値にする(Model-1, Model-2, ...)。"""
    return [rec(f"Model-{i}", benchmark, s, **kw) for i, s in enumerate(scores, start=1)]


def jv(records, **kw):
    kw.setdefault("directions", DIRS)
    return judge_values(records, model_key=KEY, **kw)


def jd(records, domains=DOMAINS, **kw):
    kw.setdefault("directions", DIRS)
    return judge_domains(records, domains, model_key=KEY, **kw)


def judgments(results):
    return [r.judgment for r in results]


def key(model, model_type=None, mode=None):
    return ("架空社", model, model_type, mode)


class Rule3SplitTest(unittest.TestCase):
    """規則 3(B):k = モデル数 // 3、上位 k が強・下位 k が弱・残りが中。"""

    def test_規則3_4モデルは_1_2_1(self):
        self.assertEqual(judgments(jv(scores_for("Bench-P", [40, 30, 20, 10]))), [STRONG, MIDDLE, MIDDLE, WEAK])

    def test_規則3_5モデルは_1_3_1(self):
        r = jv(scores_for("Bench-P", [50, 40, 30, 20, 10]))
        self.assertEqual(judgments(r), [STRONG, MIDDLE, MIDDLE, MIDDLE, WEAK])

    def test_規則3_7モデルは_2_3_2(self):
        r = jv(scores_for("Bench-P", [70, 60, 50, 40, 30, 20, 10]))
        self.assertEqual(judgments(r), [STRONG, STRONG, MIDDLE, MIDDLE, MIDDLE, WEAK, WEAK])

    def test_規則3_入力の順に関係なく_値の大きい順に付く(self):
        r = jv(scores_for("Bench-P", [20, 40, 10, 30]))
        self.assertEqual(judgments(r), [MIDDLE, STRONG, WEAK, MIDDLE])

    def test_規則6_値ごとにグループのモデル数と順位を持つ(self):
        r = jv(scores_for("Bench-P", [20, 40, 10, 30]))
        self.assertEqual([x.group_size for x in r], [4, 4, 4, 4])
        self.assertEqual([x.rank for x in r], [3, 1, 4, 2])


class Rule2MinSizeTest(unittest.TestCase):
    """規則 2(C):グループのモデル数が 3 未満なら判定不可。"""

    def test_規則2_3モデルは判定する_k1で_1_1_1(self):
        self.assertEqual(judgments(jv(scores_for("Bench-P", [30, 20, 10]))), [STRONG, MIDDLE, WEAK])

    def test_規則2_2モデルは判定不可(self):
        r = jv(scores_for("Bench-P", [30, 20]))
        self.assertEqual(judgments(r), [None, None])
        self.assertEqual({x.reason for x in r}, {REASON_FEW_MODELS.format(min=3)})
        self.assertEqual({x.rank for x in r}, {None})
        self.assertEqual({x.group_size for x in r}, {2})

    def test_C_境界は引数で変えられる(self):
        # k = 2 // 3 = 0 なので、強・弱は無く、全員が中(規則 3 の式どおり)
        self.assertEqual(judgments(jv(scores_for("Bench-P", [30, 20]), min_group_size=2)), [MIDDLE, MIDDLE])


class Rule3TieTest(unittest.TestCase):
    """規則 3(D):値が同じモデルは同じ順位とし、上の順位の判定にそろえる。"""

    def test_同点の順位は上にそろう(self):
        self.assertEqual(rank_descending([10, 10, 8, 6]), [1, 1, 3, 4])

    def test_上の境界をまたぐ同点は両方とも強(self):
        # 4 モデル・k=1。40 が 2 つとも 1 位 → 強。20 は 3 位で中、10 は 4 位で弱
        self.assertEqual(judgments(jv(scores_for("Bench-P", [40, 40, 20, 10]))), [STRONG, STRONG, MIDDLE, WEAK])

    def test_下の境界をまたぐ同点は両方とも中(self):
        # 4 モデル・k=1。10 が 2 つとも 3 位 → 3 ≤ 4-1 なので中。弱は 0 件になる
        self.assertEqual(judgments(jv(scores_for("Bench-P", [40, 30, 10, 10]))), [STRONG, MIDDLE, MIDDLE, MIDDLE])

    def test_7モデルで2位と3位の同点は両方とも強(self):
        # k=2。60 が 2 つとも 2 位 → 強が 3 件になる
        r = jv(scores_for("Bench-P", [70, 60, 60, 50, 40, 30, 20]))
        self.assertEqual(judgments(r), [STRONG, STRONG, STRONG, MIDDLE, MIDDLE, WEAK, WEAK])

    def test_全員同点は全員が強(self):
        self.assertEqual(judgments(jv(scores_for("Bench-P", [50, 50, 50, 50]))), [STRONG] * 4)


class Rule1GroupTest(unittest.TestCase):
    """規則 1(F):ベンチマーク・版・単位・測定条件が同じ値だけを比べる。"""

    def test_測定条件が違う値は別のグループになる(self):
        records = scores_for("Bench-P", [30, 20, 10], condition="Pass@1") + scores_for(
            "Bench-P", [99, 1], condition="ツールあり"
        )
        r = jv(records)
        self.assertEqual(judgments(r), [STRONG, MIDDLE, WEAK, None, None])
        self.assertEqual([x.group_size for x in r], [3, 3, 3, 2, 2])

    def test_null_どうしは同じ条件として比べる(self):
        self.assertEqual(judgments(jv(scores_for("Bench-P", [30, 20, 10], condition=None))), [STRONG, MIDDLE, WEAK])

    def test_null_と条件付きは別のグループ(self):
        records = scores_for("Bench-P", [30, 20], condition=None) + [rec("Model-3", "Bench-P", 10, condition="Pass@1")]
        r = jv(records)
        self.assertEqual([x.group_size for x in r], [2, 2, 1])
        self.assertEqual(judgments(r), [None, None, None])

    def test_F_null_を比べない設定(self):
        r = jv(scores_for("Bench-P", [30, 20, 10], condition=None), null_condition_comparable=False)
        self.assertEqual(judgments(r), [None, None, None])
        self.assertEqual({x.reason for x in r}, {REASON_NULL_CONDITION})
        # グループに入れなかった値は、モデル数を持たない(None。規則 6 の内訳で「0 モデル中」と出さない)
        self.assertEqual({x.group_size for x in r}, {None})

    def test_F_条件の比べ方は引数で変えられる(self):
        records = [
            rec("Model-1", "Bench-P", 30, condition="Pass@1"),
            rec("Model-2", "Bench-P", 20, condition="pass@1"),
            rec("Model-3", "Bench-P", 10, condition="PASS@1"),
        ]
        self.assertEqual(judgments(jv(records)), [None, None, None])
        folded = jv(records, condition_key=lambda c: c.lower() if c else c)
        self.assertEqual(judgments(folded), [STRONG, MIDDLE, WEAK])

    def test_単位が違う値は別のグループ(self):
        records = scores_for("Bench-P", [30, 20], unit="%") + [rec("Model-3", "Bench-P", 0.1, unit=None)]
        self.assertEqual([x.group_size for x in jv(records)], [2, 2, 1])

    def test_版が違う値は別のグループ(self):
        records = scores_for("Bench-P", [30, 20], version="1") + [rec("Model-3", "Bench-P", 10, version="2")]
        self.assertEqual([x.group_size for x in jv(records)], [2, 2, 1])


class DirectionTest(unittest.TestCase):
    """A:値が大きいほど上位。小さいほど良い・向きが決まらないベンチマークは判定不可(コメント 6783472128 の「順位の向き」)。"""

    def test_directions_を渡さないと_TypeError(self):
        with self.assertRaises(TypeError):
            judge_values([], model_key=KEY)
        with self.assertRaises(TypeError):
            judge_domains([], DOMAINS, model_key=KEY)

    def test_小さいほど良い値は_既定では判定不可(self):
        # 小さいほど良い値を、大きいほど上位として判定しない(コメント 6783472128 の「順位の向き」)
        r = judge_values(scores_for("Bench-P", [30, 20, 1]), model_key=KEY, directions={"Bench-P": LOWER_IS_BETTER})
        self.assertEqual(judgments(r), [None, None, None])
        self.assertEqual({x.reason for x in r}, {REASON_LOWER_IS_BETTER})
        self.assertEqual({x.group_size for x in r}, {None})

    def test_向きを渡していないベンチマークは判定不可(self):
        r = judge_values(scores_for("Bench-P", [30, 20, 1]), model_key=KEY, directions={})
        self.assertEqual(judgments(r), [None, None, None])
        self.assertEqual({x.reason for x in r}, {REASON_DIRECTION_UNKNOWN})

    def test_大きいほど良いと渡したものだけ判定する(self):
        records = scores_for("Bench-P", [30, 20, 10]) + scores_for("Bench-Q", [30, 20, 10])
        r = judge_values(records, model_key=KEY, directions={"Bench-P": HIGHER_IS_BETTER})
        self.assertEqual(judgments(r), [STRONG, MIDDLE, WEAK, None, None, None])
        self.assertEqual({x.reason for x in r[3:]}, {REASON_DIRECTION_UNKNOWN})

    def test_逆の順位で判定する切り替えの余地(self):
        # 逆の順位で判定するかは未決。rank_lower を渡したときだけ、その関数で順位を付ける
        def rank_ascending(scores):
            return [1 + sum(1 for o in scores if o < s) for s in scores]

        r = judge_values(
            scores_for("Bench-P", [30, 20, 1]), model_key=KEY,
            directions={"Bench-P": LOWER_IS_BETTER}, rank_lower=rank_ascending,
        )
        self.assertEqual(judgments(r), [WEAK, MIDDLE, STRONG])

    def test_向きの値の誤りは_ValueError(self):
        with self.assertRaises(ValueError):
            judge_values([], model_key=KEY, directions={"Bench-P": "高いほど良い"})

    def test_向きを確かめていないものだけのセルは_未公表ではなく判定不可(self):
        # 規則 5:値を公表しているが判定が付くベンチマークがない → 判定不可
        table = jd(scores_for("Bench-P", [30, 20, 10]), directions={})
        cell = table.cell_at(key("Model-1"), DOMAIN)
        self.assertEqual(cell.label, NOT_JUDGEABLE)
        self.assertEqual(cell.reason, REASON_NO_JUDGED_BENCHMARK)
        self.assertEqual(cell.votes[0].reason, REASON_DIRECTION_UNKNOWN)


class ScoreCheckTest(unittest.TestCase):
    """入力の検査:dict も ScoreRecord も viewer.records の検査に通し、score の誤りを止める(規則 3 の順位は数値の大小で付けるため)。"""

    def assert_problem_at(self, records, index):
        with self.assertRaises(RecordError) as ctx:
            jv(records)
        self.assertTrue(any(p.startswith(f"records の {index} 件目") and "score" in p for p in ctx.exception.problems))

    def test_nan_は止まる(self):
        # nan は大小を比べられず、順位が誤る
        self.assert_problem_at([raw("Model-1", "Bench-P", math.nan), raw("Model-2", "Bench-P", 2),
                                raw("Model-3", "Bench-P", 1)], 1)

    def test_文字列の_score_は止まる(self):
        # 文字列は辞書順で比べられ、順位が誤る
        self.assert_problem_at([raw("Model-1", "Bench-P", "9"), raw("Model-2", "Bench-P", "30"),
                                raw("Model-3", "Bench-P", "100")], 1)

    def test_None_の_score_は理由つきで止まる(self):
        self.assert_problem_at([raw("Model-1", "Bench-P", 3), raw("Model-2", "Bench-P", None)], 2)

    def test_bool_の_score_は止まる(self):
        self.assert_problem_at([raw("Model-1", "Bench-P", True)], 1)

    def test_ScoreRecord_も検査に通す(self):
        self.assert_problem_at([rec("Model-1", "Bench-P", 3), rec("Model-2", "Bench-P", math.inf)], 2)

    def test_どちらでもない値は止まる(self):
        with self.assertRaises(RecordError):
            jv([("Model-1", "Bench-P", 3)])

    def test_ScoreRecord_も正規化してから使う_空文字の条件は_null_と同じグループ(self):
        # dict と同じく record_from_dict を通すので、condition="" は None になる(規則 1・コメント 6783472128 の【質問】4)
        records = [rec("Model-1", "Bench-P", 30, condition=""), rec("Model-2", "Bench-P", 20, condition=None),
                   raw("Model-3", "Bench-P", 10, condition="")]
        r = jv(records)
        self.assertEqual([x.group_size for x in r], [3, 3, 3])
        self.assertEqual(judgments(r), [STRONG, MIDDLE, WEAK])
        self.assertEqual({x.record.condition for x in r}, {None})

    def test_正式データの_dict_のままでも判定できる(self):
        records = [raw(f"Model-{i}", "Bench-P", s) for i, s in enumerate([30, 20, 10], start=1)]
        table = jd(records)
        self.assertEqual(table.cell_at(key("Model-1"), DOMAIN).label, STRONG)
        self.assertIsInstance(table.cell_at(key("Model-1"), DOMAIN).votes[0].values[0].record, ScoreRecord)


class ModelKeyTest(unittest.TestCase):
    """G:モデルの単位は未決なので、`model_key` は必ず渡す。"""

    def test_model_key_を渡さないと_TypeError(self):
        with self.assertRaises(TypeError):
            judge_domains([], DOMAINS, directions=DIRS)

    def test_名前_種類_推論モードの単位なら_推論モード違いは別のモデル(self):
        records = [
            rec("Model-1", "Bench-P", 30, mode="High"),
            rec("Model-1", "Bench-P", 20, mode="Low"),
            rec("Model-2", "Bench-P", 10),
        ]
        self.assertEqual(judgments(jv(records)), [STRONG, MIDDLE, WEAK])

    def test_モデル名だけの単位なら_同じモデルが重なり_グループごと判定不可(self):
        # 暫定の挙動:同じモデルの値が 2 つあるときどれを使うか決まらない → 判定不可と理由
        records = [
            rec("Model-1", "Bench-P", 30, mode="High"),
            rec("Model-1", "Bench-P", 20, mode="Low"),
            rec("Model-2", "Bench-P", 10),
            rec("Model-3", "Bench-P", 5),
        ]
        r = judge_values(records, model_key=model_key_name, directions=DIRS)
        self.assertEqual(judgments(r), [None] * 4)
        self.assertEqual({x.reason for x in r}, {REASON_DUPLICATE_MODEL})


class Rule5PublishedTest(unittest.TestCase):
    """規則 5:未公表(値が 1 つもない)と、判定不可(値はあるが判定が付かない)を区別する。"""

    def setUp(self):
        # Bench-P は 3 モデル(判定が付く)。Bench-S(別の領域)は Model-4 だけ
        self.table = jd(scores_for("Bench-P", [30, 20, 10]) + [rec("Model-4", "Bench-S", 50)])

    def test_領域内の値が1つもないモデルは未公表(self):
        cell = self.table.cell_at(key("Model-4"), DOMAIN)
        self.assertEqual(cell.label, NOT_PUBLISHED)
        self.assertFalse(cell.is_published)
        self.assertEqual(cell.votes, ())
        self.assertEqual(cell_text(cell), NOT_PUBLISHED)

    def test_値はあるが判定が付かないモデルは判定不可(self):
        # Bench-S のグループは 1 モデル → 規則 2 で判定不可 → 領域も判定不可(規則 5)
        cell = self.table.cell_at(key("Model-4"), OTHER)
        self.assertEqual(cell.label, NOT_JUDGEABLE)
        self.assertTrue(cell.is_published)
        self.assertEqual(cell.votes[0].reason, REASON_FEW_MODELS.format(min=3))
        self.assertEqual(cell_text(cell), NOT_JUDGEABLE)

    def test_未公表は弱にしない(self):
        self.assertEqual(self.table.cell_at(key("Model-1"), OTHER).label, NOT_PUBLISHED)


class UnclassifiedTest(unittest.TestCase):
    """対応表に無いベンチマーク(R-4 §3 の「未分類」)の値を、DomainTable から取り出せる。"""

    def test_未分類の値と名前の一覧(self):
        records = scores_for("Bench-Z", [30, 20, 10]) + scores_for("Bench-P", [30, 20, 10]) + [rec("Model-1", "Bench-Y", 1)]
        table = jd(records)
        self.assertEqual(table.unclassified_benchmarks, ("Bench-Z", "Bench-Y"))
        self.assertEqual([(r.model, r.benchmark) for r in table.unclassified],
                         [("Model-1", "Bench-Z"), ("Model-2", "Bench-Z"), ("Model-3", "Bench-Z"), ("Model-1", "Bench-Y")])

    def test_未分類だけのモデルは全領域が未公表(self):
        table = jd(scores_for("Bench-Z", [30, 20, 10]))
        self.assertEqual({table.cell_at(m, d).label for m in table.models for d in table.domains}, {NOT_PUBLISHED})

    def test_未分類が無ければ空(self):
        self.assertEqual(jd(scores_for("Bench-P", [30, 20, 10])).unclassified, ())


class Rule4MajorityTest(unittest.TestCase):
    """規則 4(E・I):判定が付いたベンチマークの多数決。過半数なら、その判定。割れたら混在。"""

    def cell(self, by_benchmark):
        """{ベンチマーク: [Model-1, Model-2, Model-3 の値]} から、Model-1 の DOMAIN のセルを返す(3 モデル・k=1)。"""
        records = [r for b, s in by_benchmark.items() for r in scores_for(b, s)]
        return jd(records).cell_at(key("Model-1"), DOMAIN)

    def test_強2_中1は強(self):
        cell = self.cell({"Bench-P": [30, 20, 10], "Bench-Q": [30, 20, 10], "Bench-R": [20, 30, 10]})
        self.assertEqual((cell.label, cell.count, cell.judged), (STRONG, 2, 3))
        self.assertEqual(cell_text(cell), "強（2/3 件）")

    def test_強1_中1_弱1は混在(self):
        cell = self.cell({"Bench-P": [30, 20, 10], "Bench-Q": [20, 30, 10], "Bench-R": [10, 30, 20]})
        self.assertEqual((cell.label, cell.count, cell.judged), (MIXED, None, 3))
        self.assertEqual(cell_text(cell), "混在（強 1・中 1・弱 1）")

    def test_2件で強1_中1の同数は混在(self):
        # 過半数(2 件の半分より多い = 2 件)に届かない → 規則 4 の「割れたら混在」
        self.assertEqual(self.cell({"Bench-P": [30, 20, 10], "Bench-Q": [20, 30, 10]}).label, MIXED)

    def test_4件で強2_弱2の同数は混在(self):
        self.assertEqual(majority_vote((STRONG, STRONG, WEAK, WEAK)), (MIXED, None))

    def test_1件だけなら_その判定に件数を添える(self):
        cell = self.cell({"Bench-P": [10, 30, 20]})
        self.assertEqual((cell.label, cell.count, cell.judged), (WEAK, 1, 1))
        self.assertEqual(cell_text(cell), "弱（1/1 件）")

    def test_判定不可のベンチマークは件数に入らない(self):
        # Bench-Q は 2 モデルだけ(判定不可)。判定が付くのは Bench-P の 1 件
        records = scores_for("Bench-P", [30, 20, 10]) + scores_for("Bench-Q", [10, 20])
        cell = jd(records).cell_at(key("Model-1"), DOMAIN)
        self.assertEqual((cell.label, cell.count, cell.judged), (STRONG, 1, 1))
        # 規則 6:判定が付かなかった値も内訳に並ぶ
        self.assertEqual([v.benchmark for v in cell.votes], ["Bench-P", "Bench-Q"])
        self.assertEqual(cell.votes[1].values[0].group_size, 2)

    def test_E_決め方は引数で変えられる(self):
        def always_middle(judgments):
            return MIDDLE, len(judgments)

        cell = jd(scores_for("Bench-P", [30, 20, 10]), decide=always_middle).cell_at(key("Model-1"), DOMAIN)
        self.assertEqual(cell.label, MIDDLE)


# 「最新」の決め方は未決。テストでは、版の新旧の順を明示した並びで決める(max は文字列の比較になり、
# "9" と "10" では "9" を選び、None と文字列が混ざると TypeError になるので、例に使わない)
VERSION_ORDER = ["1", "2"]


def latest_of_model(model_versions, benchmark_versions):
    """そのモデルが値を持つ版のうち最新(読み 1)。"""
    return max(model_versions, key=VERSION_ORDER.index)


def latest_of_benchmark(model_versions, benchmark_versions):
    """ベンチマーク全体に出てくる版のうち最新(読み 2)。"""
    return max(benchmark_versions, key=VERSION_ORDER.index)


class VoteUnitTest(unittest.TestCase):
    """H:1 票はベンチマーク名ごと。版が複数なら最新だけ(「最新」の決め方と範囲は未決)。"""

    def records(self):
        # Bench-P の版 1 と版 2。どちらも 3 モデル。Model-1 は版 1 で強、版 2 で弱
        return scores_for("Bench-P", [30, 20, 10], version="1") + scores_for("Bench-P", [10, 20, 30], version="2")

    def test_版が複数あり_決め方の指定がなければ判定不可(self):
        cell = jd(self.records()).cell_at(key("Model-1"), DOMAIN)
        self.assertEqual(cell.label, NOT_JUDGEABLE)
        self.assertEqual(len(cell.votes), 1)  # ベンチマーク名ごとに 1 票
        self.assertEqual(cell.votes[0].reason, REASON_VERSIONS_UNDECIDED)
        self.assertEqual(len(cell.votes[0].values), 2)  # 規則 6:両方の版の値が内訳に残る

    def test_決め方を渡せば_その版だけで1票(self):
        cell = jd(self.records(), pick_version=latest_of_model).cell_at(key("Model-1"), DOMAIN)
        self.assertEqual((cell.label, cell.count, cell.judged), (WEAK, 1, 1))
        self.assertEqual(cell.votes[0].version, "2")

    def test_どのモデルにも無い版を返したら_ValueError(self):
        with self.assertRaises(ValueError):
            jd(self.records(), pick_version=lambda mine, all_: "9")

    def scattered(self):
        # 版 1 は Model-1〜3、版 2 は Model-1 だけ。「最新」をどの範囲の版から選ぶかで結果が変わる(コメント 6783472128 の【質問】6)
        return scores_for("Bench-P", [30, 20, 10], version="1") + [rec("Model-1", "Bench-P", 5, version="2")]

    def test_H_指定がなければ_版を1つしか持たないモデルも判定不可(self):
        table = jd(self.scattered())
        self.assertEqual({table.cell_at(m, DOMAIN).votes[0].reason for m in table.models}, {REASON_VERSIONS_UNDECIDED})

    def test_H_読み1_モデルの版から選ぶ(self):
        table = jd(self.scattered(), pick_version=latest_of_model)
        # Model-1 は版 2(1 モデルだけで規則 2 の判定不可)、Model-2・3 は版 1 で判定
        self.assertEqual([table.cell_at(m, DOMAIN).label for m in table.models], [NOT_JUDGEABLE, MIDDLE, WEAK])

    def test_H_読み2_ベンチマーク全体の版から選ぶ(self):
        table = jd(self.scattered(), pick_version=latest_of_benchmark)
        # 全員が版 2 を使う。Model-1 は規則 2 で判定不可、Model-2・3 は版 2 に値が無く判定不可
        cells = [table.cell_at(m, DOMAIN) for m in table.models]
        self.assertEqual({c.label for c in cells}, {NOT_JUDGEABLE})
        self.assertEqual([c.votes[0].reason for c in cells[1:]], [REASON_NO_VALUE_IN_VERSION] * 2)
        self.assertEqual({c.votes[0].version for c in cells}, {"2"})

    def test_pick_version_には両方の範囲の版が渡る(self):
        seen = []

        def spy(model_versions, benchmark_versions):
            seen.append((model_versions, benchmark_versions))
            return benchmark_versions[0]

        jd(self.scattered(), pick_version=spy)
        self.assertEqual(seen[0], (("1", "2"), ("1", "2")))
        self.assertEqual(seen[1], (("1",), ("1", "2")))

    def test_同じ版で測定条件違いの判定が同じなら_その判定で1票(self):
        records = scores_for("Bench-P", [30, 20, 10], condition="条件1") + scores_for(
            "Bench-P", [30, 20, 10], condition="条件2"
        )
        cell = jd(records).cell_at(key("Model-1"), DOMAIN)
        self.assertEqual((cell.label, cell.count, cell.judged), (STRONG, 1, 1))

    def test_同じ版で測定条件違いの判定が食い違えば_判定不可(self):
        records = scores_for("Bench-P", [30, 20, 10], condition="条件1") + scores_for(
            "Bench-P", [10, 20, 30], condition="条件2"
        )
        cell = jd(records).cell_at(key("Model-1"), DOMAIN)
        self.assertEqual(cell.label, NOT_JUDGEABLE)
        self.assertEqual(cell.votes[0].reason, REASON_CONDITIONS_DISAGREE)


class InputTest(unittest.TestCase):
    def test_空の入力(self):
        table = jd([])
        self.assertEqual(table.models, ())
        self.assertEqual(table.domains, (DOMAIN, OTHER))
        self.assertEqual(table.unclassified, ())
        self.assertEqual(jv([]), [])

    def test_空の対応表(self):
        table = jd(scores_for("Bench-P", [30, 20, 10]), {})
        self.assertEqual(table.domains, ())
        self.assertEqual(len(table.models), 3)

    def test_対応表が_dict_でなければ_TypeError(self):
        with self.assertRaises(TypeError):
            jd([], ["Bench-P"])
        with self.assertRaises(TypeError):
            jv([], directions=["Bench-P"])

    def test_行と領域の順は入力の順(self):
        table = jd([rec("Model-2", "Bench-S", 1)] + scores_for("Bench-P", [30, 20, 10]))
        self.assertEqual(table.models, (key("Model-2"), key("Model-1"), key("Model-3")))

    def test_無い組は_KeyError(self):
        with self.assertRaises(KeyError):
            jd([]).cell_at(key("Model-1"), DOMAIN)

    def test_split_thirds_の単体(self):
        self.assertEqual([split_thirds(r, 7) for r in range(1, 8)], [STRONG] * 2 + [MIDDLE] * 3 + [WEAK] * 2)


if __name__ == "__main__":
    unittest.main()

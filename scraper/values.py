"""各社のパーサに共通の、値の下ごしらえ。"""

import re

# 値なしを表す表記。判定は clean_value の後に行う(`—*` のような記号付きも値なしにするため)
NO_VALUE = {"", "—", "–", "-"}


def clean_value(text):
    """桁区切りのカンマと、前後の太字(**)・末尾の脚注の記号を除く。"""
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text).strip()
    text = text.strip("*")
    return re.sub(r"[*†‡§]+$", "", text).strip()

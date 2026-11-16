"""Hugging Face の Qwen の公式組織の README.md（HTML の表）から、自社モデルのスコアを取り出す（骨組み。解析はまだない）。

Qwen の自社サイト（qwen.ai）からは取らない（企画書 §6-3。自社規約が自動での取得を禁止している。R-2 §3-1）。
README の取り方は hf_readme.py（DeepSeek）と同じで、resolve の URL から生ファイルとして 1 回だけ取り、
版（sha）は同じ応答の X-Repo-Commit ヘッダーから取る（企画書 §6-3 の Hugging Face の行）。
Qwen の README の表は、Markdown ではなく README に直書きされた HTML の <table>（R-1 §2・§4-1）なので、
hf_readme.py の Markdown の表の解析は使えない。表の形（見出しの行・領域の行・推論モード・脚注の書き方）は
実物でまだ確かめていないため、解析（parse_readme）は書いていない。確かめるまで REPO_IDS を空にしておき、取得もしない。
メンバーが手動で実行する（企画書 §6-1）。取得結果は候補データで、正式データへは
実行者以外のメンバーが出典ページと照合してから反映する（企画書 §3-2 ③）。

    python3 -m scraper.hf_qwen --by <取得者> --out <出力先.json>
"""

import argparse
import json
import sys
import time
from datetime import date

from scraper.google_modelcard import MIN_INTERVAL_SEC, FetchStopped
from scraper.hf_readme import README_URL, _SHA, _get

# 取得してよいリポジトリを固定する。任意指定の引数は設けない（R-2 の判定外のリポジトリに触れないため）。
# 取得元は Qwen/Qwen3.8-27B の 1 つを予定している（R-1 §2 の Qwen の行・R-3 §2-1 の Qwen の行。License は R-2 §3-3 で Apache 2.0）。
# 解析を書くまでは、取得しても読めないので空にしておく（main は、空なら取得せずに止まる）
REPO_IDS = []
OFFICIAL_ORG = "Qwen"

PROVIDER = "Qwen"
# 取る列は「取る一覧」で決める(R-3 §2-1 の対象だけ)。Qwen3.8 系はサイズ違いを 1 モデルと数える(R-3 §3 の 2)が、
# 取るのは R-1 で形式を確かめた Qwen3.8-27B のカードの列とし、Qwen3.6-27B もそのカードの列から取る(R-3 §2-1)。
# 同じカードの Qwen3.7-Plus の列は R-1 §2 の列にないので取らない(R-3 §3 の 1)。列見出しの綴りは実物で確かめていない。
# 一覧にない列は、取り込まずに数える。足すときは企画書 §4-3 の「見直し」で行う(hf_readme.py と同じ形)
TAKEN_MODELS = frozenset({"Qwen3.8-27B", "Qwen3.6-27B"})


def parse_readme(text, source_url, retrieved_by, retrieved_at, sha):
    """README の HTML の表から、取る一覧の列の値を、hf_readme.parse_readme と同じ形（records, skipped, unreadable）で返す。

    表の形を実物で確かめていないので、まだ書いていない。推測で書くと、形が違ったときに誤った値を黙って取りうるため。
    """
    raise NotImplementedError("Qwen の README の表の形を実物で確かめてから書く")


def fetch_readme(repo_id):
    """README.md の本文と、その応答が示す版（sha）を返す。README を 1 回だけ取り、200 以外なら止める。

    hf_readme.fetch_readme と同じ取り方で、公式組織の確認だけを Qwen にしている。
    """
    if repo_id.split("/")[0] != OFFICIAL_ORG:
        raise FetchStopped(f"{repo_id} は {OFFICIAL_ORG} のリポジトリではない。取得を止める")
    res = _get(README_URL.format(repo_id=repo_id))
    sha = res.headers.get("X-Repo-Commit")
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        raise FetchStopped(f"{repo_id} の応答に版(X-Repo-Commit)が無いか、読めない({sha!r})。取得を止める")
    # 本文はメモリ上だけで持ち、ファイルに残さない（企画書 §3-2 ①・§6-3）
    return res.content.decode("utf-8"), sha


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--by", required=True, help="取得者(実行したメンバーの名前)")
    ap.add_argument("--out", required=True, help="候補データの出力先(JSON)")
    args = ap.parse_args()

    if not REPO_IDS:
        sys.exit("取得するリポジトリがない(REPO_IDS が空。README の表の解析を書いてから入れる)")
    today = date.today().isoformat()
    all_records = []
    try:
        for repo_id in REPO_IDS:
            time.sleep(MIN_INTERVAL_SEC)
            text, sha = fetch_readme(repo_id)
            # 照合する人が、取得した版(sha)の README をブラウザでそのまま開けるようにする(企画書 §3-3 の出典URL)
            url = f"https://huggingface.co/{repo_id}/blob/{sha}/README.md"
            records, skipped, unreadable = parse_readme(text, url, args.by, today, sha)
            print(f"{url}: {len(records)} 件。取り込まなかった: {dict(skipped)}", file=sys.stderr)
            for u in unreadable:
                print(f"  解釈できない値(要確認): {u['model']} / {u['mode']} / {u['benchmark']} / {u['raw_value']!r}", file=sys.stderr)
            all_records.extend(records)
    except FetchStopped as e:
        sys.exit(str(e))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"records": all_records}, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    main()

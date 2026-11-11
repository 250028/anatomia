"""Anatomia の画面(MVP)。「モデル×ベンチマーク」の表を、出典つきで 1 画面に出す。

動かし方(リポジトリのルートで。起動したら、ブラウザで http://127.0.0.1:8501 を開く):
    streamlit run viewer/app.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
        → 正式データ(data/official/)を読む
    streamlit run viewer/app.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false -- --dummy
        → ダミーデータ(tests/fixtures/official/)を読む(`--` の後ろが、このファイルへの引数)

    3 つのオプションを付ける理由(既定値は Streamlit 1.67.0 の `streamlit config show` と、手元での起動で確かめた):
    - `--server.address 127.0.0.1`：自分の PC だけで待ち受ける。付けないと、すべての口で待ち受けてほかの PC からも開け、
      起動時に外向きの IP を調べて External URL として表示する。公開範囲は企画書 §6-4 で【未決】(§8 Q-2)なので、公開しない側に倒す
    - `--server.headless true`：起動したときに、ブラウザを自動で開かない。既定は「Linux で DISPLAY が無いときだけ開かない」で、
      PC(WSL かどうかなど)によって動きが変わるので、どの PC でも同じ動きにそろえるため
    - `--browser.gatherUsageStats false`：利用状況を外(Streamlit 社)へ送らない(既定は送る)。画面からネットワークへ出ないようにするため

方針:
- このファイルは「ロジック層(viewer/records.py・viewer/grid.py)の関数を呼んで、表示するだけ」にする。
  表の作り方・未公表の判定・詳細の項目は、ロジック層が決める(企画書 §6-2 の「収集と表示を分ける理由」)
- 画面からは取得(スクレイピング)もネットワークへのアクセスもしない。正式データのファイルを読むだけ(企画書 §6-1・§6-2)
- 領域の列・強中弱・総合スコア・平均・順位・スコアでの並べ替え・色の濃淡は作らない
  (企画書 §2-3 の「やらないこと」。領域単位の判定は §8 Q-6 で【未決】)
- Streamlit は、操作のたびにこのファイルを 1 行目から実行し直す。上から順に読めば、画面の上から順に対応する
- データ由来の文字列(企業名・モデル名・ベンチマーク名・読めない理由など)は、Markdown として描く部品
  (st.markdown・st.info・st.error・st.caption など)に渡さない。`*`・`_`・`$…$`・`|` などが太字や数式になるため。
  データは st.dataframe・st.text・st.code(どれも Markdown として解釈しない)で出し、Markdown の部品には固定の文だけを渡す
"""

import sys
from pathlib import Path

import streamlit as st

# `streamlit run viewer/app.py` は、このファイルのあるフォルダ(viewer/)を import の探し先に足すが、
# リポジトリのルートは足さない。そのままでは `from viewer.records import ...` が見つからないので、
# ルートを先頭に足す(Streamlit 1.67.0 の streamlit/web/bootstrap.py の `_fix_sys_path` で確かめた)
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from viewer.grid import (  # noqa: E402(上の sys.path の後で import する)
    build_grid,
    companies,
    detail_items,
    filter_by_company,
    last_retrieved_by_company,
    table_header,
    table_rows,
)
from viewer.records import RecordError, load_official  # noqa: E402

# 読むデータの場所は、ここの 2 つだけに書く
OFFICIAL_DIR = REPO_ROOT / "data" / "official"  # 照合済みの正式データ(企画書 §3-3)
DUMMY_DIR = REPO_ROOT / "tests" / "fixtures" / "official"  # 架空の会社・モデル・値

# ダミーを読むのは、起動のときに `-- --dummy` を付けたときだけ。
# 正式データが無いときに、黙ってダミーへ切り替えることはしない(架空の値を、本物と取り違えないため)
USE_DUMMY = "--dummy" in sys.argv[1:]
DATA_DIR = DUMMY_DIR if USE_DUMMY else OFFICIAL_DIR

# 企画書 §4-4「有効性の限界」の 3 つ。文面は企画書を正とし、ここは写し(本文中の節の参照だけを外した)
LIMITS = [
    "公表値は各社の自己申告であり、第三者が検証した値ではない",
    "各社は得意なベンチマークを選んで公表する傾向があり、弱みは「未公表」として現れやすい",
    "手動更新のため、最新モデルの反映に遅れが出る",
]


def shown_path(path):
    """画面に出すパス。リポジトリのルートからの相対で短くする。"""
    return path.relative_to(REPO_ROOT).as_posix()


st.set_page_config(page_title="Anatomia", layout="wide")

# ---- 1. ダミーの表示(最上部) ----
if USE_DUMMY:
    st.warning(
        f"**ダミーデータを表示しています。** 会社・モデル・値はすべて架空で、実在しません"
        f"（読んでいる場所：`{shown_path(DATA_DIR)}`）。"
    )

st.title("Anatomia — モデル × ベンチマーク")

# ---- 2. 有効性の限界(常に出す) ----
st.info("**この画面の値について**\n\n" + "\n".join(f"- {text}" for text in LIMITS))

# ---- 3. 正式データを読む。読めないときは、ここで止める ----
try:
    records = load_official(DATA_DIR)
except (FileNotFoundError, NotADirectoryError):
    st.error(f"正式データのディレクトリがありません：`{shown_path(DATA_DIR)}`")
    st.markdown(
        "照合済みの正式データを `data/official/<会社>.json` に置くと、表が出ます（企画書 §3-3）。\n\n"
        "ダミーデータで画面を見るときは、起動のコマンドの最後に `-- --dummy` を付けてください"
        "（コマンドの全体は viewer/app.py の冒頭）。"
    )
    st.stop()
except RecordError as e:
    # 読めたものだけで表を出すと、読めなかった値が「未公表」に見えてしまう(企画書 §2-4 原則 2)。
    # そのため、1 件でも読めなければ表は出さず、理由を全部出す
    st.error(f"正式データに読めないところが {len(e.problems)} 件あるため、表を出しません。")
    st.code("\n".join(e.problems), language=None)
    st.stop()

if not records:
    st.warning(f"正式データがまだありません（`{shown_path(DATA_DIR)}` にスコアが 0 件）。")
    st.stop()

st.caption(f"`{shown_path(DATA_DIR)}` から {len(records)} 件のスコアを読みました。")

# ---- 4. 企業で絞り込む ----
all_companies = companies(records)
selected = st.multiselect("企業で絞り込む", options=all_companies, default=all_companies, key="企業")
if not selected:
    st.info("企業を 1 つ以上選ぶと、表が出ます。")
    st.stop()
shown = filter_by_company(records, selected)

# ---- 5. 企業ごとの最終取得日(常に出す) ----
# 全体の最新日だけだと、古い企業まで新しく見えるので、企業ごとに出す
st.markdown("**最終取得日**（企業ごと）")
st.dataframe(
    [{"企業": company, "最終取得日": day} for company, day in last_retrieved_by_company(shown).items()],
    hide_index=True,
    width="content",
)

# ---- 6. 「モデル × ベンチマーク」の表 ----
grid = build_grid(shown)
header = table_header(grid)
if len(set(header)) != len(header):
    # 版を名前に含める書き方と別の項目にする書き方が混ざると、別の列に同じ見出しができ得る
    # (viewer/grid.py の BenchmarkColumn.label の注)。見出しで列を見分けられなくなるので、止める
    duplicated = sorted({h for h in header if header.count(h) > 1})
    st.error("表の見出しが重なっているため、表を出せません。重なった見出し：")
    st.code("\n".join(duplicated), language=None)
    st.stop()

# 見出しの文字列から、ベンチマークの列(BenchmarkColumn)を引くための対応
column_by_label = {column.label: column for column in grid.columns}

st.subheader(f"モデル × ベンチマーク（{len(grid.rows)} 行）")
event = st.dataframe(
    [dict(zip(header, row)) for row in table_rows(grid)],
    hide_index=True,
    on_select="rerun",
    # "single-cell"：セルを 1 つ選べるようにする。
    # "single-column"：列も選べるようにすると、ブラウザでの見出しのクリックによる並べ替えが無効になる
    # (st.dataframe の docstring「When column selections are enabled, column sorting is disabled.」)。
    # 並べ替えを出さないために付けている。列を選んでも、この画面では何もしない
    selection_mode=["single-cell", "single-column"],
    # 選んだセルは「何行目・どの列」で覚えられる。絞り込みを変えると同じ番号が別のモデルを指すので、
    # 絞り込みごとに key を変え、絞り込みを変えたら選択を外す
    key="表の選択:" + "|".join(sorted(selected)),
)
st.caption(
    "「未公表」は、正式データにその組の値がないことを示します（低いスコアという意味ではありません）。"
    "「※」は測定条件が付いた値です。条件は、セルを選ぶと下の詳細に出ます。"
)

# ---- 7. 選んだセルの詳細 ----
st.subheader("選んだセルの詳細")
selected_cells = event.selection.cells  # [(行の番号, 列の見出し)]。選んでいなければ空
if not selected_cells:
    st.caption("表のスコアのセルを 1 つ選ぶと、ここに出典 URL・取得日などの詳細が出ます。")
else:
    row_index, column_label = selected_cells[0]
    column = column_by_label.get(column_label)  # 提供企業・モデルなどの列なら None
    if column is None or not 0 <= row_index < len(grid.rows):
        st.caption("ベンチマークの列のセルを選ぶと、詳細が出ます。")
    else:
        # 番号は、ここで行の値(ModelRow)に置き換え、セルは値で引く(viewer/grid.py の cell_at の注)
        row = grid.rows[row_index]
        items = detail_items(grid.cell_at(row, column))
        if not items:
            st.info("選んだセルは「未公表」です（正式データに、この組の値がありません）。")
            st.text(f"{row.label} × {column.label}")
        else:
            # 測定条件だけが違う値は、1 つのセルに複数入る。1 件を 1 行にして並べる
            st.dataframe(
                [dict(item) for item in items],
                hide_index=True,
                column_config={"出典 URL": st.column_config.LinkColumn("出典 URL")},
                placeholder="",
            )

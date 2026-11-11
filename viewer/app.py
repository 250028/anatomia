"""Anatomia の画面(MVP)。「モデル×ベンチマーク」の表を、出典つきで 1 画面に出す。

動かし方(リポジトリのルートで。起動したら、ブラウザで http://127.0.0.1:8501 を開く):
    streamlit run viewer/app.py              → 正式データ(data/official/)を読む
    streamlit run viewer/app.py -- --dummy   → ダミーデータ(tests/fixtures/official/)を読む(`--` の後ろが、このファイルへの引数)

    起動の設定(自分の PC だけで待ち受ける・ブラウザを自動で開かない・利用状況を外へ送らない)と文字の大きさは、
    リポジトリのルートの .streamlit/config.toml に 1 か所でまとめ、理由もそこに書いた。Streamlit は「実行したディレクトリ」の
    .streamlit/config.toml を読むので、必ずリポジトリのルートで実行する。ほかのディレクトリで実行すると設定が読まれず、
    Streamlit の既定(すべての口で待ち受ける・利用状況を送る・文字 16px)になる

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

import pandas as pd  # streamlit が依存していて一緒に入る。表のセルの文字色(Styler)にだけ使う
import streamlit as st

# `streamlit run viewer/app.py` は、このファイルのあるフォルダ(viewer/)を import の探し先に足すが、
# リポジトリのルートは足さない。そのままでは `from viewer.records import ...` が見つからないので、
# ルートを先頭に足す(Streamlit 1.67.0 の streamlit/web/bootstrap.py の `_fix_sys_path` で確かめた)
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from viewer.grid import (  # noqa: E402(上の sys.path の後で import する)
    build_grid,
    cell_position,
    companies,
    detail_items,
    filter_by_company,
    highest_cells,
    label_conflicts,
    last_retrieved_by_company,
    pair_at,
    prefers_transposed,
    table_header,
    table_rows,
    transposed_header,
    transposed_rows,
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

# 表の向きの選択肢(サイドバーの切り替え)
# 未公表のセルに出す記号。表の 8 割を占める「未公表」の文字の繰り返しをやめ、値のあるセルを目に入りやすくする
# (水戸さんの依頼。2026-11-11)。「—」(全角幅のダッシュ)は、表で「値なし」によく使われる静かな記号で、
# 負の数の「-」や、1 つのセルに値を並べる「 / 」と紛れない。意味は「未公表」のまま(凡例に常に出し、詳細では言葉で出す)
NOT_PUBLISHED_MARK = "—"
# 未公表の記号の文字色。値のある文字より薄くする(明るい背景でも暗い背景でも読める灰色)。値のあるセルの濃淡はしない
NOT_PUBLISHED_COLOR = "#9aa0a6"

# ベンチマークごとに、公表された値のうち最大のもの(grid.highest_cells)の文字の色と太さ。
# 水戸さんの依頼(2026-11-11)。明るい背景でも暗い背景(ダークテーマ)でも読める赤を 1 つ選んだ。背景色は付けず、
# 色だけに頼らないように太字にもする(1.67.0 の画面側は、Styler の color・font-weight を表のセルに使う)
HIGHEST_STYLE = "color: #e5484d; font-weight: bold"

MODELS_AS_ROWS = "モデルを行に"
BENCHMARKS_AS_ROWS = "ベンチマークを行に"

# ---- 表の大きさ(数値は Streamlit 1.67.0 の st.dataframe の docstring と、同梱の画面側のコードで確かめた) ----
# 文字の基準の大きさ(.streamlit/config.toml の theme.baseFontSize)と、既定の 16px との比。
# 表の行の高さ・見出しの高さは、画面側でこの比で大きくなる(1.67.0 の同梱の画面側のコードで確かめた)。
# 下の px の数は 16px のときの値で書き、px で高さを決める所(詳細の欄・行が多いときの表)だけ、この比を掛ける
FONT_SCALE = (st.get_option("theme.baseFontSize") or 16) / 16
# 行の高さ(16px のときの px。文字が 18px なら、画面では 27 × 18/16 ≒ 30px)。既定は 35px。
# 文字(16px のとき 14px)の 2 倍ほどで、文字が詰まって見えない範囲で詰め、同じ画面に入る行を増やす。
# 28 → 27 にしたのは、probe のデータ(ベンチマークを行に、23 行)で、表の下の端が 1920×1080 の画面の
# 表示できる高さ(約 915px)を数 px 超える見積もりになったため(1px 詰めると、23 行で約 26px 縮む)
ROW_HEIGHT = 27
# 見出しの行の高さ(16px のときの px)。st.dataframe では変えられず、1.67.0 の画面側の既定値(2.1875rem = 35px)
HEADER_HEIGHT = 35
# 表の中をスクロールせずに全行を出す、行の数の上限。30 行 + 見出しで約 950px(文字 18px のとき)で、1920×1080 の画面の
# 表示できる高さにおおよそ収まる。これを超えると、ページのスクロールで見出しが画面の外に出て、どの列か分からなくなる。
# そのため、超えたときは表をこの行数の高さに固定し、表の中でスクロールする(見出しは表の上に残る)
MAX_ROWS_WITHOUT_SCROLL = 30


# サイドバー(メニュー)の幅(px)。限界の 3 文・絞り込み・表の向き・凡例が、ゆったり読める幅。
# 本文の上に重ねて出すので、広くしても本文(表)の幅は減らない(水戸さんの依頼。2026-11-11)
SIDEBAR_WIDTH_PX = 460
# 最初はメニューを閉じておく。重ねて出す形で最初から開いていると、表の左側(見出しの列)が隠れた状態で始まるため。
# 開く・閉じるは、Streamlit のもともとのボタン(閉じるボタンはメニューの中、開くボタンは本文の左上)
SIDEBAR_INITIAL_STATE = "collapsed"
# メニューの見せ方の CSS(固定の文字列。データ由来の文字は混ぜない)。1.67.0 には正規の指定が無いので、ここ 1 か所にまとめる:
# - 本文(main[data-testid="stMain"])を、画面の幅いっぱいに置く。メニューを開くと、本文を押して狭くせず、上に重なって出る。
#   1.67.0 の同梱の画面側のコードが、画面の幅が狭いとき(md 以下)に本文へ付けている指定
#   (position: absolute; top/left/right/bottom: 0; height: 100dvh)を、どの幅でも付ける
# - メニューの幅を固定し、幅を変える取っ手を隠す(ドラッグで幅を変えられないようにする)
# 頼る名前(stMain・stSidebar・data-collapsed・stSidebarResizeHandle)は 1.67.0 の同梱コード(static/js/index.*.js)にある。
# 版が変わって名前が変わると効かなくなるが、画面は壊れない(メニューが本文を押して狭くする、元の動きに戻るだけ)
SIDEBAR_CSS = f"""<style>
main[data-testid="stMain"] {{
    position: absolute !important;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    height: 100dvh;
}}
section[data-testid="stSidebar"][data-collapsed="false"] {{
    width: {SIDEBAR_WIDTH_PX}px !important;
    min-width: {SIDEBAR_WIDTH_PX}px !important;
    max-width: {SIDEBAR_WIDTH_PX}px !important;
}}
section[data-testid="stSidebar"] div:has(> [data-testid="stSidebarResizeHandle"]) {{
    display: none !important;
}}
</style>"""


def shown_path(path):
    """画面に出すパス。リポジトリのルートからの相対で短くする。"""
    return path.relative_to(REPO_ROOT).as_posix()


def table_height(row_count):
    """表の高さ。上限までは "content"(全行がちょうど入る高さ)、超えたら上限の行数ぶんの高さに固定する。"""
    if row_count <= MAX_ROWS_WITHOUT_SCROLL:
        return "content"
    return round((HEADER_HEIGHT + MAX_ROWS_WITHOUT_SCROLL * ROW_HEIGHT) * FONT_SCALE) + 2  # 2 は上下の枠線(1px ずつ)


def styled_table(header, rows, grid, transposed):
    """表(見出しと行)を、セルの文字色を付けた pandas の Styler にする。色は位置(行・列)で付け、値の文字では判断しない
    (企業名やモデル名が記号と同じ文字でも、取り違えないため)。
    - 未公表のセル：薄い灰色
    - ベンチマークごとに、公表された値のうち最大のセル(grid.highest_cells)：赤い太字
    ほかのセル(値のあるセル)には色を付けない(値の大きさによる濃淡はしない)。"""
    styles = [["" for _ in header] for _ in rows]
    highest = highest_cells(grid)
    for row in grid.rows:
        for column in grid.columns:
            r, c = cell_position(grid, row, column, transposed)
            if not grid.cell_at(row, column).is_published:
                styles[r][c] = f"color: {NOT_PUBLISHED_COLOR}"
            elif (row, column) in highest:
                styles[r][c] = HIGHEST_STYLE
    frame = pd.DataFrame(rows, columns=header)
    return frame.style.apply(lambda _: pd.DataFrame(styles, index=frame.index, columns=frame.columns), axis=None)


def remember_orientation_choice():
    """利用者が表の向きを自分で切り替えたことを覚える(下の「表の向き」の注)。"""
    st.session_state["表の向きを選んだ"] = True


# 1.67.0 の set_page_config は、どこで何回呼んでもよい(docstring)。ページ全体の設定なので最初に置く
st.set_page_config(page_title="Anatomia", layout="wide", initial_sidebar_state=SIDEBAR_INITIAL_STATE)
# メニューを本文の上に重ね、幅を固定する(上の SIDEBAR_CSS の注。set_page_config の initial_sidebar_state に
# 幅〔px〕を渡せるが、最初の幅だけで、ドラッグも、本文を押して狭くする動きも止まらない)
st.html(SIDEBAR_CSS)

# ---- 1. ダミーの表示(本文の最上部。1 行) ----
if USE_DUMMY:
    st.warning("**ダミーデータを表示しています**（会社・モデル・値はすべて架空で、実在しません）")

# ---- 2. サイドバー：タイトルと、有効性の限界(常に出す。折りたたまない) ----
st.sidebar.title("Anatomia")
st.sidebar.caption("各社が公表したベンチマークの値を、モデル × ベンチマークの表で比べる")
st.sidebar.info("**この画面の値について**\n\n" + "\n".join(f"- {text}" for text in LIMITS))

# ---- 3. 正式データを読む。読めないときは、本文に理由を出して止める ----
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

st.sidebar.caption(f"`{shown_path(DATA_DIR)}` から {len(records)} 件のスコアを読みました。")

# ---- 4. サイドバー：企業の絞り込み ----
all_companies = companies(records)
selected = st.sidebar.multiselect("企業で絞り込む", options=all_companies, default=all_companies, key="企業")
if not selected:
    st.info("企業を 1 つ以上選ぶと、表が出ます。")
    st.stop()
shown = filter_by_company(records, selected)
grid = build_grid(shown)

# ---- 5. サイドバー：表の向き ----
# 既定は、絞り込み後のデータで「列の数が少なくなるほう」(grid.prefers_transposed)。
# 利用者が一度でも切り替えたら、その選択を保つ。そのために session_state に 2 つだけ持つ:
# - "表の向き"：切り替えの部品の値(key)。自分で選ぶまでは、毎回データから決めた既定を入れ直す
# - "表の向きを選んだ"：利用者が切り替えたか(on_change で立てる)
if not st.session_state.get("表の向きを選んだ"):
    st.session_state["表の向き"] = BENCHMARKS_AS_ROWS if prefers_transposed(grid) else MODELS_AS_ROWS
orientation = st.sidebar.radio(
    "表の向き", [MODELS_AS_ROWS, BENCHMARKS_AS_ROWS], key="表の向き", on_change=remember_orientation_choice
)
transposed = orientation == BENCHMARKS_AS_ROWS

# ---- 6. 本文のいちばん上：常に出す 1 行(自己申告であること・企業ごとの最終取得日) ----
# メニューは最初は閉じていて、閉じている間は中身が見えないので、企画書 §3-4【案】の「常に表示する」もの
# (データの最終取得日、§4-4 の限界のうち自己申告であること)を、本文に 1 行で出す。自己申告の文は §4-4 の原文のまま。
# 最終取得日は、全体の最新日だけだと古い企業まで新しく見えるので、企業ごとに出す。
# 企業名はデータなので、Markdown として解釈しない st.text で出す(文全体を 1 つの st.text にする)
last_retrieved = "、".join(f"{company} {day}" for company, day in last_retrieved_by_company(shown).items())
st.text(f"{LIMITS[0]}（限界の全文は左のメニュー）。　最終取得日（企業ごと）：{last_retrieved}")

# ---- 7. 「モデル × ベンチマーク」の表 ----
conflicts = label_conflicts(grid, transposed)
if conflicts:
    # 見出しが重なると、選んだ列を見出しから引けず、人も見分けられないので止める
    # (モデルを行に：ベンチマークの版の書き方の混在。ベンチマークを行に：別の企業に同じ名前のモデル、など)
    st.error(f"「{orientation}」の向きでは、表の見出しが重なるため、表を出せません。重なった見出し：")
    st.code("\n".join(conflicts), language=None)
    st.stop()

if transposed:
    header, rows = transposed_header(grid), transposed_rows(grid, not_published=NOT_PUBLISHED_MARK)
    pinned_columns = header[:1]  # ベンチマーク名の列
else:
    header, rows = table_header(grid), table_rows(grid, not_published=NOT_PUBLISHED_MARK)
    pinned_columns = header[: len(header) - len(grid.columns)]  # 提供企業・モデル・種類・推論モード

event = st.dataframe(
    styled_table(header, rows, grid, transposed),
    hide_index=True,
    height=table_height(len(rows)),
    row_height=ROW_HEIGHT,
    # 見出しの列は、横にスクロールしても左に残す。列の幅は指定しない(中身と見出しの文字に合わせて自動で決まり、
    # 見出しも値も省略されない。1.67.0 の画面側では、自動の幅は見出しの文字の幅も測る)
    column_config={name: st.column_config.Column(pinned=True) for name in pinned_columns},
    on_select="rerun",
    # "single-cell"：セルを 1 つ選べるようにする。
    # "single-column"：列も選べるようにすると、ブラウザでの見出しのクリックによる並べ替えが無効になる
    # (st.dataframe の docstring「When column selections are enabled, column sorting is disabled.」)。
    # 並べ替えを出さないために付けている。列を選んでも、この画面では何もしない
    selection_mode=["single-cell", "single-column"],
    # 選んだセルは「何行目・どの列」で覚えられる。絞り込みや向きを変えると、同じ番号が別のセルを指すので、
    # 絞り込みと向きを key に入れ、どちらかを変えたら選択を外す
    key=f"表の選択:{orientation}:" + "|".join(sorted(selected)),
)

# ---- 8. 選んだセルの詳細(表の下、凡例の上) ----
st.markdown("**選んだセルの詳細**")
selected_cells = event.selection.cells  # [(行の番号, 列の見出し)]。選んでいなければ空
pair = pair_at(grid, *selected_cells[0], transposed=transposed) if selected_cells else None
if not selected_cells:
    st.caption("表のセルを選ぶと、ここに詳細（出典 URL・取得日など）が出ます。")
elif pair is None:
    # 提供企業・モデルなどの列や、提供企業の行を選んだとき
    st.caption("スコアのセル（ベンチマークとモデルが交わるところ）を選ぶと、詳細が出ます。")
else:
    # 番号は、pair_at で行と列の値(ModelRow・BenchmarkColumn)に置き換え、セルは値で引く(viewer/grid.py の cell_at の注)
    row, column = pair
    items = detail_items(grid.cell_at(row, column))
    if not items:
        st.info("選んだセルは「未公表」です（正式データに、この組の値がありません）。")
        st.text(f"{row.label} × {column.label}")
    else:
        # 測定条件だけが違う値は、1 つのセルに複数入る。1 件を 1 行にして並べる
        st.dataframe(
            [dict(item) for item in items],
            hide_index=True,
            height="content",
            row_height=ROW_HEIGHT,
            column_config={"出典 URL": st.column_config.LinkColumn("出典 URL")},
            placeholder="",
        )

# ---- 9. 凡例(本文のいちばん下。全文。メニューには置かない〔同じ文を 2 か所に置かない〕) ----
# メニューが閉じていても、記号と赤い太字の意味が分かるように本文に出す(水戸さんの指示。2026-11-11)
st.caption(
    f"「{NOT_PUBLISHED_MARK}」：未公表（その会社が、この値を公表していない。低いスコアという意味ではありません）。  \n"
    "「※」：測定条件が付いた値。条件は、セルを選ぶと詳細に出ます。  \n"
    "赤い太字：そのベンチマークで、公表された値のうち最大のもの（2 つ以上のモデルが公表し、単位がそろうときだけ）。"
    "値が小さいほど良いベンチマークや、測定条件が違う値（※）があるときは、いちばん良い結果とは限りません。"
)

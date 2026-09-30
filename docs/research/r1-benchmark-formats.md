# R-1 各社のベンチマーク公開形式の調査

> **目的**：各社のベンチマークがどの形式で公開されているかを調べ、スクレイピングで取得できるかを判断する（企画書 §5 R-1、Linear 250-57）
> **調査日**：2026-09-30（レビュー反映後の改訂を含む）
> **調査方法**：各ページを 1 回ずつ取得し（間隔 3 秒）、**JavaScript 実行前の生 HTML** に数値が含まれるかを確認した。requests で取れるのはこの生 HTML だけなので、「生 HTML に数値がない＝ requests では取れない」と判断できる。ただし、この基準だけでは Hugging Face のページに混ざる第三者の値を区別できない（§4-1）
> **注意**：この文書の「取得可」「困難」は、**技術的に取れるか（形式上の判定）**。規約上の可否は [R-2](r2-terms-robots.md) を参照する

---

## 1. 結論

- **8 社中 6 社は、各社の主力モデルのどこか 1 か所に「requests + HTML パーサ」で取れる公式ページがある**（Anthropic、Google、Meta、xAI、DeepSeek、Qwen）。**OpenAI（ボット対策で 403）と Mistral（主力モデルは画像）は、主力モデルの数値を取れない**。数えたのは、§2 の「最新の主力モデル」のページ
- **発表ブログは画像が多い。** Google・Mistral・DeepSeek・Meta（ブログ）・Anthropic（一部）は、発表記事ではスコアを画像で載せている。**取得元は「発表ブログ」ではなく「モデルカード」を優先するのがよい**
- **Mistral の主力モデル（Small 4・Large 3・Medium 3.5）は、公式の数値が画像。** 一方、**小型の Ministral 3 系は Hugging Face の README にベンチマークが Markdown の表で載っている**。主力モデルを取るには手入力が必要で、企画書 §8 Q-1（画像の値を手入力で認めるか）の判断待ちになる。Ministral 3 系を §4-3 の「現行主力モデル」に数えてよいかは R-3 で判断する
- **同じ会社でもモデル・ページによって形式が変わる**（例：Anthropic は Opus 5.5 が HTML 表、Fable 5 が画像）。対象を決めたら、モデルごとに取得元を記録しておく必要がある

## 2. 企業 × 公開形式の一覧

形式の凡例：
- **HTML表**：`<table>` タグの表。requests + パーサで取れる
- **HTML(div)**：`<div>` を並べて表に見せている。数値は生 HTML にあるので取れるが、`<table>` 用の処理は使えず、ページごとに要素の指定が必要
- **Markdown**：Hugging Face の README.md を生データで取得できる
- **画像**：数値が画像の中にしかない。スクリプトでは取れない
- **JS描画**：生 HTML に本文がない。Playwright が必要
- **取得拒否**：ボット判定などで中身を取れない

「技術的に取れるか」の列は形式上の判定で、規約上の可否は含まない（[R-2](r2-terms-robots.md) を参照）。

| 企業 | 最新の主力モデル（調査日時点） | 公式ページ | 形式 | 生HTMLで取得 | 測定条件の記載 | 技術的に取れるか |
| --- | --- | --- | --- | --- | --- | --- |
| OpenAI | GPT-6 Astra、GPT-5.6 Sol など | [発表記事](https://openai.com/index/gpt-6-astra/) | 取得拒否（Cloudflare のボット判定で 403） | × | 不明 | **困難** |
| | | [システムカード](https://deploymentsafety.openai.com/gpt-5-6-preview) | HTML表 | ○ | あり | 安全性評価が中心で、性能ベンチマークは載っていない |
| | | Hugging Face（openai 組織）、GitHub（openai/simple-evals） | — | — | — | 主力モデルの公式の値がない（§3） |
| Anthropic | Claude Opus 5.5、Fable 5 | [Opus 5.5 発表](https://www.anthropic.com/claude-opus-5-5) | HTML表（19 行、脚注・「with tools」などの条件つき） | ○ | あり | **取得可** |
| | | [Fable 5 発表](https://www.anthropic.com/news/claude-fable-5-mythos-5) | 画像 | × | — | ページによる |
| Google | Gemini 3.8 Flash、3.5 Flash など | [ブログ（3.5 / 3.8 Flash）](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-5/) | 画像（本文に一部数値あり） | × | — | ブログは不可 |
| | | [DeepMind モデルカード（3.5 Flash）](https://deepmind.google/models/model-cards/gemini-3-5-flash/) | HTML表（測定条件の列あり） | ○ | あり | **取得可** |
| | | [DeepMind モデルカード（3.8 Flash）](https://deepmind.google/models/model-cards/gemini-3-8-flash/) | HTML表（レビューでの確認） | ○ | あり | **取得可** |
| Meta | Muse Spark 1.1 / 1.2 | [AI at Meta ブログ](https://ai.meta.com/blog/introducing-muse-spark-meta-model-api/) | 画像。curl では 400 エラー | × | — | ブログは不可 |
| | | [Meta for Developers モデルページ](https://dev.meta.ai/models/muse-spark-1-1) | HTML(div) | ○ | 一部（「w/ tools」など） | **取得可**（取得元は dev.meta.ai に固定。旧 URL の developer.meta.com は dev.meta.ai へ 302・308 でリダイレクトされる） |
| xAI | Grok 4.7 | [発表記事](https://x.ai/news/grok-4-7) | HTML(div) | ○ | あり（注記・アスタリスク） | **取得可** |
| | | [モデルカード PDF](https://media.x.ai/v1/website/4p7card-5eccc980.pdf) | PDF（テキスト形式、グラフはベクター） | △ | — | 本文の文字の符号化が特殊で、簡易抽出では読めない。R-9 で要検証 |
| Mistral AI | Mistral Small 4、Mistral Large 3、Mistral Medium 3.5（Medium 3.5 はレビューで追加。README に "Mistral Medium 3.5 is now powering Le Chat" とある） | [発表記事](https://mistral.ai/news/mistral-small-4/) | 画像 | × | — | **困難**（主力モデル） |
| | | [Hugging Face モデルカード（Small 4）](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603) | 画像 | × | — | 同上 |
| | | Hugging Face モデルカード（Large 3：`Mistral-Large-3-675B-Instruct-2512`、Medium 3.5：`Mistral-Medium-3.5-128B`）（レビューでの確認） | 画像（Large 3 は 3 枚、Medium 3.5 は 4 枚。Medium 3.5 は本文に τ³-Telecom 91.4%・SWE-Bench Verified 77.6% の 2 つだけ数値あり） | × | — | 同上 |
| | | [Hugging Face モデルカード（Ministral 3 系）](https://huggingface.co/mistralai/Ministral-3-14B-Instruct-2512)（レビューでの確認） | **Markdown**（README の「Benchmark Results」に Reasoning・Instruct・Base の 3 つの表。画像は 0 枚。3B・8B・14B が同じ表） | ○ | 表による | **取得可**（Ministral 3 系のみ。主力モデルではない） |
| DeepSeek | DeepSeek-V4-Pro、V4.1-Flash | [API ドキュメントのニュース](https://api-docs.deepseek.com/news/news260424/) | 画像 | × | — | ニュースは不可 |
| | | [Hugging Face モデルカード](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro) | Markdown（README.md） | ○ | あり（shot 数・Pass@1・推論モード） | **取得可** |
| Alibaba (Qwen) | Qwen3.8 系、Qwen3.6-27B | [公式ブログ](https://qwen.ai/blog?id=qwen3.6-27b) | JS描画（生 HTML に本文なし） | × | — | Playwright なら可能性あり |
| | | [Hugging Face モデルカード](https://huggingface.co/Qwen/Qwen3.8-27B) | HTML表（README.md 内に HTML の `<table>` を直書き） | ○ | 一部（harness 名など） | **取得可** |

## 3. 取得が難しい企業と理由

| 企業 | 理由 | 考えられる対応 |
| --- | --- | --- |
| OpenAI | 発表記事・ヘルプセンターが Cloudflare のボット判定で 403。「Enable JavaScript and cookies」のチャレンジ画面が返る。Hugging Face・GitHub にも、主力モデルの公式の値がない（レビューでの確認）。HF の openai 組織にある言語モデルは gpt-oss 系（2025-08 作成）や研究用のモデルで、GPT-6 Astra・GPT-5.6 はなく、gpt-oss-120b の README にも表はなく arXiv のモデルカードへのリンクだけ。GitHub の openai/simple-evals は "July 2025: simple-evals will no longer be updated for new models or benchmark results." とあり、表は最新でも o3・o4-mini・GPT-4.1 まで | ①ボット判定を回避してまで取得するのは R-2 の観点で避けたい。②手入力を認めるか（Q-1）を先生に確認する。③対象外にする |
| Mistral AI（主力モデル） | 公式ブログ・Hugging Face ともに、主力モデル（Small 4・Large 3・Medium 3.5）のベンチマークが画像だけ。**Ministral 3 系は HF の README に Markdown の表がある**ので、こちらはスクリプトで取れる | 主力モデルは手入力を認めるか（Q-1）次第。認めなければ、Ministral 3 系を §4-3 の「現行主力モデル」に数えるか（R-3 で判断）、または対象外 |

> **補足**：OpenAI と Mistral（主力モデル）を外しても、残り 6 社（Anthropic、Google、Meta、xAI、DeepSeek、Qwen）で成功の定義「5 社以上」は満たせる見込み。ただし、ここでの「取得可」は形式上の判定で、**R-2（利用規約・robots.txt）の規約上の判定で、実際に取得可と判断できる社数は減っている**。R-3 では、この文書と R-2 の両方を読んで選定する

## 4. 調査で分かった注意点

1. **Hugging Face の「Evaluation results」は公式値とは限らない**
   Mistral のモデルページに GPQA Diamond の値が出ていたが、元データ（`.eval_results/gpqa_diamond.yaml`）は `verified: false`、`pullRequest: 2` で、**第三者のプルリクエストで提案された値**だった。企画書 §2-3「第三者の値は取り込まない」に反するので使わない。レビューで、同じ未検証の値が DeepSeek-V4-Pro のページに 22 件（すべて `verified: false`、10 本の PR 由来、うち 13 件は arXiv やベンチマークのサイトなど外部の出典）、Qwen3.8-27B のページに 18 件（すべて `verified: false`）あることも確認された。どちらも README の表と同じ生 HTML の中に JSON として埋め込まれている。Hub API のファイル一覧では、main に `.eval_results/` が 1 つもない。つまり、マージされていない PR の値がページに表示されていると考えられる。**レンダリング後のページは使わず、README.md の生ファイルから取る**
   - **値の出所と取得経路を分けて考える**：企画書 §2-3 が除外するのは「第三者機関のリーダーボードの値」で、基準は「各社が公表した値か」。deepseek-ai・Qwen などの**公式組織が README に書いた表は、置き場所が HF でも各社の公表値**にあたる。取得経路の規約上の扱いは R-2 が確認している
   - **取得方法**：README.md は、HF がプログラムからの取得に推奨している huggingface_hub（`hf_hub_download`。URL に `/resolve/` を含む経路）で生ファイルとして取る（R-2 §5）。PR の値が混ざる余地がなく、HF の画面の作りが変わっても影響を受けにくい。取得元は公式組織のリポジトリに限る（Hub API の `author` で確認できる）。パーサは、Markdown の表（DeepSeek・Ministral 3）と、README に直書きされた HTML の表（Qwen）の両方に対応が要る
   - **版の記録**：Hub API はリポジトリの `sha` を返す（レビュー時点で DeepSeek-V4-Pro は `b5968e9…`、lastModified は 2026-06-22）。企画書 §3-3 の出典 URL・取得日と一緒に残せば、公開後に README が編集されても、③の確認でどの版の値かを特定できる
2. **ベンチマーク名の表記ゆれがある。ただし「表記」と「別のベンチマーク」を区別する**
   - **表記ゆれの例（正規化で揃えてよい）**：DeepSeek は「SWE Verified (Resolved)」、他社は「SWE-bench Verified」。Anthropic は「Terminal-Bench 4.0」、他社は「Terminal-bench 4.0」のように、大文字小文字・ハイフン・空白が違う
   - **別のベンチマーク（揃えてはいけない）**：Google のモデルカードには、Gemini 3.8 Flash の同じ表に「Terminal-bench 2.1」（Agentic terminal coding、89.4%）と「Terminal-bench 4.0」（General agent capabilities、19.1%）が別の行として載っている（レビューでの確認）。同じモデルで 89.4% と 19.1% なので、名前を揃えると比較できない値を同じ列に並べることになり、企画書 §2-4 の原則 3（条件が異なる値は条件を明示して並べる）の前提が崩れる。Anthropic の Terminal-Bench 4.0 と比べられるのは、Google の 2.1 ではなく 4.0 の行。Google のカードの中でも、3.5 Flash は「GDPval-AA」、3.8 Flash は「GDPVal-AA v2」と、世代によって版が変わる
   - **方針**：工程②の正規化で揃えるのは**表記（大文字小文字・ハイフン・空白）だけ**にする。**版（2.1／4.0、v2）や種類（SWE-bench Verified／Pro）が違えば、別のベンチマークとして扱う**（R-4・R-5 へ引き継ぐ。§5）
3. **表の中に装飾が混ざる**
   最高値が太字（Markdown の `**94.3**`）になっている、脚注記号（`66.4%¹`）がつく、未公表を「—」「-」「--」で表す、など。抽出時に取り除く処理が要る
4. **ページの作りは企業ごとに違う**
   HTML(div) のページ（Meta、xAI）は `<table>` 用の処理が使えないため、企業ごとに専用の抽出処理を書くことになる。ページの構造が変わると壊れやすいので、企画書 §3-2 ③ の人による確認が重要になる
5. **アクセスのしかたで結果が変わるページがある**
   `ai.meta.com` は curl でアクセスすると 400 になる。`developer.meta.com` は `dev.meta.ai` へのリダイレクトがある。**Meta の取得元は `https://dev.meta.ai/models/muse-spark-1-1` に固定する**（R-2 §5）
6. **モデルカードの表には他社モデルの値も並んでいる。取り込むのは「自社モデルの値」だけにする**（レビューでの確認）
   表を確認できたページは、すべて他社モデルとの比較表だった。Gemini 3.8 Flash は Claude Opus 5・GPT-5.6 Sol などの列と、API 料金（Input price $/1M tokens）の行がある。DeepSeek-V4-Pro は Opus-4.6 Max・GPT-5.4 xHigh・Gemini-3.1-Pro High など、Qwen3.8-27B は Opus4.6 Max など、Ministral 3 は Qwen3-14B・Gemma3-12B などがある。他社の列の値は、カードを書いた企業が測った（または引用した）値で、出典はその企業のページ。企画書 §2-3 の「出典の性質が混ざると、比較の前提が崩れる」にあたる
   - **ルール**：取り込むのは、そのモデルの企業自身のページの自社モデルの値だけ。特に、§3 で困難とした OpenAI の値（GPT-5.6 Sol など）を、Google のカードから埋めない。同じモデルの値が複数のページにあるときは、そのモデル自身のページを正とする
7. **推論モードや単位が混在する**（レビューでの確認）
   同じモデルに推論モード別の値が複数ある（DeepSeek-V4-Pro の Non-Think／High／Max）。単位も混在する（Ministral 3 は 0.850 のような小数、Gemini は %、GDPval は Elo）。抽出の設計で漏れないよう、R-5・R-9 へ引き継ぐ。料金の行は R-6 の参考にもなる

## 5. 他の調査項目への引き継ぎ

| 引き継ぎ先 | 内容 |
| --- | --- |
| R-2（利用規約・robots.txt） | 取得候補のページ：anthropic.com、deepmind.google、dev.meta.ai、x.ai、huggingface.co。特に Hugging Face は企業ではなく**第三者のプラットフォーム**なので、HF 自体の規約も確認が必要（**R-2 で確認済み**。判定は R-2 を参照）。この文書の「取得可」は形式上の判定で、規約上の可否は R-2 で決まる |
| R-3（対象の選定） | 形式上の取得可：Anthropic、Google、Meta、xAI、DeepSeek、Qwen ／ 困難：OpenAI、Mistral（主力モデル）。Mistral の Ministral 3 系は HF に Markdown の表があり、§4-3 の「現行主力モデル」に数えるかは R-3 で判断する。**規約上の可否は R-2 を参照して選定する** |
| R-4・R-5（ベンチマークの正規化・測定条件） | 正規化で揃えるのは**表記（大文字小文字・ハイフン・空白）だけ**にし、**版（2.1／4.0、v2）や種類（Verified／Pro）が違えば別のベンチマークとして扱う**（§4-2）。同じモデルの推論モード別の値と、単位の混在（小数・%・Elo）も設計に入れる（§4-7） |
| R-5（測定条件） | 条件の書き方が企業ごとにバラバラ（表の列／脚注／セル内の注記「with tools」）。取得可の 6 社はいずれも何らかの形で条件を載せている |
| R-6（料金） | Gemini のモデルカードなど、比較表に API 料金の行がある（§4-6） |
| R-9（収集技術） | 当面は **requests + HTML パーサで足りる**（取得可の 6 社はすべて生 HTML に数値がある）。Playwright が要るのは Qwen 公式ブログのみで、モデルカードを使えば不要。PDF（xAI モデルカード）は pdfplumber での抽出を要検証。**HF は README.md を `hf_hub_download` で生ファイルとして取り、公式組織のリポジトリに限り、リポジトリの `sha` を出典 URL・取得日と一緒に記録する**（§4-1）。**取り込むのは自社モデルの値だけ**（§4-6） |
| §8 Q-1（画像の値の扱い） | OpenAI と Mistral の主力モデルを対象に含めるかどうかがこの判断で決まる。先生への確認が必要 |

## 6. この調査の限界

- 各社 1〜3 ページのみの確認。他のモデル（旧モデルや小型モデル）のページは形式が違う可能性がある
- 取得は 2026-09-30 の 1 回だけ。ページの構造は予告なく変わる
- OpenAI の発表記事は中身を確認できていないため、形式（表か画像か）は不明
- **「レビューでの確認」と書いた内容**（Ministral 3 系・Large 3・Medium 3.5 の形式、Gemini 3.8 Flash のカード、DeepSeek・Qwen の未検証の値の件数、OpenAI の HF・GitHub の状況、Hub API の `sha`）は、レビュアーが 2026-09-30 に確認した結果を反映したもので、私たち自身では再確認していない。取得を始める前に再確認する
- この文書の「取得可」は形式上の判定で、規約上の可否は R-2 に従う

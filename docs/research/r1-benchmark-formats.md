# R-1 各社のベンチマーク公開形式の調査

> **目的**：各社のベンチマークがどの形式で公開されているかを調べ、スクレイピングで取得できるかを判断する（企画書 §5 R-1、Linear 250-57）
> **調査日**：2026-09-30
> **調査方法**：各ページを 1 回ずつ取得し（間隔 3 秒）、**JavaScript 実行前の生 HTML** に数値が含まれるかを確認した。requests で取れるのはこの生 HTML だけなので、「生 HTML に数値がない＝ requests では取れない」と判断できる

---

## 1. 結論

- **8 社中 7 社は、どこか 1 か所に「requests + HTML パーサ」で取れる公式ページがある。** OpenAI だけは性能ベンチマークを載せたページ自体が取得できない（ボット対策で 403）
- **発表ブログは画像が多い。** Google・Mistral・DeepSeek・Meta（ブログ）・Anthropic（一部）は、発表記事ではスコアを画像で載せている。**取得元は「発表ブログ」ではなく「モデルカード」を優先するのがよい**
- **Mistral は公式の数値がすべて画像。** 取得するなら手入力が必要で、企画書 §8 Q-1（画像の値を手入力で認めるか）の判断待ちになる
- **同じ会社でもモデル・ページによって形式が変わる**（例：Anthropic は Opus 5.5 が HTML 表、Fable 5 が画像）。対象を決めたら、モデルごとに取得元を記録しておく必要がある

## 2. 企業 × 公開形式の一覧

形式の凡例：
- **HTML表**：`<table>` タグの表。requests + パーサで取れる
- **HTML(div)**：`<div>` を並べて表に見せている。数値は生 HTML にあるので取れるが、`<table>` 用の処理は使えず、ページごとに要素の指定が必要
- **Markdown**：Hugging Face の README.md を生データで取得できる
- **画像**：数値が画像の中にしかない。スクリプトでは取れない
- **JS描画**：生 HTML に本文がない。Playwright が必要
- **取得拒否**：ボット判定などで中身を取れない

| 企業 | 最新の主力モデル（調査日時点） | 公式ページ | 形式 | 生HTMLで取得 | 測定条件の記載 | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| OpenAI | GPT-6 Astra、GPT-5.6 Sol など | [発表記事](https://openai.com/index/gpt-6-astra/) | 取得拒否（Cloudflare のボット判定で 403） | × | 不明 | **困難** |
| | | [システムカード](https://deploymentsafety.openai.com/gpt-5-6-preview) | HTML表 | ○ | あり | 安全性評価が中心で、性能ベンチマークは載っていない |
| Anthropic | Claude Opus 5.5、Fable 5 | [Opus 5.5 発表](https://www.anthropic.com/claude-opus-5-5) | HTML表（19 行、脚注・「with tools」などの条件つき） | ○ | あり | **取得可** |
| | | [Fable 5 発表](https://www.anthropic.com/news/claude-fable-5-mythos-5) | 画像 | × | — | ページによる |
| Google | Gemini 3.8 Flash、3.5 Flash など | [ブログ（3.5 / 3.8 Flash）](https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-3-5/) | 画像（本文に一部数値あり） | × | — | ブログは不可 |
| | | [DeepMind モデルカード（3.5 Flash）](https://deepmind.google/models/model-cards/gemini-3-5-flash/) | HTML表（測定条件の列あり） | ○ | あり | **取得可** |
| Meta | Muse Spark 1.1 / 1.2 | [AI at Meta ブログ](https://ai.meta.com/blog/introducing-muse-spark-meta-model-api/) | 画像。curl では 400 エラー | × | — | ブログは不可 |
| | | [Meta for Developers モデルページ](https://developer.meta.com/ai/models/muse-spark-1-1/) | HTML(div) | ○ | 一部（「w/ tools」など） | **取得可**（dev.meta.ai へリダイレクト） |
| xAI | Grok 4.7 | [発表記事](https://x.ai/news/grok-4-7) | HTML(div) | ○ | あり（注記・アスタリスク） | **取得可** |
| | | [モデルカード PDF](https://media.x.ai/v1/website/4p7card-5eccc980.pdf) | PDF（テキスト形式、グラフはベクター） | △ | — | 本文の文字の符号化が特殊で、簡易抽出では読めない。R-9 で要検証 |
| Mistral AI | Mistral Small 4、Mistral Large 3 | [発表記事](https://mistral.ai/news/mistral-small-4/) | 画像 | × | — | **困難** |
| | | [Hugging Face モデルカード](https://huggingface.co/mistralai/Mistral-Small-4-119B-2603) | 画像 | × | — | 同上 |
| DeepSeek | DeepSeek-V4-Pro、V4.1-Flash | [API ドキュメントのニュース](https://api-docs.deepseek.com/news/news260424/) | 画像 | × | — | ニュースは不可 |
| | | [Hugging Face モデルカード](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro) | HTML表 ／ Markdown（README.md） | ○ | あり（shot 数・Pass@1・推論モード） | **取得可** |
| Alibaba (Qwen) | Qwen3.8 系、Qwen3.6-27B | [公式ブログ](https://qwen.ai/blog?id=qwen3.6-27b) | JS描画（生 HTML に本文なし） | × | — | Playwright なら可能性あり |
| | | [Hugging Face モデルカード](https://huggingface.co/Qwen/Qwen3.8-27B) | HTML表（README.md 内に HTML の `<table>` を直書き） | ○ | 一部（harness 名など） | **取得可** |

## 3. 取得が難しい企業と理由

| 企業 | 理由 | 考えられる対応 |
| --- | --- | --- |
| OpenAI | 発表記事・ヘルプセンターが Cloudflare のボット判定で 403。「Enable JavaScript and cookies」のチャレンジ画面が返る | ①ボット判定を回避してまで取得するのは R-2 の観点で避けたい。②手入力を認めるか（Q-1）を先生に確認する。③対象外にする |
| Mistral AI | 公式ブログ・Hugging Face ともにベンチマークが画像だけ | 手入力を認めるか（Q-1）次第。認めなければ対象外 |

> **補足**：OpenAI と Mistral を外しても、残り 6 社（Anthropic、Google、Meta、xAI、DeepSeek、Qwen）で成功の定義「5 社以上」は満たせる見込み。ただし R-2（利用規約・robots.txt）の結果で減る可能性がある。

## 4. 調査で分かった注意点

1. **Hugging Face の「Evaluation results」は公式値とは限らない**
   Mistral のモデルページに GPQA Diamond の値が出ていたが、元データ（`.eval_results/gpqa_diamond.yaml`）は `verified: false`、`pullRequest: 2` で、**第三者のプルリクエストで提案された値**だった。企画書 §2-3「第三者の値は取り込まない」に反するので使わない。取得するのは README の本文（公式が書いた表）に限る
2. **ベンチマーク名の表記ゆれが実際にある**
   例：DeepSeek は「SWE Verified (Resolved)」、他社は「SWE-bench Verified」。Google のモデルカードは「Terminal-bench 2.1」、Anthropic は「Terminal-Bench 4.0」。工程②の正規化で吸収する必要がある
3. **表の中に装飾が混ざる**
   最高値が太字（Markdown の `**94.3**`）になっている、脚注記号（`66.4%¹`）がつく、未公表を「—」「-」「--」で表す、など。抽出時に取り除く処理が要る
4. **ページの作りは企業ごとに違う**
   HTML(div) のページ（Meta、xAI）は `<table>` 用の処理が使えないため、企業ごとに専用の抽出処理を書くことになる。ページの構造が変わると壊れやすいので、企画書 §3-2 ③ の人による確認が重要になる
5. **アクセスのしかたで結果が変わるページがある**
   `ai.meta.com` は curl でアクセスすると 400 になる。`developer.meta.com` は `dev.meta.ai` へのリダイレクトがある。R-2 で規約を確認したうえで、取得元 URL を固定しておくのがよい

## 5. 他の調査項目への引き継ぎ

| 引き継ぎ先 | 内容 |
| --- | --- |
| R-2（利用規約・robots.txt） | 取得候補のページ：anthropic.com、deepmind.google、developer.meta.com / dev.meta.ai、x.ai、huggingface.co。特に Hugging Face は企業ではなく**第三者のプラットフォーム**なので、HF 自体の規約も確認が必要 |
| R-3（対象の選定） | 取得可：Anthropic、Google、Meta、xAI、DeepSeek、Qwen ／ 困難：OpenAI、Mistral |
| R-5（測定条件） | 条件の書き方が企業ごとにバラバラ（表の列／脚注／セル内の注記「with tools」）。取得可の 6 社はいずれも何らかの形で条件を載せている |
| R-9（収集技術） | 当面は **requests + HTML パーサで足りる**（取得可の 6 社はすべて生 HTML に数値がある）。Playwright が要るのは Qwen 公式ブログのみで、モデルカードを使えば不要。PDF（xAI モデルカード）は pdfplumber での抽出を要検証 |
| §8 Q-1（画像の値の扱い） | OpenAI・Mistral を対象に含めるかどうかがこの判断で決まる。先生への確認が必要 |

## 6. この調査の限界

- 各社 1〜3 ページのみの確認。他のモデル（旧モデルや小型モデル）のページは形式が違う可能性がある
- 取得は 2026-09-30 の 1 回だけ。ページの構造は予告なく変わる
- OpenAI の発表記事は中身を確認できていないため、形式（表か画像か）は不明

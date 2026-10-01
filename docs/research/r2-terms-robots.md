# R-2 各社サイトの利用規約・robots.txt の確認

> **目的**：スクレイピングが許容されているかを確認し、禁止されているサイトを対象から外す（企画書 §5 R-2、Linear 250-58）
> **調査日**：2026-09-30（レビュー反映後の改訂を含む）
> **対象**：R-1（[r1-benchmark-formats.md](r1-benchmark-formats.md)）で取得元の候補になったドメインと、困難と判定した 2 社のドメイン
> **注意**：これは法的な判断ではない。規約の文面を読んだうえでの整理であり、「要相談」は先生に確認する

---

## 1. 結論

判定の単位は「企業」ではなく「**企業 × 取得元**」とし、「規約上の判定」と「技術的に取れるか」を分けて示す。

| 企業 | 取得元 | 規約上の判定 | 技術的に取れるか（R-1） | 総合 |
| --- | --- | --- | --- | --- |
| Google | deepmind.google | 取得可（robots.txt 準拠が条件で、`Allow: /`） | 取れる | **取得可** |
| DeepSeek | huggingface.co（README.md） | 取得可（HF の整理が前提。§4） | 取れる | **取得可（先生の確認待ち）** |
| Qwen | huggingface.co（README.md） | 取得可（同上） | 取れる | **取得可（先生の確認待ち）** |
| Mistral AI | huggingface.co（README.md） | 取得可（同上。自社規約の対象は自社の Products のみ） | Ministral 3 系は Markdown の表で取れる。主力モデル（Small 4・Large 3・Medium 3.5）は数値が画像のみ | **Ministral 3 系のみ取得可（先生の確認待ち）。主力モデルは手入力（Q-1）が必要** |
| Anthropic | anthropic.com | 要相談（スクリプトでのアクセスを禁止。§3-1、§4） | ページによる（Opus 5.5 は HTML の表、Fable 5 は画像） | **要相談** |
| xAI | x.ai | 要相談（AUP がスクリプトでのアクセスを禁止。§3-1、§4） | 取れる | **要相談** |
| Meta | dev.meta.ai | 要相談（不可寄り。Meta の規約は自動データ収集に書面の許可を求める） | 取れる | **要相談（不可寄り）。判断は Q-1 の答えで決まる。質問 B の対象には加えない（理由は §4）** |
| OpenAI | openai.com | 不可（規約が自動抽出を禁止） | ボット対策で取れない。HF・GitHub にも主力モデルの公式の値がない | **不可** |

- **現時点で取得可と判断したのは Google・DeepSeek・Qwen の 3 社。** うち DeepSeek・Qwen は質問 A（Hugging Face の整理）について先生の確認待ちなので、**先生の確認なしで取得できるのは Google だけ**。スクリプトでの取得だけで成功の定義「5 社以上」に届かせるには、下の 2 点の確認が要る（Q-1 で手入力が認められれば、これとは別に社数が増える可能性がある。§4）
  1. 質問 A（Hugging Face の整理。§4）が認められる → DeepSeek・Qwen（と Mistral の Ministral 3 系）が確定
  2. 質問 B（「消費者向け規約は公開ページの低頻度な取得にも適用されるか」。§4）が「適用されない」となる（主なルート）、または「robots.txt の `Allow: /` を許可とみなせる」となる（**根拠は弱い**。§4 の質問 B にある反対の材料を参照）→ Anthropic・xAI が加わり、Google・DeepSeek・Qwen・Anthropic・xAI の 5 社に届く
- **Mistral の Ministral 3 系は、この 3 社・5 社の数に含めていない。** 小型モデルだけなので、企画書 §4-3 の「現行主力モデル」に数えるかは R-3 で判断する。数える場合は、質問 A が認められた時点で 4 社になり、質問 B で Anthropic か xAI の**どちらか 1 社**が加われば 5 社に届く
- robots.txt だけを見ると、**どのサイトも取得先のページを禁止していない**。可否を分けているのは利用規約のほう

## 2. robots.txt

2026-09-30 に各ドメインの `/robots.txt` を取得した。

| ドメイン | 取得先ページへの制限 | 補足 |
| --- | --- | --- |
| openai.com | なし（`Allow: /`） | ただし実際のページは Cloudflare のボット判定で 403（R-1） |
| www.anthropic.com | なし（`Allow: /`） | |
| deepmind.google | なし（`Allow: /`） | |
| blog.google | なし（検索ページのみ `Disallow`） | |
| ai.meta.com | なし（`/ajax/`、`/*.php` などのみ `Disallow`） | 冒頭に「Facebook 上のデータを自動手段で収集するには、書面の許可が必要」という注意書き。`Scrapy` など一部のボットは全面禁止 |
| developer.meta.com | なし（同上） | 同じ注意書きあり。ただし Facebook 上のデータについての文言で、取得先の dev.meta.ai には当てはまらない。R-1 初版の URL は dev.meta.ai へ 302・308 でリダイレクトされる |
| dev.meta.ai | なし（同上） | **Meta の取得元はここに固定する（URL は R-1 §4-5 に書く）。** robots.txt の注意書きはなし。ページの「利用規約」リンクは Facebook 利用規約に遷移する（§3-3） |
| x.ai | なし（`/tools/` のみ `Disallow`） | `Content-Signal: ai-train=yes, search=yes, ai-input=yes`（AI 学習［ai-train］・検索［search］・AI への入力［ai-input］という利用目的についての宣言。Anatomia の用途［比較表への掲載］はどれにも当たらない） |
| mistral.ai | なし（`Allow: /`） | |
| huggingface.co | なし（`User-agent: *` / `Allow: /` のみ。`/api/`・`/raw/`・`/resolve/` への `Disallow` もない） | |
| api-docs.deepseek.com | robots.txt が存在しない（HTML が返る） | |
| qwen.ai | robots.txt が存在しない（HTML が返る） | |

## 3. 利用規約

### 3-1. 企業ごとの該当条項

| 企業 | 規約 | 該当条項（原文） | 読み取れること |
| --- | --- | --- | --- |
| Google | [Google 利用規約](https://policies.google.com/terms)「Don't abuse our services」 | "using automated means to access content from any of our services **in violation of the machine-readable instructions on our web pages (for example, robots.txt files ...)**" | **robots.txt に従う限り、自動アクセスは禁止されていない。** deepmind.google は `Allow: /` なので問題なし |
| Hugging Face | [Terms of Service](https://huggingface.co/terms-of-service)（Effective Date: 2022-09-15）、[Content Policy](https://huggingface.co/content-policy)（規約に組み込まれた方針） | 規約：自動取得を禁止する条項はない。ただし "all of our policies available on our Website" の順守を求め、"Any Content you download, access or use from us or another User, is at your own risk and **subject to these Terms and/or the terms accompanying such Content**" とある。Content Policy には濫用の例として "Using tools like Cloudflare Tunnel, TOR, proxies, VNC, Chrome Remote Server, etc., to bypass restrictions" と "excessive bulk activity" がある | 自動取得を禁止する条項はない。**低頻度で読むだけなら当たらないが、「間隔を空け、制限を回避しない」ことを守る。§6-3 のルールを HF にも適用する。** 公開リポジトリのコンテンツを HF の機能を通じて使用・複製することを許諾する条項があり、質問 A の根拠になる。DeepSeek・Qwen・Mistral（確認したのは Small 4）の License にも取得を制限する条件はない。全文の確認結果と各 License は §3-3 |
| xAI | [Terms of Service - Consumer](https://x.ai/legal/terms-of-service)（Last Updated: 2026-09-11）と、規約が取り込む [Acceptable Use Policy](https://x.ai/legal/acceptable-use-policy)（Effective: 2026-08-14） | 規約：「Service」に "associated applications, features, tools, software and websites" を含み、"By accessing and using our Service, you acknowledge and agree to these Terms and any other applicable terms and policies, including our Acceptable Use Policy." とある。AUP："applies to anyone using our Service"。禁止事項に "**Accessing the Services through unauthorized automated or non-human means, whether through a bot, script, or otherwise**" | **スクリプトでのアクセスを禁止しており、Anthropic の規約とほぼ同じ文言・構造。** 判定は Anthropic と同じ「要相談」。初版で引用した "any robot, spider, scraper ... than a human can reasonably produce ..." は現行の規約本文にないため、「人間と同程度の頻度なら禁止に当たらない」という読み方は根拠にしない。取得元の x.ai の発表記事が「本サービス」に含まれるかは、規約から読み取れない。ブラウザでの確認結果は §3-3 |
| Anthropic | [Consumer Terms of Service](https://www.anthropic.com/legal/consumer-terms) §3（Effective: 2025-10-08） | "To **crawl, scrape, or otherwise harvest data** or information from our Services other than as permitted under these Terms."／"**Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it, to access the Services through automated or non-human means, whether through a bot, script, or otherwise.**"／"Services" = "Claude.ai, Claude Pro, and other products and services ... along with any associated apps, software, **and websites**"／"By accessing our Services, you agree to these Terms."（レビューでの確認） | **ウェブサイトのスクレイピング・スクリプトでのアクセスも禁止対象**と読める。ただしこれは Claude の利用者向けの規約で、アカウントを持たずにサイトを見るだけの人にも適用されるかははっきりしない。"explicitly permit" を robots.txt の `Allow: /` が満たすかも論点 → 要相談 |
| Meta | [Automated Data Collection Terms](https://www.facebook.com/legal/automated_data_collection_terms)（Effective: 2024-10-07。旧 URL からのリダイレクト先） | "You will not engage in Automated Data Collection **without first obtaining Meta's express written permission**"。続きに "or in any manner that is not explicitly authorized by Meta" | **書面の許可が必要。許可があっても、収集したデータの用途は検索エンジン・URL プレビューなどに限られ、許可を得た後の義務も重い。学生のプロジェクトでは、許可の申請は現実的でない。** dev.meta.ai のモデルページのフッターの「Terms of Service」は https://www.facebook.com/policies_center/ を指す（初版のブラウザでの確認）。Muse Spark 1.3 のページで「利用規約」を開くと、Facebook 利用規約に遷移した（§3-3）。リンクの書き方は違うが、どちらも Facebook の規約ページに行き着くので、dev.meta.ai は対象と見てよい。確認結果は §3-3 |
| OpenAI | [Terms of Use](https://openai.com/policies/row-terms-of-use/)（Effective: 2026-01-01） | "Automatically or programmatically extract data or Output" を禁止。「Services」に "any associated software applications and websites" を含む。同じ箇所に "circumvent any rate limits or restrictions or bypass any protective measures" もある | 自動での抽出を禁止。Internet Archive の保存版（2026-09-29 取得）で原文を照合済み。ボット対策を回避しないという R-1 の判断の裏づけにもなる。実際のページもボット対策で取得できない |
| Mistral AI | [ROW Consumer Terms](https://legal.mistral.ai/terms/row-consumer-terms)（Effective: 2026-09-25） | 対象の "Mistral AI Products" を "Vibe and the other websites, products, software, services, and technologies we offer" と定義し、"(f) Use any method to **extract any content from the Mistral AI Products** other than as permitted through the Mistral AI Products" | 自社サイト・自社サービスからの抽出を禁止。**Hugging Face 上のモデルカードはこの規約の対象外**という整理（§4）を DeepSeek・Qwen と同じように当てはめると、不可の理由は技術的な壁（主力モデルの数値が画像のみ）だけになる。Ministral 3 系は HF の README に Markdown の表がある（R-1 のレビューで確認） |
| DeepSeek | [DeepSeek 利用規約](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html)（日本語版が返った） | 「本サービスのコンテンツをキャプチャ、コピー（**ロボット、スパイダー、その他自動セットアップの使用**、ミラーの設定を含む……）すること」を禁止。「本サービス」には「ウェブサイト」を含む | **自社サイトからの自動取得は禁止。** 取得元を Hugging Face にすれば、この規約の対象外（と整理する。§4） |
| Qwen | [Service Agreement](https://qwen.ai/termsservice)（契約の相手は Nth Power Global Tech Singapore Pte. Ltd.） | §II："extracting data or outputting content **through automated or programmatic means**" と "using bots to access the Service" を禁止。§IV："no person may use or transfer any content in Qwen Products and related Services without authorization, including ... monitoring, copying, ... or downloading such content **through any bots, spiders, or other programs or devices**" | **自社サイトからの自動取得は禁止。** 取得元を Hugging Face にすれば対象外。「Service」は個人向けの製品が中心で、取得元の qwen.ai のブログが含まれるかは規約から読み取れないが、HF 経由なら判定は変わらない。「qwen.ai からは取得しない」ルールの根拠になる。確認結果は §3-3 |

### 3-2. 共通して言えること

- 多くの規約は、**AI サービス（チャットなど）の利用者向け**に書かれている。「サイトを見るだけの人」にも適用されるかは規約ごとにはっきりしない。ただし Anthropic・xAI は、文面上「アクセスしただけで規約に同意したとみなす」書き方になっている（§4 の質問 B）。この調査では、安全側に倒して「適用される」前提で判定した
- Anthropic と xAI の規約は、どちらも「サービス」にウェブサイトを含み、スクリプトでのアクセスを禁止する同じ構造で、同じ問い（§4）が当てはまる
- 取得するのはベンチマークの**数値**（事実のデータ）と出典情報だけで、記事の本文はリポジトリに含めず公開もしない（企画書 §6-3。取得したページは実行者の手元には保存する）。ただし、規約上「取得すること自体」が禁止されていれば、取得後に何を使うかにかかわらず規約違反になりうる

### 3-3. ブラウザでの確認記録（2026-09-30）

§3-1 の表から、ブラウザで原文を確認した結果を移した。xAI・Hugging Face・DeepSeek・Mistral は日本語表示、Qwen の規約、Qwen の README、Meta は英語の原文。

**Hugging Face（規約の全文。発効日 2022-09-15）**

- 自動取得（スクレイピング・クローラー・ロボット・ボットなど）を禁止する条項は見当たらなかった
- 質問 A を裏づける条項が 2 つある
  - 「コンテンツ」の節に、"コンテンツに合理的かつ慣習的なライセンス（オープンソースライセンスなど）の通知が含まれている場合、当該コンテンツは、その後のアクセス、配布、または使用においても、当該ライセンスの条件に従う" とある
  - 同じ節に、リポジトリを公開にすると "各ユーザーに対し、当社のサービスおよび機能を通じて、お客様のコンテンツを使用、表示、公開、複製、配布、および派生作品を作成するための、永続的、取消不能、全世界的、ロイヤリティフリー、非独占的なライセンスを付与する" とある（公開モデルカードは、HF を通じて読む・複製することが許されている）
- モデルカードの License（自動取得に触れる文言はどれもなかった。追加の条件は、Mistral（Small 4）に「第三者の権利を侵害……使用してはなりません」の一文があるだけで、そのほかの License は一般的な条件のみ）

| モデル | License | 確認した場所 |
| --- | --- | --- |
| Mistral-Small-4-119B-2603 | Apache 2.0。末尾に "このモデルを、知的財産権を含む第三者の権利を侵害、不正使用、または違反するような方法で使用してはなりません" とある | README 本文 |
| DeepSeek-V4-Pro | MIT（「このリポジトリとモデルの重みは、MIT ライセンスの下でライセンスされています」） | README 末尾の「ライセンス」の節。ページ上部にバッジもある |
| Qwen3.8-27B | Apache 2.0（`license: apache-2.0`） | README 先頭の YAML 情報（`/raw/main/README.md`）。README 本文に License の節はない |

- **Ministral 3 系の License**：スクリプトで取るのは Ministral 3 系なので、根拠は取得するリポジトリのものにする必要がある。レビュアーが Ministral-3-14B-Instruct-2512 の README で "This model is licensed under the Apache 2.0 License" を確認している（私たち自身では未確認）。**取得を始める前に、対象のリポジトリで確認する**
- 未確認：補足規約（Supplemental Terms、PDF）、Content Policy の本文、各リポジトリの LICENSE ファイル

**xAI（規約本体と AUP）**

- **規約本体**（Terms of Service - Consumer、最終更新 2026-09-11）
  - 「本サービス」は「Grok、Grokipedia、および SpaceXAI の個人向けその他のサービス（関連アプリケーション、機能、ツール、ソフトウェア、ウェブサイトを含む）」
  - 「本サービスにアクセスして使用することにより、……許容使用ポリシーを含むその他の適用される規約およびポリシーを承認し、同意したものとみなされる」（AUP の取り込みを確認）
  - 冒頭に「お客様が本規約に同意した場合、またはお客様がプラットフォームにアクセス、操作、および/または使用した場合に」契約が成立するとあり、§4 には「利用可能な場合は、ログインせずに当社のサービスにアクセスできます」とある（アカウントなしのアクセスも規約の対象と読める）
  - **初版で引用した "any robot, spider, scraper ..." に当たる文は、現行の規約本文にない**（保存版でのレビューと一致）。前のバージョンは https://x.ai/legal/terms-of-service/previous-2026-09-01 にあり、そちらに含まれていたかは未確認
- **AUP**（発効 2026-08-14。会社名は「SpaceXAI」）
  - 「当社のサービスをご利用になるすべての方に適用」（"applies to anyone using our Service" に当たる）
  - 禁止事項に「ボット、スクリプト、またはその他の方法による、許可されていない自動化された手段または非人間的な手段によるサービスへのアクセス」
  - ほかにレート制限や保護措置の回避の禁止、「入力または出力のスクレイピング、収集」の禁止もある（後者はモデルの入出力の話で、公開ページの取得を直接指すかは不明）
  - 「サービス」などの定義は規約（消費者向け・企業向け）に委ねている
- **残る論点**：規約の「本サービス」は Grok・Grokipedia など製品を中心に書かれ、§1 は x.ai を会社の紹介ページとして示している。**取得元の x.ai の発表記事のページが「本サービス」（ウェブサイト）に含まれるかは、規約から読み取れない**

**Qwen（Service Agreement）**

- 「Service」は "Qwen, Qwenstudio, and other Services provided by Qwen for individual users, including related applications and websites"
- 初版で引用した 2 つの文言は、§II「What you may not do」に**原文どおりある**（"using bots to access the Service"、"Extracting data or outputting content through automated or programmatic means"）
- 初版になかった文言：§II に "Circumvent any rate limit or access restriction, or any safeguards or security mitigations"、§IV に bots・spiders などによるコンテンツの監視・複製・ダウンロードの禁止（コンテンツ自体の取得を禁止）
- "Use Policy" を規約の一部として順守するよう求めており（§II・§XIII）、使うことで同意したものとみなす
- **残る論点**：「Service」は個人向けの製品が中心で、qwen.ai のブログが含まれるかは規約から読み取れない（§XIII に、規約を qwen.com と qwen.ai に掲載するとある）
- 未確認：規約の日付（貼り付けに最終更新日・発効日がなかった）、Use Policy の本文

**Meta（自動データ収集規約。Effective 2024-10-07、契約の相手は Meta Platforms, Inc.）**

- §3：規約に同意するだけでは許可にならず、許可は Meta の正式な承認手続きで**別に取る**必要がある
- 「Automated Data Collection」は、web scrapers・bots・spiders・crawlers などでウェブページからデータを取得すること（§8）
- **許可があっても、収集したデータの用途は「検索エンジンの結果の提供」か「Meta の URL のプレビュー表示」、または別途の書面の許可を得た用途に限られる**（§4）。ベンチマークの比較表への利用は、このどちらにも当たらない
- 許可を得る場合の義務が重い（プライバシー・セキュリティのプログラムの整備、Meta による監査・レビュー、補償など。§4〜§6）
- robots.txt の順守、自社を識別できる IP アドレス・User-Agent の使用も求められる（§4）
- **残る論点**：対象の「Meta Company Products」は Facebook 利用規約の定義に委ねられており（本文には定義がない）、dev.meta.ai が含まれるかは、下の Facebook 利用規約の確認結果を参照。なお、初版の「Facebook・Instagram 以外も含むと書かれている」は、この規約の本文にはなく、Facebook 利用規約側の定義の話
- **Facebook 利用規約（2025-01-01 適用。貼り付けた日本語版）の確認結果**
  - 適用範囲：冒頭に「Facebook、Messenger、弊社が提供するその他の製品、**ウェブサイト**、機能、アプリ、サービス、技術、およびソフトウェア」とあり、文面上は dev.meta.ai も含まれうる。さらに、dev.meta.ai の Muse Spark 1.3 のページで「利用規約」のリンクを開くと、この Facebook 利用規約に遷移した（ブラウザでの確認。ページ側に別の規約はない）。**dev.meta.ai は、この規約の対象と見てよい**。「Meta 社製品」の定義ページは、リンクが貼り付けに残っておらず読めていない
  - §3.2-3：「弊社から事前の許可を得ることなく、自動化手段を用いて弊社製品のデータにアクセスしたり、データを取得したりすること」を禁止。Facebook アカウントにログインしているかどうかは問わない。ログインなしでも適用される書き方で、Anthropic・xAI と同じ論点になる。ただし Meta は質問 B の対象に加えない（理由は §4）
  - §3.2-7：アクセスを制御・制限するための技術的措置の回避を禁止
  - 判定は「要相談（不可寄り）」のまま。自動データ収集規約に加えて、利用規約本体にも自動取得の禁止がある。手入力なら Q-1 の答えで決まる点も変わらない

## 4. 判定の根拠と、先生に相談したいこと

| 企業 | 判定 | 根拠 | 相談したいこと |
| --- | --- | --- | --- |
| Google | 取得可 | 規約が robots.txt 準拠を条件にしており、robots.txt は `Allow: /` | — |
| DeepSeek | 取得可（確認待ち） | Hugging Face は規約・robots.txt ともに自動取得を制限していない | 質問 A |
| Qwen | 取得可（確認待ち） | 同上 | 質問 A |
| Mistral AI | Ministral 3 系のみ取得可（確認待ち） | 同上。Mistral の規約の対象は自社の Products で、HF 上のモデルカードは対象外 | 質問 A。主力モデルは数値が画像のみなので、手入力（Q-1）が必要 |
| Anthropic | 要相談 | 規約が「ウェブサイトを含むサービス」へのスクリプトでのアクセスを禁止 | 質問 B |
| xAI | 要相談 | AUP が「ボット・スクリプトでのアクセス」を禁止。文言・構造が Anthropic と同じ | 質問 B |
| Meta | 要相談（不可寄り） | 自動データ収集には書面の許可が必要。許可があっても用途が限られ（検索エンジン・URL プレビュー）、義務も重い（§3-1） | 許可の申請は現実的でないため、独立した質問にはせず **Q-1 にまとめる**（手入力が認められれば手入力、認められなければ対象外）。**質問 B の対象には加えない**：自動データ収集規約は書面での明示の許可を求めているので、質問 B の後半（`Allow` を許可とみなせるか）は当てはまらない。前半が「及ばない」となったときは、Facebook 利用規約も同じ理屈になるので、Meta も再検討する |
| OpenAI | 不可 | 規約が自動抽出を禁止＋ボット対策。HF・GitHub にも主力モデルの公式の値がない | 手入力を認めるか（Q-1） |

**質問 A（Hugging Face の整理）**
> DeepSeek・Qwen・Mistral は、自社サイトの規約でボットによる取得を禁止している。ただしモデルカードは Hugging Face 上にもあり、Hugging Face の規約は自動取得を禁止していない（robots.txt も `Allow: /`）。取得元を Hugging Face の README.md に限れば、各社の自社規約の対象外として扱ってよいか。あわせて、各モデルカードの License の条件も確認する

**質問 B（消費者向け規約の適用範囲）**
> 「サービス」にウェブサイトを含む消費者向け規約（Anthropic・xAI）は、文面上、アクセスしただけで規約に同意したとみなす書き方になっている（Anthropic："By accessing our Services, you agree to these Terms."、xAI："when you otherwise access, interact with, and/or use the platform"、"Where available, you may access our Service without logging in"）。アカウントを作らず、同意の操作もしていない閲覧者にも、こうした規約が及ぶ前提で扱うべきか。及ぶ前提なら、robots.txt の `Allow: /` を規約上の「許可」とみなせるか（Anthropic の規約には "explicitly permit"、xAI の AUP には "unauthorized" という言葉がある）。xAI については、あわせて、x.ai の発表記事のページが規約の「本サービス」（Grok・Grokipedia などの製品とその関連ウェブサイト）に含まれるかも確認したい
>
> 後半には、許可とみなせない側の材料もある。robots.txt の標準である RFC 9309 は、冒頭で "These rules are not a form of access authorization." としている（https://www.rfc-editor.org/rfc/rfc9309 §1）。Google が取得可なのは、Google の規約そのものが robots.txt に従うことを条件にしているからで、Anthropic・xAI の規約は、§3-1 の引用の範囲では robots.txt に触れていない。`User-agent: *` / `Allow: /` は「制限していない」という既定の状態なので、Anthropic の "explicitly permit" にあたるとは言いにくい

> **手入力（Q-1）について**：メンバーがブラウザで見て値を書き写すのはスクレイピングではないので、上の規約の多くには当たらない。Q-1 で手入力が認められれば、Anthropic・xAI・Meta・OpenAI・Mistral の主力モデルも対象に含められる可能性がある。ただし企画書 §6-1 の「Python スクリプトで収集する」という授業の制約との関係も含めて、先生に確認したい。

## 5. 他の調査項目への引き継ぎ

| 引き継ぎ先 | 内容 |
| --- | --- |
| R-3（対象の選定） | 現時点で取得可と判断したのは Google・DeepSeek・Qwen の 3 社。うち DeepSeek・Qwen は質問 A（HF の整理）の確認待ち。質問 B が認められれば Anthropic・xAI が加わり 5 社になる。R-3 は、この答えで場合分けして書く。Mistral の Ministral 3 系は、主力モデルに数えるかを R-3 で判断する（§1） |
| §6-3（スクレイピングの実行ルール） | 「1 ページごとに数秒以上」の間隔を空け、ボット対策などの制限を回避しない。**このルールは Hugging Face にも適用する。** DeepSeek・Qwen・Mistral は **Hugging Face の README.md を `/resolve/` 経由（`huggingface_hub` の `hf_hub_download` など）で取得し、自社サイトからは取得しない**ことを明記する。HF のドキュメント（[rate-limits](https://huggingface.co/docs/hub/rate-limits)）が `/resolve/` をプログラム向けの経路とし、"We strongly recommend using huggingface_hub for all programmatic access to the Hub" と書いているため。README だけを取れば、R-1 §4-1 の第三者の値（Evaluation results）も混ざらない |
| R-1 §4-5（Meta の取得元） | 取得元は dev.meta.ai に固定する（ページは R-1 §4-5。§2） |
| §8 Q-1（先生確認） | Anthropic・xAI・Meta・OpenAI・Mistral（主力モデル）の扱いが、手入力を認めるかどうかで変わる |
| §8 Q-2（公開範囲） | 一般公開する場合、各社の規約との関係をさらに確認する必要がある（今回は「取得」の可否だけを見た） |

## 6. この調査の限界

- 法的な判断ではない。規約の文面を読んだうえでの整理
- xAI の AUP（発効日 2026-08-14）と規約本体（最終更新 2026-09-11）は、ブラウザで現行の文面を確認した（日本語表示。規約本体の主要な文言は、レビューで英語の保存版（2026-09-28）との照合を確認済み。AUP の英語原文との照合は未）。前のバージョン（2026-09-01）に初版の引用があったかは未確認。OpenAI の規約は、403 のため直接は読めず、**Internet Archive の保存版**（2026-09-29 取得）で確認した
- Qwen の規約（Service Agreement）は、ブラウザで本文を確認した（英語の原文）。日付と、規約が取り込む Use Policy の本文は未確認
- Meta の自動データ収集規約（Effective October 7, 2024）は、ブラウザで本文を確認した。Facebook 利用規約（2025-01-01 適用の日本語版）は貼り付けで確認した。dev.meta.ai のページの「利用規約」リンクがこの規約に遷移することも確認した。最新版かどうかと、「Meta 社製品」の定義ページは未確認
- 各リポジトリの License は、Qwen が README 先頭の YAML 情報で Apache 2.0、DeepSeek が README 本文で MIT、Mistral（Small 4）が README 本文で Apache 2.0 と確認した（LICENSE ファイルは未確認）。スクリプトで取る Ministral 3 系の License は、レビューでの確認のみで、取得前に対象のリポジトリで確認する（§3-3）
- Hugging Face の規約は、HTML 本文の語の検索（「scrape / crawl / robot / bot / spider / harvest / extract / mining / rate / API」など）と、ブラウザでの全文確認（日本語表示）の両方で、自動取得を禁止する条項が見当たらないことを確認した。補足規約（Supplemental Terms）と Content Policy の本文は未確認
- 規約は予告なく改定される（Mistral・OpenAI・xAI は直近数か月〜数週間以内に改定されている）。実際に取得を始める前に再確認する
- 各社サイトの URL・ページ構成は R-1 の調査時点のもの。R-1 と合わせて、取得を始める前に再確認する

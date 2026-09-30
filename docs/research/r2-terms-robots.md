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
| Anthropic | anthropic.com | 要相談（スクリプトでのアクセスを禁止。§3-1、§4） | 取れる | **要相談** |
| xAI | x.ai | 要相談（AUP がスクリプトでのアクセスを禁止。§3-1、§4） | 取れる | **要相談** |
| Meta | dev.meta.ai | 要相談（不可寄り。Meta の規約は自動データ収集に書面の許可を求める） | 取れる | **要相談（不可寄り）** |
| OpenAI | openai.com | 不可（規約が自動抽出を禁止） | ボット対策で取れない。HF・GitHub にも主力モデルの公式の値がない | **不可** |

- **現時点で取得可と判断したのは Google・DeepSeek・Qwen の 3 社。** うち DeepSeek・Qwen は Hugging Face の整理について先生の確認待ちなので、**先生の確認なしで取得できるのは Google だけ**。成功の定義「5 社以上」に届かせるには、下の 2 点の確認が要る
  1. Hugging Face の整理（§4）が認められる → DeepSeek・Qwen（と Mistral の Ministral 3 系）が確定
  2. 「消費者向け規約は公開ページの低頻度な取得にも適用されるか」（§4 の質問）が「適用されない」または「robots.txt の `Allow: /` を許可とみなせる」となる → Anthropic・xAI が加わり、Google・DeepSeek・Qwen・Anthropic・xAI の 5 社に届く
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
| developer.meta.com | なし（同上） | 同じ注意書きあり。ただし Facebook 上のデータについての文言で、取得先の dev.meta.ai には当てはまらない。R-1 の URL は dev.meta.ai へ 302・308 でリダイレクトされる |
| dev.meta.ai | なし（同上） | **Meta の取得元はここ（`https://dev.meta.ai/models/muse-spark-1-1`）に固定する。** 注意書きはなし |
| x.ai | なし（`/tools/` のみ `Disallow`） | `Content-Signal: ai-train=yes, search=yes, ai-input=yes`（AI 学習・検索での利用を許可する宣言） |
| mistral.ai | なし（`Allow: /`） | |
| huggingface.co | なし（`User-agent: *` / `Allow: /` のみ。`/api/`・`/raw/`・`/resolve/` への `Disallow` もない） | |
| api-docs.deepseek.com | robots.txt が存在しない（HTML が返る） | |
| qwen.ai | robots.txt が存在しない（HTML が返る） | |

## 3. 利用規約

### 3-1. 企業ごとの該当条項

| 企業 | 規約 | 該当条項（原文） | 読み取れること |
| --- | --- | --- | --- |
| Google | [Google 利用規約](https://policies.google.com/terms)「Don't abuse our services」 | "using automated means to access content from any of our services **in violation of the machine-readable instructions on our web pages (for example, robots.txt files ...)**" | **robots.txt に従う限り、自動アクセスは禁止されていない。** deepmind.google は `Allow: /` なので問題なし |
| Hugging Face | [Terms of Service](https://huggingface.co/terms-of-service)（Effective Date: 2022-09-15）、[Content Policy](https://huggingface.co/content-policy)（規約に組み込まれた方針） | 規約：scrape / crawl / robot / bot / spider / harvest / extract / mining / rate / API のいずれについても、自動取得を禁止する条項はない。ただし "all of our policies available on our Website" の順守を求め、"Any Content you download, access or use from us or another User, is at your own risk and **subject to these Terms and/or the terms accompanying such Content**" とある。Content Policy には濫用の例として "Using tools like Cloudflare Tunnel, TOR, proxies, VNC, Chrome Remote Server, etc., to bypass restrictions" と "excessive bulk activity" がある | 自動取得を禁止する条項はない。**低頻度で読むだけなら当たらないが、「間隔を空け、制限を回避しない」ことを守る。§6-3 のルールを HF にも適用する。** **規約の全文は 2026-09-30 にブラウザで確認済み**（日本語表示。発効日 2022-09-15）。自動取得（スクレイピング・クローラー・ロボット・ボットなど）を禁止する条項は見当たらなかった。質問Aを裏づける条項が 2 つある：①「コンテンツ」の節に、"コンテンツに合理的かつ慣習的なライセンス（オープンソースライセンスなど）の通知が含まれている場合、当該コンテンツは、その後のアクセス、配布、または使用においても、当該ライセンスの条件に従う" とある。②同じ節に、リポジトリを公開にすると "各ユーザーに対し、当社のサービスおよび機能を通じて、お客様のコンテンツを使用、表示、公開、複製、配布、および派生作品を作成するための、永続的、取消不能、全世界的、ロイヤリティフリー、非独占的なライセンスを付与する" とある（公開モデルカードは、HF を通じて読む・複製することが許されている）。モデルカードにはリポジトリごとの条件（License 欄）が付くため、DeepSeek・Qwen・Mistral の License を確認する必要がある（**未確認**）。規約が参照する補足規約（Supplemental Terms、PDF）と Content Policy の本文も未確認 |
| xAI | [Terms of Service - Consumer](https://x.ai/legal/terms-of-service)（Last Updated: 2026-09-11）と、規約が取り込む [Acceptable Use Policy](https://x.ai/legal/acceptable-use-policy)（Effective: 2026-08-14） | 規約：「Service」に "associated applications, features, tools, software and websites" を含み、"By accessing and using our Service, you acknowledge and agree to these Terms and any other applicable terms and policies, including our Acceptable Use Policy." とある。AUP："applies to anyone using our Service"。禁止事項に "**Accessing the Services through unauthorized automated or non-human means, whether through a bot, script, or otherwise**" | **スクリプトでのアクセスを禁止しており、Anthropic の規約とほぼ同じ文言・構造。** 判定は Anthropic と同じ「要相談」。初版で引用した "any robot, spider, scraper ... than a human can reasonably produce ..." は、Internet Archive の保存版（2026-09-28 取得）の規約本文に見当たらず、旧版か別の文書のものだった可能性がある。したがって「人間と同程度の頻度なら禁止に当たらない」という読み方は根拠にしない。**AUP は 2026-09-30 にブラウザで確認済み**：発効日 2026-08-14、「当社のサービスをご利用になるすべての方に適用」（"applies to anyone using our Service" に当たる）、禁止事項に「ボット、スクリプト、またはその他の方法による、許可されていない自動化された手段または非人間的な手段によるサービスへのアクセス」がある。ほかにレート制限や保護措置の回避の禁止、「入力または出力のスクレイピング、収集」の禁止もある（後者はモデルの入出力の話で、公開ページの取得を直接指すかは不明）。AUP の会社名は「SpaceXAI」で、「サービス」などの定義は規約（消費者向け・企業向け）に委ねている。確認したのは日本語表示で、英語の原文との照合はしていない。**規約本体も 2026-09-30 にブラウザで確認済み**（日本語表示。最終更新日 2026-09-11、Terms of Service - Consumer）：①「本サービス」は「Grok、Grokipedia、および SpaceXAI の個人向けその他のサービス（関連アプリケーション、機能、ツール、ソフトウェア、ウェブサイトを含む）」、②「本サービスにアクセスして使用することにより、……許容使用ポリシーを含むその他の適用される規約およびポリシーを承認し、同意したものとみなされる」（AUP の取り込みを確認）、③ 冒頭に「お客様が本規約に同意した場合、またはお客様がプラットフォームにアクセス、操作、および/または使用した場合に」契約が成立するとあり、§4 には「利用可能な場合は、ログインせずに当社のサービスにアクセスできます」とある（アカウントなしのアクセスも規約の対象と読める）、④ **初版で引用した "any robot, spider, scraper ..." に当たる文は、現行の規約本文にない**（保存版のレビューと一致。前のバージョンは https://x.ai/legal/terms-of-service/previous-2026-09-01 にあり、そちらに含まれていたかは未確認）。**残る論点**：規約の「本サービス」は Grok・Grokipedia など製品を中心に書かれ、§1 は x.ai を会社の紹介ページとして示している。**取得元の x.ai の発表記事のページが「本サービス」（ウェブサイト）に含まれるかは、規約から読み取れない** |
| Anthropic | [Consumer Terms of Service](https://www.anthropic.com/legal/consumer-terms) §3（Effective: 2025-10-08） | "To **crawl, scrape, or otherwise harvest data** or information from our Services other than as permitted under these Terms."／"**Except when you are accessing our Services via an Anthropic API Key or where we otherwise explicitly permit it, to access the Services through automated or non-human means, whether through a bot, script, or otherwise.**"／"Services" = "Claude.ai, Claude Pro, and other products and services ... along with any associated apps, software, **and websites**" | **ウェブサイトのスクレイピング・スクリプトでのアクセスも禁止対象**と読める。ただしこれは Claude の利用者向けの規約で、アカウントを持たずにサイトを見るだけの人にも適用されるかははっきりしない。"explicitly permit" を robots.txt の `Allow: /` が満たすかも論点 → 要相談 |
| Meta | [Automated Data Collection Terms](https://www.facebook.com/legal/automated_data_collection_terms)（旧 URL からのリダイレクト先） | "You will not engage in Automated Data Collection **without first obtaining Meta's express written permission**" | **2026-09-30 にブラウザで本文を確認済み**（英語の原文。Effective October 7, 2024、契約の相手は Meta Platforms, Inc.）。①上の引用は原文どおりで、続きに "or in any manner that is not explicitly authorized by Meta" がある。②§3：規約に同意するだけでは許可にならず、許可は Meta の正式な承認手続きで**別に取る**必要がある。③「Automated Data Collection」は、web scrapers・bots・spiders・crawlers などでウェブページからデータを取得すること（§8）。④**許可があっても、収集したデータの用途は「検索エンジンの結果の提供」か「Meta の URL のプレビュー表示」、または別途の書面の許可を得た用途に限られる**（§4）。ベンチマークの比較表への利用は、このどちらにも当たらない。⑤許可を得る場合の義務が重い（プライバシー・セキュリティのプログラムの整備、Meta による監査・レビュー、補償など。§4〜§6）。**学生のプロジェクトでは、許可の申請は現実的でない。** ⑥robots.txt の順守、自社を識別できる IP アドレス・User-Agent の使用も求められる（§4）。**残る論点**：対象の「Meta Company Products」は Facebook 利用規約の定義に委ねられており（本文には定義がない）、dev.meta.ai が含まれるかは**未確認**。ただし **dev.meta.ai のモデルページのフッターの「Terms of Service」が https://www.facebook.com/policies_center/ を指している**ので、Meta の規約が適用される前提で考えるのが安全。なお、初版の「Facebook・Instagram 以外も含むと書かれている」は、この規約の本文にはなく、Facebook 利用規約側の定義の話で、未確認 |
| OpenAI | [Terms of Use](https://openai.com/policies/row-terms-of-use/)（Effective: 2026-01-01） | "Automatically or programmatically extract data or Output" を禁止。「Services」に "any associated software applications and websites" を含む。同じ箇所に "circumvent any rate limits or restrictions or bypass any protective measures" もある | 自動での抽出を禁止。Internet Archive の保存版（2026-09-29 取得）で原文を照合済み。ボット対策を回避しないという R-1 の判断の裏づけにもなる。実際のページもボット対策で取得できない |
| Mistral AI | [ROW Consumer Terms](https://legal.mistral.ai/terms/row-consumer-terms)（Effective: 2026-09-25） | 対象の "Mistral AI Products" を "Vibe and the other websites, products, software, services, and technologies we offer" と定義し、"(f) Use any method to **extract any content from the Mistral AI Products** other than as permitted through the Mistral AI Products" | 自社サイト・自社サービスからの抽出を禁止。**Hugging Face 上のモデルカードはこの規約の対象外**という整理（§4）を DeepSeek・Qwen と同じように当てはめると、不可の理由は技術的な壁（主力モデルの数値が画像のみ）だけになる。Ministral 3 系は HF の README に Markdown の表がある（R-1 のレビューで確認） |
| DeepSeek | [DeepSeek 利用規約](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html)（日本語版が返った） | 「本サービスのコンテンツをキャプチャ、コピー（**ロボット、スパイダー、その他自動セットアップの使用**、ミラーの設定を含む……）すること」を禁止。「本サービス」には「ウェブサイト」を含む | **自社サイトからの自動取得は禁止。** 取得元を Hugging Face にすれば、この規約の対象外（と整理する。§4） |
| Qwen | [Terms of Service](https://qwen.ai/termsservice) | "extracting data or outputting content **through automated or programmatic means**" と "using bots to access the Service" を禁止 | **自社サイトからの自動取得は禁止。** 取得元を Hugging Face にすれば対象外。**2026-09-30 にブラウザで本文を確認済み**（qwen.ai は JS 描画で、直接も保存版も取れなかったため）。規約の名前は「Service Agreement」（契約の相手は Nth Power Global Tech Singapore Pte. Ltd.）。①「Service」は "Qwen, Qwenstudio, and other Services provided by Qwen for individual users, including related applications and websites"。② 上の 2 つの文言は、§II「What you may not do」に**原文どおりある**（"using bots to access the Service"、"Extracting data or outputting content through automated or programmatic means"）。③ 初版になかった文言：§II に "Circumvent any rate limit or access restriction, or any safeguards or security mitigations"、§IV に "no person may use or transfer any content in Qwen Products and related Services without authorization, including ... monitoring, copying, ... or downloading such content **through any bots, spiders, or other programs or devices**"（コンテンツ自体の取得を禁止）。④ "Use Policy" を規約の一部として順守するよう求めており（§II・§XIII）、使うことで同意したものとみなす。**Use Policy の本文は未確認**。⑤ 貼り付けには最終更新日・発効日がなく、**規約の日付は未確認**。**残る論点**：「Service」は個人向けの製品が中心で、取得元の qwen.ai のブログが含まれるかは規約から読み取れない（§XIII に、規約を qwen.com と qwen.ai に掲載するとある）。ただし HF 経由なら Qwen 自社の Service ではないので、判定は変わらない。影響するのは「qwen.ai からは取得しない」というルールの根拠で、これで裏づけられた |

### 3-2. 共通して言えること

- 多くの規約は、**AI サービス（チャットなど）の利用者向け**に書かれている。「サイトを見るだけの人」にも適用されるかは規約ごとにはっきりしない。この調査では、安全側に倒して「適用される」前提で判定した
- Anthropic と xAI の規約は、どちらも「サービス」にウェブサイトを含み、スクリプトでのアクセスを禁止する同じ構造で、同じ問い（§4）が当てはまる
- 取得するのはベンチマークの**数値**（事実のデータ）と出典情報だけで、記事の本文は保存・公開しない（企画書 §6-3）。ただし、規約上「取得すること自体」が禁止されていれば、取得後に何を使うかにかかわらず規約違反になりうる

## 4. 判定の根拠と、先生に相談したいこと

| 企業 | 判定 | 根拠 | 相談したいこと |
| --- | --- | --- | --- |
| Google | 取得可 | 規約が robots.txt 準拠を条件にしており、robots.txt は `Allow: /` | — |
| DeepSeek | 取得可（確認待ち） | Hugging Face は規約・robots.txt ともに自動取得を制限していない | 質問 A |
| Qwen | 取得可（確認待ち） | 同上 | 質問 A |
| Mistral AI | Ministral 3 系のみ取得可（確認待ち） | 同上。Mistral の規約の対象は自社の Products で、HF 上のモデルカードは対象外 | 質問 A。主力モデルは数値が画像のみなので、手入力（Q-1）が必要 |
| Anthropic | 要相談 | 規約が「ウェブサイトを含むサービス」へのスクリプトでのアクセスを禁止 | 質問 B |
| xAI | 要相談 | AUP が「ボット・スクリプトでのアクセス」を禁止。文言・構造が Anthropic と同じ | 質問 B |
| Meta | 要相談（不可寄り） | 自動データ収集には書面の許可が必要。許可があっても用途が限られ（検索エンジン・URL プレビュー）、義務も重い（§3-1） | 許可の申請は現実的でないため、対象外にするか、手入力（Q-1）にするか |
| OpenAI | 不可 | 規約が自動抽出を禁止＋ボット対策。HF・GitHub にも主力モデルの公式の値がない | 手入力を認めるか（Q-1） |

**質問 A（Hugging Face の整理）**
> DeepSeek・Qwen・Mistral は、自社サイトの規約でボットによる取得を禁止している。ただしモデルカードは Hugging Face 上にもあり、Hugging Face の規約は自動取得を禁止していない（robots.txt も `Allow: /`）。取得元を Hugging Face の README.md に限れば、各社の自社規約の対象外として扱ってよいか。あわせて、各モデルカードの License の条件も確認する

**質問 B（消費者向け規約の適用範囲）**
> 「サービス」にウェブサイトを含む消費者向け規約は、アカウントを持たずに公開ページを低頻度でスクリプト取得する場合にも適用されるか。適用されるなら、robots.txt の `Allow: /` を規約上の「許可」とみなせるか（Anthropic の規約には "explicitly permit"、xAI の AUP には "unauthorized" という言葉がある）。あわせて、xAI については、x.ai の発表記事のページが規約の「本サービス」（Grok・Grokipedia などの製品とその関連ウェブサイト）に含まれるか、も確認したい

> **手入力（Q-1）について**：メンバーがブラウザで見て値を書き写すのはスクレイピングではないので、上の規約の多くには当たらない。Q-1 で手入力が認められれば、Anthropic・xAI・Meta・OpenAI・Mistral の主力モデルも対象に含められる可能性がある。ただし企画書 §6-1 の「Python スクリプトで収集する」という授業の制約との関係も含めて、先生に確認したい。

## 5. 他の調査項目への引き継ぎ

| 引き継ぎ先 | 内容 |
| --- | --- |
| R-3（対象の選定） | 現時点で取得可と判断したのは Google・DeepSeek・Qwen の 3 社。うち DeepSeek・Qwen は質問 A（HF の整理）の確認待ち。質問 B が認められれば Anthropic・xAI が加わり 5 社になる。R-3 は、この答えで場合分けして書く |
| §6-3（スクレイピングの実行ルール） | 「1 ページごとに数秒以上」の間隔を空け、ボット対策などの制限を回避しない。**このルールは Hugging Face にも適用する。** DeepSeek・Qwen・Mistral は **Hugging Face の README.md を `/resolve/` 経由（`huggingface_hub` の `hf_hub_download` など）で取得し、自社サイトからは取得しない**ことを明記する。HF のドキュメント（[rate-limits](https://huggingface.co/docs/hub/rate-limits)）が `/resolve/` をプログラム向けの経路とし、"We strongly recommend using huggingface_hub for all programmatic access to the Hub" と書いているため。README だけを取れば、R-1 §4-1 の第三者の値（Evaluation results）も混ざらない |
| R-1 §4-5（Meta の取得元） | 取得元は `https://dev.meta.ai/models/muse-spark-1-1` に固定する（§2） |
| §8 Q-1（先生確認） | Anthropic・xAI・Meta・OpenAI・Mistral（主力モデル）の扱いが、手入力を認めるかどうかで変わる |
| §8 Q-2（公開範囲） | 一般公開する場合、各社の規約との関係をさらに確認する必要がある（今回は「取得」の可否だけを見た） |

## 6. この調査の限界

- 法的な判断ではない。規約の文面を読んだうえでの整理
- xAI の AUP（発効日 2026-08-14）と規約本体（最終更新 2026-09-11）は、ブラウザで現行の文面を確認した（日本語表示。英語の原文との照合は未）。前のバージョン（2026-09-01）に初版の引用があったかは未確認。OpenAI の規約は、403 のため直接は読めず、**Internet Archive の保存版**（2026-09-29 取得）で確認した
- Qwen の規約（Service Agreement）は、ブラウザで本文を確認した（英語の原文）。日付と、規約が取り込む Use Policy の本文は未確認
- Meta の自動データ収集規約（Effective October 7, 2024）は、ブラウザで本文を確認した。「Meta Company Products」の定義（Facebook 利用規約側）に dev.meta.ai が含まれるかは未確認
- DeepSeek・Qwen・Mistral の各リポジトリの License（モデルカードの License 欄）は未確認
- Hugging Face の規約は、HTML 本文の語の検索（「scrape / crawl / robot / bot / spider / harvest / extract / mining / rate / API」など）と、ブラウザでの全文確認（日本語表示）の両方で、自動取得を禁止する条項が見当たらないことを確認した。補足規約（Supplemental Terms）と Content Policy の本文は未確認
- 規約は予告なく改定される（Mistral・OpenAI・xAI は直近数か月〜数週間以内に改定されている）。実際に取得を始める前に再確認する
- 各社サイトの URL・ページ構成は R-1 の調査時点のもの。R-1 と合わせて、取得を始める前に再確認する

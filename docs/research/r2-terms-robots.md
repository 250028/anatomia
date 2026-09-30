# R-2 各社サイトの利用規約・robots.txt の確認

> **目的**：スクレイピングが許容されているかを確認し、禁止されているサイトを対象から外す（企画書 §5 R-2、Linear 250-58）
> **調査日**：2026-09-30
> **対象**：R-1（[r1-benchmark-formats.md](r1-benchmark-formats.md)）で取得元の候補になったドメインと、困難と判定した 2 社のドメイン
> **注意**：これは法的な判断ではない。規約の文面を読んだうえでの整理であり、「要相談」は先生に確認する

---

## 1. 結論

| 判定 | 企業 | 取得元 |
| --- | --- | --- |
| **取得可** | Google | deepmind.google（モデルカード） |
| **取得可** | DeepSeek | huggingface.co（モデルカード） |
| **取得可** | Qwen | huggingface.co（モデルカード） |
| **取得可（条件つき）** | xAI | x.ai（発表記事）。人間の閲覧と同程度のアクセス頻度に限る |
| **要相談** | Anthropic | anthropic.com。規約が「ウェブサイトを含むサービス」のスクレイピングを禁止している |
| **要相談（不可寄り）** | Meta | developer.meta.com。Meta の自動データ収集規約が、書面の許可を求めている |
| **不可** | OpenAI | 規約が自動取得を禁止し、さらにボット対策で実際に取得できない |
| **不可** | Mistral AI | 規約がコンテンツの抽出を禁止し、R-1 でも数値は画像のみ |

- **確実に取得できるのは 4 社**（Google、DeepSeek、Qwen、xAI）。成功の定義「5 社以上」に届かせるには、**Anthropic か Meta について先生の判断が必要**
- **Hugging Face を経由すると、DeepSeek と Qwen は自社サイトの規約に触れずに取得できる。** 両社の自社サイトはボットによる取得を禁止しているが、モデルカードは Hugging Face 上にあり、Hugging Face の規約とrobots.txt はどちらも取得を制限していない
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
| developer.meta.com | なし（同上） | 同じ注意書きあり |
| dev.meta.ai | なし（同上） | developer.meta.com のリダイレクト先。注意書きはなし |
| x.ai | なし（`/tools/` のみ `Disallow`） | `Content-Signal: ai-train=yes, search=yes, ai-input=yes`（AI 学習・検索での利用を許可する宣言） |
| mistral.ai | なし（`Allow: /`） | |
| huggingface.co | なし（`Allow: /`） | |
| api-docs.deepseek.com | robots.txt が存在しない（HTML が返る） | |
| qwen.ai | robots.txt が存在しない（HTML が返る） | |

## 3. 利用規約

### 3-1. 企業ごとの該当条項

| 企業 | 規約 | 該当条項（原文） | 読み取れること |
| --- | --- | --- | --- |
| Google | [Google 利用規約](https://policies.google.com/terms)「Don't abuse our services」 | "using automated means to access content from any of our services **in violation of the machine-readable instructions on our web pages (for example, robots.txt files ...)**" | **robots.txt に従う限り、自動アクセスは禁止されていない。** deepmind.google は `Allow: /` なので問題なし |
| Hugging Face | [Terms of Service](https://huggingface.co/terms-of-service) | 該当条項なし（本文約 3 万字を確認。scrape / crawl / automated / robot のいずれも出てこない） | 自動取得を禁止する条項はない。robots.txt も `Allow: /` |
| xAI | [Terms of Service - Consumer](https://x.ai/legal/terms-of-service) | "any robot, spider, scraper ... or any other automated means to access the Service **in a manner that sends more request messages to the servers running the Service than a human can reasonably produce** in the same period of time by using a conventional on-line web browser" | 禁止されているのは「人間より多いリクエスト」。**数秒間隔で数ページを取得する程度なら禁止に当たらない**と読める。※規約ページは 403 で直接読めず、検索結果の抜粋で確認した。原文の再確認が必要 |
| Anthropic | [Consumer Terms of Service](https://www.anthropic.com/legal/consumer-terms) §3 | "To **crawl, scrape, or otherwise harvest data** or information from our Services other than as permitted under these Terms."／"Services" = "Claude.ai, Claude Pro, and other products and services ... along with any associated apps, software, **and websites**" | **ウェブサイトのスクレイピングも禁止対象**と読める。ただしこれは Claude の利用者向けの規約で、アカウントを持たずにサイトを見るだけの人にも適用されるかははっきりしない → 要相談 |
| Meta | [Automated Data Collection Terms](https://www.facebook.com/apps/site_scraping_tos_terms.php) | "You will not engage in Automated Data Collection **without first obtaining Meta's express written permission**" | **書面の許可が必要。** 対象は「Meta Company Products」で、Facebook・Instagram 以外も含むと書かれている。developer.meta.com が含まれるかは明記がないが、robots.txt にも同じ注意書きがあるので、含まれる前提で考えるのが安全 |
| OpenAI | [Terms of Use](https://openai.com/policies/row-terms-of-use/) | "Automatically or programmatically extract data or Output" を禁止 | 自動での抽出を禁止。※規約ページが 403 のため、検索結果の抜粋で確認した。R-1 のとおり、実際のページもボット対策で取得できない |
| Mistral AI | [ROW Consumer Terms](https://legal.mistral.ai/terms/row-consumer-terms) | "(f) Use any method to **extract any content from the Mistral AI Products** other than as permitted through the Mistral AI Products" | コンテンツの抽出を禁止。R-1 でも数値は画像のみで、そもそも取得できない |
| DeepSeek | [DeepSeek 利用規約](https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html)（日本語版が返った） | 「本サービスのコンテンツをキャプチャ、コピー（**ロボット、スパイダー、その他自動セットアップの使用**、ミラーの設定を含む……）すること」を禁止。「本サービス」には「ウェブサイト」を含む | **自社サイトからの自動取得は禁止。** 取得元を Hugging Face にすれば、この規約の対象外 |
| Qwen | [Terms of Service](https://qwen.ai/termsservice) | "extracting data or outputting content **through automated or programmatic means**" と "using bots to access the Service" を禁止 | **自社サイトからの自動取得は禁止。** 取得元を Hugging Face にすれば対象外。※qwen.ai は JS 描画のため、検索結果の抜粋で確認した |

### 3-2. 共通して言えること

- 多くの規約は、**AI サービス（チャットなど）の利用者向け**に書かれている。「サイトを見るだけの人」にも適用されるかは規約ごとにはっきりしない。この調査では、安全側に倒して「適用される」前提で判定した
- 取得するのはベンチマークの**数値**（事実のデータ）と出典情報だけで、記事の本文は保存・公開しない（企画書 §6-3）。ただし、規約上「取得すること自体」が禁止されていれば、取得後に何を使うかにかかわらず規約違反になりうる

## 4. 判定の根拠と、先生に相談したいこと

| 企業 | 判定 | 根拠 | 相談したいこと |
| --- | --- | --- | --- |
| Google | 取得可 | 規約が robots.txt 準拠を条件にしており、robots.txt は `Allow: /` | — |
| DeepSeek | 取得可 | Hugging Face は規約・robots.txt ともに制限なし | Hugging Face 経由なら自社規約の対象外、という整理でよいか |
| Qwen | 取得可 | 同上 | 同上 |
| xAI | 取得可（条件つき） | 規約が禁止するのは「人間より多いリクエスト」 | 規約の原文を確認できていない。原文を確認したうえでこの読み方でよいか |
| Anthropic | 要相談 | 規約が「ウェブサイトを含むサービス」のスクレイピングを禁止 | 利用者向けの規約が、サイトを見るだけの人にも適用されるか。手入力なら問題ないか（Q-1 とも関係） |
| Meta | 要相談（不可寄り） | 自動データ収集には書面の許可が必要 | 許可を申請するべきか、対象外にするか |
| OpenAI | 不可 | 規約が自動抽出を禁止＋ボット対策 | 手入力を認めるか（Q-1） |
| Mistral AI | 不可 | 規約がコンテンツ抽出を禁止＋数値が画像のみ | 手入力を認めるか（Q-1） |

> **手入力（Q-1）について**：メンバーがブラウザで見て値を書き写すのはスクレイピングではないので、上の規約の多くには当たらない。Q-1 で手入力が認められれば、Anthropic・Meta・OpenAI・Mistral も対象に含められる可能性がある。ただし企画書 §6-1 の「Python スクリプトで収集する」という授業の制約との関係も含めて、先生に確認したい。

## 5. 他の調査項目への引き継ぎ

| 引き継ぎ先 | 内容 |
| --- | --- |
| R-3（対象の選定） | 確実に取得できるのは 4 社（Google、DeepSeek、Qwen、xAI）。5 社以上にするには、Anthropic・Meta についての先生の判断か、Q-1（手入力）が必要 |
| §6-3（スクレイピングの実行ルール） | xAI の規約に合わせて「人間の閲覧と同程度の頻度」を守る。企画書の「1 ページごとに数秒以上」で満たせる見込み。DeepSeek・Qwen は **Hugging Face のページだけから取得し、自社サイトからは取得しない**ことをルールに明記する |
| §8 Q-1（先生確認） | Anthropic・Meta・OpenAI・Mistral の扱いが、手入力を認めるかどうかで変わる |
| §8 Q-2（公開範囲） | 一般公開する場合、各社の規約との関係をさらに確認する必要がある（今回は「取得」の可否だけを見た） |

## 6. この調査の限界

- 法的な判断ではない。規約の文面を読んだうえでの整理
- xAI・OpenAI・Qwen の規約ページは、ボット対策や JS 描画のため直接は読めず、**検索結果の抜粋**で確認した。原文をブラウザで確認する必要がある
- Hugging Face の規約は、2026-09-30 時点の HTML 本文から「scrape / crawl / automated / robot」などの語を検索して確認した。言い回しの違う条項を見落としている可能性はある
- 規約は予告なく改定される。実際に取得を始める前に再確認する

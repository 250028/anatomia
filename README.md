# Anatomia

AIモデル分析サービス

各社が公式に公表した AI モデルのベンチマークスコアを集め、「どのモデルが、どの領域で強いか・弱いか」を一覧・比較できるアプリケーション（第1段階）。範囲は企画書の §2-3 が正。

- 第2段階【案】：価格（API 料金）の収集と、コストパフォーマンスの表示。定義を調べてから着手する（企画書 §2-3・§5 の R-6）
- 将来：用途に応じた最適なモデルのレコメンド機能（企画書 §2-3）

## ドキュメント

| 知りたいこと | 見るファイル |
| --- | --- |
| 何を、誰のために、どう作るのか（企画書） | [`docs/proposal.md`](docs/proposal.md) |
| 開発環境の作り方（セットアップ手順） | [`docs/setup.md`](docs/setup.md) |
| 調査の結果（一覧は企画書 §5） | [`docs/research/`](docs/research/) |
| AI エージェント（Claude Code・Codex など）に守らせるルール | [`AGENTS.md`](AGENTS.md) |

## ディレクトリ

| 場所 | 入っているもの（正とする文書） |
| --- | --- |
| [`scraper/`](scraper/) | 取得スクリプトと、正式データの形への変換（企画書 §6-1・§6-3・§3-3） |
| [`tests/`](tests/) | テスト（実行のしかたは [`docs/setup.md`](docs/setup.md)） |
| [`data/manual/`](data/manual/) | 手入力の値の入れ物（企画書 §3-3） |
| [`requirements.txt`](requirements.txt) | Python のライブラリの一覧 |

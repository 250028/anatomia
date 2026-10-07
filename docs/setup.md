# 開発環境のセットアップ(案)

> **位置づけ**：メンバーが手元で開発環境を作るための手順。企画書 §6-2（開発環境【案】）の「Python 3（バージョンはチームで固定）」を具体にしたもの\
> **確度**：**【案】**。Python のバージョンとライブラリは、チームで確認してから確定する（ライブラリは R-9 で確定）。確定したら、この文書と `requirements.txt` を合わせる\
> **動作確認**：手順 4・5 の `requirements.txt` とテスト（`tests/`）は #9 に入っていて、main にはまだない。#9 のブランチ（`3c94fc8`）で、Python 3.12.3（Ubuntu 24.04）の venv に `pip install -r requirements.txt` を入れ、`python -m unittest discover tests` が 22 件 OK になることまで確認した。Docker は、Docker Desktop（WSL integration）で `docker run --rm hello-world` が通ることまで確認した（収集スクリプトのコンテナ実行は未確認）。**main での確認は、#9 のマージ後**\
> **更新のしかた**：上書き（最新が正）

## 1. 入れるもの

| 道具 | 版 | 必須か | 用途 |
| --- | --- | --- | --- |
| Python | **3.12 系(案)** | 必須 | 収集スクリプトの実行 |
| Git | 最新 | 必須 | リポジトリの取得・PR |
| GitHub CLI(`gh`) | 最新 | 任意 | ターミナルから GitHub にログイン・PR 操作 |
| requests | 最新 | 必須 | ページの取得 |
| beautifulsoup4、lxml | 最新 | 必須(案) | HTML の解析 |
| Playwright、pdfplumber | 最新 | 必要になった人だけ | JavaScript で描画されるページ、PDF の読み取り |
| Docker | 最新 | 任意(使う予定) | 収集スクリプトを、全員が同じ Python の環境で動かす |
| Claude Code | 最新 | 任意 | AI によるコード作成の補助 |

**Python を 3.12 にする案の理由**:

- Ubuntu 24.04(WSL の最新版)に標準で入っていて、追加の手順が要らない。
- 新しすぎると、ライブラリの対応が遅れることがある。
- 3.12 で動くコードは、それ以降の版でも動く。逆は成り立たない(3.14 で書いたコードが 3.12 で動かないことがある)。

## 2. 手順(Linux / WSL の Ubuntu 24.04)

```bash
# 1. 道具を入れる
sudo apt update && sudo apt install -y git python3-venv python3-pip

# 2. リポジトリを取得する
mkdir -p ~/workspace && cd ~/workspace
git clone https://github.com/250028/anatomia.git
cd anatomia

# 3. 仮想環境を作って有効にする(プロジェクトごとの専用の Python 環境)
python3 -m venv .venv
source .venv/bin/activate

# 4. ライブラリを入れる
pip install -U pip
pip install -r requirements.txt

# 5. 動作確認(テスト)
python -m unittest discover tests
```

- 手順 4・5 は、#9 が main にマージされてから使える（それまでは `requirements.txt` と `tests/` が main にない）。
- 次回以降、作業を始めるときは `cd ~/workspace/anatomia && source .venv/bin/activate` だけ実行する。
- `(.venv)` がプロンプトの先頭に出ていれば、仮想環境が有効になっている。
- Ubuntu 24.04 では、仮想環境の外で `pip install` するとエラーになる。**必ず仮想環境を有効にしてから入れる。**
- `.venv` は `.gitignore` に入っているので、commit されない。

## 3. 任意の道具

### GitHub CLI

```bash
sudo apt install -y gh
gh auth login
```

### Docker

収集スクリプトを、Python のバージョンを固定した環境（コンテナ）で動かすために使う想定。企画書にはまだ書かれていない【案】で、使うことが決まったら企画書 §6-2 に反映する。`Dockerfile` もまだない（必要になったときに別の PR で作る）。

**Windows + WSL の場合（Docker Desktop を使う）**

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) を Windows に入れる。
2. Docker Desktop の Settings → Resources → WSL integration で、使っている Ubuntu をオンにして「Apply & restart」を押す。
3. Ubuntu のターミナルで確認する。

```bash
docker --version
docker run --rm hello-world
```

- Ubuntu の中に Docker を入れ直す必要はない（Docker Desktop が WSL とつながる）。
- Docker Desktop には利用条件（ライセンス）がある。職場や学校のパソコンで使う人は、各自で確認する。

**Docker を使っても変わらないこと**

- 取得は**メンバーが手動で実行する**。コンテナの自動起動・定期実行（`restart` の設定や cron など）は設定しない（AGENTS.md 禁則 3）。
- 取得したページの本文はリポジトリに入れない（AGENTS.md 禁則 6）。コンテナの出力先を、リポジトリの中に置くときは注意する。
- Docker を使わなくても、§2 の手順（venv）で同じスクリプトを動かせる状態を保つ。

### Claude Code

```bash
curl -fsSL https://claude.ai/install.sh | bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
cd ~/workspace/anatomia && claude
```

初回はブラウザでのログインと、フォルダを信頼するかの確認が出る。

## 4. Windows(WSL を使わない場合)

- Python 3.12 を <https://www.python.org/downloads/> から入れる(「Add python.exe to PATH」にチェックを入れる)。
- 仮想環境の有効化は、PowerShell で `.venv\Scripts\Activate.ps1` を実行する。それ以外は上の手順と同じ。
- 迷ったら WSL(Ubuntu 24.04)を入れるほうが、手順を揃えられる。

## 5. 困ったとき

| 症状 | 原因と対処 |
| --- | --- |
| `externally-managed-environment` と出る | 仮想環境が有効になっていない。`source .venv/bin/activate` を実行する |
| `python3 -m venv` が失敗する | `sudo apt install -y python3-venv` を実行する |
| `ModuleNotFoundError` | 仮想環境が有効か確認し、`pip install -r requirements.txt` をやり直す |
| `claude: command not found` | PATH に `~/.local/bin` を追加する(§3) |

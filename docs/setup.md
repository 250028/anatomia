# 開発環境のセットアップ【案】

> **位置づけ**：メンバーが手元で開発環境を作るための手順。企画書 §6-2（開発環境【案】）の「Python 3（バージョンはチームで固定）」を具体にしたもの。対象は収集側（Python）で、画面側（§6-2 の Next.js）の環境は含まない\
> **確度**：**【案】**。Python のバージョンとライブラリは、チームで確認してから確定する。ライブラリは R-9 で確定し、一覧は `requirements.txt` を正とする（この文書には書き写さない）。バージョンを決める場所（§8 Q-3 に含めるか、§6-2 で決めるか）は未定で、リーダーの判断を仰ぐ。確定後は §6-2 を正とし、この文書は参照にする案\
> **動作確認**：main（`48e4b15`、#9 のマージ後）を `git clone` し直し、Python 3.12.3（Ubuntu 24.04）の venv で、手順 4・5（`pip install -r requirements.txt`、`python -m unittest discover -s tests -t .`）が 22 件 OK になることを作成者が確認した（Ubuntu 24.04.5 の標準の Python が 3.12.3 であること、venv の外の `pip install` が `externally-managed-environment` で失敗することも、2026-10-07 に作成者が 24.04 で確認した）。Docker は、Docker Desktop（WSL integration）と、WSL の Ubuntu 24.04 に直接入れた Docker Engine（Docker Desktop なし）のどちらでも、`docker run --rm hello-world` が通ることまで作成者が確認した（Docker Engine は 2026-10-08。`docker` グループへの追加後にターミナルを開き直す必要があることも確認した。収集スクリプトのコンテナ実行は未確認）\
> **更新のしかた**：上書き（最新が正）\
> **最終更新**：2026-10-08

## 1. 入れるもの

| 道具 | 版 | 必須か | 用途 |
| --- | --- | --- | --- |
| Python | **3.12 系【案】** | 必須 | 収集スクリプトの実行 |
| Git | 最新 | 必須 | リポジトリの取得・PR |
| GitHub CLI(`gh`) | 最新 | 任意 | ターミナルから GitHub にログイン・PR 操作 |
| Python のライブラリ | `requirements.txt` を正とする | 必須 | 収集スクリプトの実行。一覧は R-9 で確定する（§6-2）。ここには書き写さない |
| Docker | 最新 | 任意【案】 | 収集スクリプトを、全員が同じ Python の環境で動かす |
| Claude Code | 最新 | 任意 | AI によるコード作成の補助 |

**Python を 3.12 にする【案】の理由**:

- Ubuntu 24.04 の標準の Python が 3.12.3 である（2026-10-07、24.04.5 で `python3 --version` を作成者が確認した）。仮想環境用の `python3-venv` は、apt で別に入れる。
- 全員が同じ版にそろえると、版の違いで動作が変わることがない（§6-2「バージョンはチームで固定」の趣旨）。
- 新しすぎる版は、ライブラリの対応が遅れることがある（一般的な傾向で、このリポジトリのライブラリでは未確認）。

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
python -m unittest discover -s tests -t .
```

- 次回以降、作業を始めるときは `cd ~/workspace/anatomia && source .venv/bin/activate` だけ実行する。
- `(.venv)` がプロンプトの先頭に出ていれば、仮想環境が有効になっている。
- Ubuntu 24.04 では、仮想環境の外で `pip install` すると `externally-managed-environment` のエラーになる（作成者が 24.04 で確認済み）。**必ず仮想環境を有効にしてから入れる。**
- `.venv` は `.gitignore` に入っているので、commit されない。

## 3. 任意の道具

### GitHub CLI

```bash
sudo apt install -y gh
gh auth login
```

### Docker

収集スクリプトを、Python のバージョンを固定した環境（コンテナ）で動かすために使う想定。企画書にはまだ書かれていない【案】で、使うことが決まったら企画書 §6-2 に反映する。`Dockerfile` もまだない（必要になったときに別の PR で作る）。

A と B は、どちらか 1 つを選ぶ（両方を入れると、B の注意のとおり、どちらを使っているか分かりにくい）。A は Windows に Docker Desktop を入れる（利用条件は A の注意）。B は Ubuntu の中に入れる（systemd と `sudo` が要る）。

**Windows + WSL の場合（A. Docker Desktop を使う）**

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) を Windows に入れる。
2. Docker Desktop の Settings → Resources → WSL integration で、使っている Ubuntu をオンにして「Apply & restart」を押す。
3. Ubuntu のターミナルで確認する。

```bash
docker --version
docker run --rm hello-world
```

- A の場合、Ubuntu の中に Docker を入れ直す必要はない（Docker Desktop が WSL とつながる）。
- Docker Desktop には利用条件（ライセンス）がある。職場や学校のパソコンで使う人は、各自で確認する。

**Ubuntu 24.04 の場合（B. Ubuntu に Docker Engine を直接入れる。Docker Desktop は不要）**

前提：WSL の場合は、systemd が有効であること（`/etc/wsl.conf` に `[boot]` と `systemd=true`）。有効かどうかは `ps -p 1 -o comm=` で確かめ、`systemd` と出れば有効。`systemctl` が「System has not been booted with systemd」と出るなら無効なので、`/etc/wsl.conf` に上の2行を `sudo` で書き、PowerShell で `wsl --shutdown` してから Ubuntu を開き直す（無効だったときの手順は一般的な知識で、作成者は試していない）。Ubuntu 24.04 で、[Docker 公式の apt リポジトリ](https://docs.docker.com/engine/install/ubuntu/)から入れる。WSL なしの Ubuntu 24.04 でも、systemd の前提を除けばほぼ同じ手順のはずだが、WSL なしでは試していない。

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER && sudo systemctl enable --now docker
```

`docker` グループへの追加は、ログインし直すまで今のターミナルに反映されないのが一般的なので、**ターミナルを開き直す**（または `newgrp docker` を実行する）。そのうえで確認する（`docker` グループに入っていない状態から、同じターミナルで `sudo usermod -aG docker $USER` のあとに `docker run --rm hello-world` を実行すると `permission denied` になり、ターミナルを開き直すと通ることを、作成者が 2026-10-08 に Ubuntu 24.04 で確認した）。

```bash
hash -r
ls -l "$(which docker)"
docker run --rm hello-world
```

- どちらの `docker` を使っているかは、`ls -l "$(which docker)"` でリンク先を見る（B では `/usr/bin/docker` が通常のファイルであることを作成者が確認した）。Docker Desktop の WSL integration では、Docker Desktop 側を指すリンクが置かれることがあるが、A の環境での結果は未確認。`docker info --format '{{.OperatingSystem}}'` でも見分けられる見込みだが、こちらも A では未確認。
- `docker` グループに入っていると、`sudo` なしで `docker` を使える。このグループは root 相当の権限を持つので、自分専用の環境で使う。
- Docker Desktop の WSL integration が残っていると、どちらの `docker` を使っているか分かりにくい。使わないなら integration をオフにするか、アンインストールする。
- 手順はそのまま実行して通ることを作成者が確認した（2026-10-08、Ubuntu 24.04）。

**Docker を使っても変わらないこと**

- 取得は**メンバーが手動で実行する**。コンテナの自動起動・定期実行（`restart` の設定や cron など）は設定しない（企画書 §6-1。エージェント向けは AGENTS.md 禁則 3）。
- 取得したページの本文はリポジトリに入れない（企画書 §3-2 ①・§6-3。エージェント向けは AGENTS.md 禁則 6）。本文をファイルに保存するときは、コンテナの出力先をリポジトリの外にする。
- Docker を使わなくても、§2 の手順（venv）で同じスクリプトを動かせる状態を保つ。

### Claude Code

```bash
curl -fsSL https://claude.ai/install.sh | bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
cd ~/workspace/anatomia && claude
```

初回はブラウザでのログインと、フォルダを信頼するかの確認が出る。

## 4. Windows

WSL（Ubuntu 24.04）を使う。WSL なしの Windows 単体の手順は、確かめていないので書かない。

## 5. 困ったとき

| 症状 | 原因と対処 |
| --- | --- |
| `externally-managed-environment` と出る | 仮想環境が有効になっていない。`source .venv/bin/activate` を実行する |
| `python3 -m venv` が失敗する | `sudo apt install -y python3-venv` を実行する |
| `ModuleNotFoundError` | 仮想環境が有効か確認し、`pip install -r requirements.txt` をやり直す |
| `claude: command not found` | PATH に `~/.local/bin` を追加する(§3) |

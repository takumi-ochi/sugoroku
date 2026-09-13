---
name: start-server
description: すごろくのゲームサーバーをウィンドウなしのバックグラウンドで起動し、PC画面とスマホ参加用のURLをクリックできるリンクで表示する。「サーバー起動」「ゲームを始めたい」「サーバー立てて」などと言われたときに使う。
---

# すごろくサーバーの起動

## 1. スクリプトを実行する

PowerShell ツールで、プロジェクトのルートから次を実行する（初回は venv 作成と依存インストールで数分かかるので timeout は 300000 にする）。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\.claude\skills\start-server\start.ps1
```

スクリプトがやること:

- ポート（`config.py` の `PORT`）がすでに待ち受け中なら、何もせず `STATUS=already_running`
- `.venv` がなければ作って依存をインストールする
- `main.py` を**ウィンドウなし**で起動し、待ち受けるまで最大30秒待つ
  - Claude のセッションが終わってもサーバーは動き続ける
  - 出力はログファイル（`LOG`）に書かれる。ターミナルのQRコードは出ないが、PC画面にQRが表示される

出力は `KEY=VALUE` の行:

| キー | 値 |
|---|---|
| `STATUS` | `already_running` / `started` / `error` |
| `HOST_URL` | PC画面のURL |
| `JOIN_URL` | スマホ参加用のURL（LAN IP） |
| `NETWORK` | 使っているネットワークの種類（`Private` / `Public` など） |
| `LOG` | サーバーのログファイル |
| `MESSAGE` | `error` のときの理由 |

## 2. 結果をユーザーに伝える

`STATUS` が `started` または `already_running` のときは、次の形で**Markdownリンク**として表示する（URLはスクリプトの出力をそのまま使う）。

```markdown
サーバーを起動しました。（すでに起動していた場合は「サーバーはすでに起動しています。」）

- PC画面: [HOST_URL](HOST_URL) （スマホ用のQRコードもここに出ます）
- スマホ参加: [JOIN_URL](JOIN_URL)

止めるときは `/stop-server` を使ってください。
```

補足を付ける条件:

- `NETWORK` が `Public` のとき: スマホから繋がらない可能性が高い。管理者PowerShellで `setup-firewall.ps1` を実行するよう案内する（手順は README の「Git Bash から」を参照）。勝手に実行しない（管理者権限の変更なので、ユーザーの確認が要る）
- `JOIN_URL` が `127.0.0.1` のとき: ネットワーク未接続。Wi-Fi を確認するよう伝える
- `STATUS=error`: `LOG` のファイルを Read して、原因をユーザーに伝える

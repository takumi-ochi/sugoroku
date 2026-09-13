---
name: stop-server
description: バックグラウンドで動いているすごろくのゲームサーバーを停止する。「サーバー止めて」「ゲーム終わり」などと言われたときに使う。
---

# すごろくサーバーの停止

`/start-server` はウィンドウなしで起動するため、`Ctrl+C` では止められない。停止はこのスキルで行う。

## 1. スクリプトを実行する

PowerShell ツールで、プロジェクトのルートから次を実行する。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\.claude\skills\stop-server\stop.ps1
```

ポートを待ち受けている `main.py` のプロセスを止める。run.bat から起動したものも止まる（その場合 run.bat のウィンドウは「Press any key」で残る）。

## 2. 結果を伝える

- `STATUS=stopped`: 「サーバーを停止しました。」
- `STATUS=not_running`: 「サーバーは起動していません。」

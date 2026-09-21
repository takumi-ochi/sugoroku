# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Windows の親機で FastAPI + WebSocket のサーバーを動かし、同じWi-Fi上のスマホがブラウザで
繋いで遊ぶすごろく。コメント・UI文言・テスト名はすべて日本語。

**ゲームのルール、通信の中身、設計の決まりごとは README.md に書いてある。そちらを参照すること。**

## コマンド

依存は `.venv` にある。`python` ではなく `.venv/Scripts/python.exe` を直接指す。

```bash
# サーバー起動・再起動（ウィンドウなしのバックグラウンド。Ctrl+C では止まらない）
/run-server            # スキル。停止は /stop-server
.venv/Scripts/python.exe main.py    # 前面で起動したいときだけ

# ゲームロジックのテスト（サーバー不要）
.venv/Scripts/python.exe -m unittest discover -s tests -t . -v
.venv/Scripts/python.exe -m unittest tests.test_game.TestCards -v                      # クラス単位
.venv/Scripts/python.exe -m unittest tests.test_game.TestCards.test_カードマスに止まると1枚もらえる -v
.venv/Scripts/pytest.exe tests/test_game.py -k カード                                   # pytest も入っている

# 共有JSのテスト（ブラウザ不要）
node --test "tests/js/*.test.mjs"
```

`.py` を変更したら `/run-server` で再起動しないと反映されない。HTML・JS・CSS は
`Cache-Control: no-store` で配っているので、ブラウザの再読み込みだけで反映される。

## 構成

```
main.py         起動のみ（QR表示 + uvicorn）
config.py       PORT・LAN IP・参加URL

game/           ゲームのルールと状態。FastAPI も WebSocket も import しない
  logic.py        Game クラス（手番・ターン・サイコロ・マス効果・カード・順位）
  board.py        盤面の定義
  cards.py        カードの種類と山札
  events.py       「誰に何を送るか」を表す Event

net/            通信のみ。ゲームのルールは持たない
  server.py       HTTP と WebSocket の入り口
  hub.py          接続の保持と Event の配信

static/
  host.html       PC画面（/host）
  player.html     スマホ画面（/）
  shared/         両画面が使う部品（format.js / dice.js / sound.js / anim.js / ring.js / dice.css）

tests/
  test_game.py        ゲームロジックの単体テスト
  js/shared.test.mjs  共有JSの単体テスト
```

`game/logic.py` の `handle()` / `handle_host()` がメッセージ1件を処理して `Event` のリストを返し、
`net/hub.py` がそれを宛先ごとに実際のWebSocketへ流す。`game/` は送信も切断も自分では行わない。

テストは `FixedDice` で出目とカードを固定する（`solo()` は1人だけのゲームを作るヘルパ）。

# すごろく（Windows親機 ⇄ iOS / Android）

PCの画面に盤面を出し、手元のスマホでサイコロを振って遊ぶ。
スマホ側はブラウザだけ。アプリのインストールは要らない。

## 起動

**`run.bat` をダブルクリック**するのが一番簡単です。

コマンドから起動する場合:

```bash
# Git Bash
./.venv/Scripts/python.exe main.py
```

```powershell
# PowerShell（実行ポリシーの制限を受けないよう -File で呼ぶ）
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

止めるときは `Ctrl + C`。

初回のみ venv 作成と依存インストールが走ります（`run.bat` が自動でやります）。

起動するとターミナルにQRコードと2つのURLが出ます。

- **PC画面** `http://localhost:8000/host` をブラウザで開く（QRもここに出ます）
- **スマホ** 同じWi-Fiに繋いだ状態でQRを読む

## あそびかた

1. PCで `/host` を開く → 右上が緑の「サーバー接続済み」になる
2. スマホでQRを読む → 名前を入れて「参加する」
3. 全員そろったらPC画面の **「ゲーム開始」** を押す
4. 手番の人のスマホに **「サイコロをふる」** が出る。押すと3Dサイコロが回り、
   出目が決まるとコマが1マスずつ進む（PC・スマホの両方で音が鳴る）
5. 全員がゴールしたら終了。「もう一度あそぶ」で再戦できる

### ルール

- 30マス。`0` がスタート、`29` がゴール
- 手番は参加した順。出目は 1〜6
- ゴールちょうどでなくてよい。超えたぶんは切り捨てて止まる
- 止まったマスの効果
  - **ワープ** その数だけさらに進む
  - **もどる** その数だけ下がる（0より手前には戻らない）
  - **一回休み** 次の自分の番を飛ばす
- 全員がゴールするまで続き、ゴールした順に順位がつく

盤面のマス配置は `game/board.py` の `SPECIALS` で決まる。ここを書き換えれば盤が変わる。

### 途中の出入り

- 手番の人が抜けても、次の人に自動で回る
- スマホの「退出する」、PC画面の各行の「切断」でいつでも抜けられる
- 全員抜けると開始前の状態に戻る

## 繋がらないときは

| 症状 | 原因と対処 |
|---|---|
| スマホでページが開かない | **同じWi-Fiにいない**のが大半。スマホのモバイル通信をオフにして確認 |
| 同上 | ファイアウォール。`setup-firewall.ps1` を管理者PowerShellで実行（設定は永続化されるので通常は1回だけ） |
| 同上 | 別のWi-Fiに繋ぎ替えた場合、そのネットワークが「パブリック」だと再びブロックされる。`setup-firewall.ps1` を再実行すれば直る |
| ターミナルのIPが `127.0.0.1` | ネットワーク未接続。Wi-Fi/有線を確認 |
| ゲストWi-Fi / 社内Wi-Fi | 端末間通信がブロックされている（AP isolation）。スマホのテザリングにPCを繋ぐと回避できることが多い |
| iOSで画面ロック後に反応しなくなる | 対処済み。復帰時に自動再接続します（1秒以内） |

## 構成

通信とゲームのルールを分けてある。ゲームを作り込むときに触るのは `game/` だけ。

```
main.py            起動するだけ（QR表示 + uvicorn）
config.py          ポート番号・LAN IP・参加URL

game/              ゲームのルールと状態  ← ここを育てていく
  logic.py           Game クラス。手番・サイコロ・マスの効果
  board.py           盤面の定義（マス数と特殊マス）
  events.py          「誰に何を送るか」の表現

net/               通信  ← ゲームを増やしても基本さわらない
  server.py          HTTPとWebSocketの入り口
  hub.py             接続の保持とイベント配信

static/
  host.html          PC画面（盤面・サイコロ・参加者一覧）
  player.html        スマホ画面（サイコロを振る）
  shared/            両画面で使う部品  ← 見た目や音を直すのはここ
    format.js          画面に出す文字（位置・出目・ゴール）
    dice.js            3Dサイコロ
    sound.js           効果音（WebAudioで合成。音声ファイル不要）
    anim.js            1マスずつの移動、状態の順番待ち
    dice.css           サイコロの見た目

tests/
  test_game.py       ゲームロジックの単体テスト（サーバー不要）
  js/shared.test.mjs 共有部品の単体テスト（ブラウザ不要）
```

### なぜ分けるか

`game/logic.py` は FastAPI も WebSocket も import していない。
そのためサーバーを起動せずにルールを検証できる。

```bash
./.venv/Scripts/python.exe -m unittest discover -s tests -t . -v
```

### 流れ

```
スマホ ──{"type":"roll"}──> net/server.py
                              |
                              v
                          net/hub.py  ──> game/logic.py の handle()
                              |                  |
                              |          [Event(...), Event(...)] を返す
                              v                  |
                          宛先ごとに送信 <────────┘
                              |
                    ┌─────────┴─────────┐
                    v                   v
                 PC画面              全スマホ
```

`game/logic.py` は「誰に何を送るか」を `Event` で返すだけで、送信そのものはしない。
`net/hub.py` がそれを受け取って実際のWebSocketに流す。

### 状態の持ち方

差分ではなく、毎回 `state` をまるごと全員に配る。

```python
{"type": "state",
 "phase": "playing",              # waiting / playing / finished
 "goal": 29,
 "board": [{"kind": "forward", "value": 2, "label": "ワープ +2"}, ...],
 "turn": "p1",                    # いま手番のプレイヤーID
 "last_roll": {"seq": 7, "id": "p1", "name": "アオイ", "value": 4,
               "from": 3, "land": 7, "to": 9, "effect": "ワープ +2", "rank": null},
 "players": [{"id": "p1", "name": "アオイ", "color": "#ff5c7c",
              "pos": 9, "resting": false, "rank": null}, ...]}
```

画面側は受け取った `state` を描き直すだけでよく、表示がずれない。
途中から `/host` を開いても、その時点の盤面がそのまま出る。

`last_roll` の3つの位置はアニメーション用に分けてある。

| | 意味 |
|---|---|
| `from` | 振る前の位置 |
| `land` | 出目ぶん進んだ位置（マスの効果を受ける前） |
| `to` | マスの効果まで反映した最終位置 |

`from → land` を1マスずつ歩き、効果マスなら一拍おいて `land → to` を歩く。
`seq` は振るたびに増える通し番号で、画面側が「新しい出目か」を判定する。
再読み込みや途中参加のときは演出せず、いきなり最終状態を描く。

### ゲームを足すには

`game/logic.py` の `handle()` に分岐を足す。状態は `Game` のフィールドに持たせる。
`net/` は触らなくてよい。

```python
if kind == "roll":
    return self._roll(player)
elif kind == "answer":            # 例: クイズの回答
    return self._check_answer(player, message["choice"])
```

盤だけ変えたいなら `game/board.py` の `SPECIALS` を書き換える。

### 通信の中身

スマホ → サーバー

```json
{"type": "roll"}     サイコロをふる（自分の番でなければ無視される）
{"type": "leave"}    退出ボタンを押した
```

PC画面 → サーバー

```json
{"type": "start"}               ゲーム開始（全員スタートに戻して手番を先頭へ）
{"type": "reset"}               開始前の状態に戻す
{"type": "kick", "id": "p2"}    その参加者を切断する
```

サーバー → PC画面 / スマホ（両方に同じものを配る）

```json
{"type": "state", ...}    上記のとおり
```

サーバー → スマホ（その人だけ）

```json
{"type": "joined", "you": {...}}   参加できた。自分のIDと色が入る
{"type": "left"}                   退出が受理された（この直後に切断される）
{"type": "kicked"}                 PC画面から切断された
```

### 切断の扱い

`left` / `kicked` を送ったあと、サーバーがWebSocketを閉じる。

ゲームロジックは `Event(..., close=True)` で「閉じてほしい」と示すだけで、
実際の `ws.close()` は `net/hub.py` が行う。ここでも層は分かれている。

スマホ側は、退出・キックのときだけ自動再接続を止めて名前入力画面に戻る
（iOSの画面ロックによる切断とは区別している）。

## テスト

```bash
# ゲームのルール
./.venv/Scripts/python.exe -m unittest discover -s tests -t . -v

# 画面の共有部品
node --test tests/js/
```

どちらもサーバーもブラウザも起動しない。

サイコロは差し替えられるので、出目を固定してマスの効果や手番の回り方を検証している。

```python
game = Game(rng=FixedDice(9, 1))   # 必ず 9 → 1 が出る
```

## PC画面とスマホで表示を揃える仕組み

同じ内容を2つのHTMLに別々に書くと、片方だけ直して食い違う。実際に起きた。

- サイコロのCSSを片方にだけ変更 → PC側だけサイコロが消えた
- 位置の文字列を別々に組み立て → 表示がずれた

そこで **両画面が使う部分は `static/shared/` にしか置かない**ことにした。

| 直したい場所 | 触るファイル |
|---|---|
| 位置や出目の文言 | `shared/format.js` |
| サイコロの見た目 | `shared/dice.css` |
| サイコロの動き | `shared/dice.js` |
| 効果音 | `shared/sound.js` |
| 移動の速さ | `shared/anim.js` |

位置の表示は `posLabel()` だけが作る。PC画面の一覧もスマホの見出しも同じ関数を呼ぶので、
文言も数字も食い違いようがない。`node --test tests/js/` がこれを検証している。

### 表示をサーバーの値で締める

演出中は表示用の仮の位置を使うが、**演出が終わったら必ずサーバーの状態で描き直す**。

- PC画面: `drawPanel()` と `drawTokens()`
- スマホ: `drawStatic()`

途中で切断されても、次の状態が届けば正しい値に戻る。

### 注意: サイコロのCSSに足してはいけないもの

`.cube` に `filter` / `opacity` / `overflow` を足さないこと。
これらは `transform-style: preserve-3d` を無効化し、立方体が平坦化して消える。
影が欲しいときは `.face` 側の `box-shadow` を使う（`shared/dice.css` に注意書きあり）。

### ブラウザのキャッシュ

HTML・JS・CSSは `Cache-Control: no-store` で配っている。
画面を書き換えたのに古いJSが動き続ける事故を防ぐため。通常の再読み込みで必ず最新になる。

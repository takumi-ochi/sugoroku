---
name: implementation
description: すごろくアプリに手を入れるときの進め方。機能追加・ルール変更・マスやカードを足す・画面や音の調整・バグ修正のときに使う。「〜を追加して」「ルールを変えて」「マスを増やして」「カードを足して」「画面を直して」「挙動がおかしい」などと言われたら、コードを書き始める前にこれを読む。
---

# すごろくの改修の進め方

このアプリは **スマホ連携（../game_common）とゲームのルール（game/）と見た目（static/）を分けてある**。
どこを触るかを先に決めると、直す量も壊れ方も小さくなる。迷ったら README.md の「構成」を読む。

スマホ連携は他のゲームと共有している共通部品なので、**すごろく固有のものを持ち込まない**。
共通側を触るときは ../game_common/README.md を読むこと。

## 1. どの層の話か決める

| やりたいこと | 触るファイル | 触らなくていいもの |
|---|---|---|
| マスの並び・種類・金額 | `game/board.py`（`SPECIALS` と定数） | それ以外ほぼ全部 |
| カードの種類・枚数・手札上限 | `game/cards.py` | `../game_common/` |
| 手番・ターン・サイコロ・勝敗 | `game/logic.py` | `../game_common/` |
| スマホ／PCからの新しい操作 | `game/logic.py` の `handle()` / `handle_host()` に分岐を足す | `../game_common/`（増やしても基本さわらない） |
| 画面に出す文言・金額・順位 | `static/shared/format.js` | HTML 側で文字列を組み立てない |
| サイコロの見た目・動き・音・移動速度 | `static/shared/` の `dice.css` / `dice.js` / `sound.js` / `anim.js` | HTML 側に同じものを書かない |
| PC画面だけ／スマホだけのレイアウト | `static/host.html` / `static/player.html` | |
| HTTPやWebSocketの入り口、配信の仕組み | `../game_common/mobilelink/` | 他のゲームにも効く。通信の都合のときだけ |
| 切れたときの繋ぎ直し | `../game_common/mobilelink/static/conn.js` | 同上 |

**両画面に出るものは `static/shared/` にしか置かない。** 片方だけ直して食い違う事故が実際に起きている。

## 2. 層の決まりを守る

- `game/` は FastAPI も WebSocket も import しない。サーバーなしでテストできる状態を保つ。
- `game/` が共通側に見せている形は `state()` / `add_player()` / `remove_player()` /
  `handle()` / `handle_host()` の5つだけ（`../game_common/mobilelink/protocol.py`）。この形は崩さない。
- ゲーム側は送信しない。`mobilelink` の `to_hosts()` / `to_player()` で **「誰に何を送るか」を返すだけ**。
  切断も `Event(..., close=True)` で意思表示するだけで、実際に閉じるのは共通側の `Hub`。
- 状態は差分ではなく `state` をまるごと配る。フィールドを足したら `Game.state()` に入れる。
- **手札の中身は `state()` に入れない。** 公開分は `state()`、本人にだけ足すのは `_private()`。
  PC画面と他の参加者に見えてはいけないものは、必ず `_private()` 側へ。
- カードを1枚指すときは添字ではなく `uid`。指示が届くまでに手札が変わるため。
- `.cube` に `filter` / `opacity` / `overflow` を足さない（立方体が平坦化して消える。影は `.face` の `box-shadow`）。

新しい操作を足すときの形:

```python
# game/logic.py handle()
if kind == "roll":
    return self._roll(player)
elif kind == "answer":            # 例: クイズの回答
    return self._check_answer(player, message["choice"])
```

スマホ／PC からのメッセージを増やしたら、README.md の「通信の中身」も一緒に直す。

## 3. テストを書く

**ルールを変えたら必ずテストも足す・直す。** テスト名は日本語の文章にする。

```python
# tests/test_game.py
game, p = solo(4, cards=[cards.GUARD])   # 1人だけ・出目を固定・ひくカードも固定
game = Game(rng=FixedDice(9, 1))         # 必ず 9 → 1 が出る
```

- ゲームのルール → `tests/test_game.py`（既存の `TestBoard` / `TestTurn` / `TestSquares` などの近い場所へ）
- `shared/` の文言・移動 → `tests/js/shared.test.mjs`
- 期待値は「最後の `state` の中身」で確かめる。演出用の値は `last_roll` を見る。

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -t . -v
node --test "tests/js/*.test.mjs"
```

共通側（`../game_common`）を触ったなら、そちらのテストも通す。他のゲームにも影響する。

```bash
cd ../game_common && ../sugoroku/.venv/Scripts/python.exe -m unittest discover -s tests -t . -v
cd ../game_common && node --test "tests/js/*.test.mjs"
```

**通してから報告する。** 落ちたら落ちた出力のまま伝える。

## 4. 変更を反映する

- `.py` を触った → `/run-server` で再起動する（**確認を取らずそのまま実行してよい**）。
  再起動すると進行中のゲーム（参加者・所持金・ターン）は消えるので、それは伝える。
- `.html` / `.js` / `.css` だけ → 再起動は不要。「ブラウザを再読み込みしてください」と伝える。

## 5. 報告する

- 何を変えたか（ファイルはクリックできるリンクで）
- テストの結果（通った／落ちた）
- 反映のために相手がやること（再読み込み、またはサーバー再起動済みの旨）
- ルールの見た目が変わったなら、README.md の「あそびかた」も直したか

## やらないこと

- 頼まれていない盤面・金額・ターン数の「ついでの調整」。数字はゲームバランスなので勝手に変えない。
- `game/` へのフレームワーク依存の持ち込み。
- `../game_common/` へのすごろく固有のものの持ち込み（盤・カード・階層など）。
- 同じ文言を HTML 2枚に別々に書くこと。
- テストを消して通すこと。

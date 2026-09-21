---
name: push
description: すごろくの変更をテストしてからコミットし、GitHub（origin）へpushする。「pushして」「コミットしてpush」「GitHubに上げて」「変更を保存して上げて」などと言われたときに使う。
---

# コミットして push する

このスキルが呼ばれた時点で、コミットと push はユーザーが頼んだものとして進めてよい（確認は要らない）。
ただし **force push・`--no-verify`・履歴の書き換えは、明示的に頼まれない限りしない。**

## 1. 状態を見る

```bash
git status --short
git branch --show-current
git diff --stat
git log --oneline -5
```

- 変更が無ければ「コミットするものがありません」と伝えて終わる。
- `master` にいるのは普通（このリポジトリは master で運用している）。ブランチは作り分けない。

## 2. テストを通す

**どちらも通ってから進む。** 落ちたら push せず、落ちた出力をそのまま伝えて止まる。

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -t .
node --test "tests/js/*.test.mjs"
```

## 3. 入れるものを選ぶ

`git add -A` で一括では入れない。`git status` の一覧を見て、ファイル名を指定して `git add` する。

入れてはいけないもの:

- `.venv/`、`__pycache__/`、`*.pyc`（`.gitignore` 済み）
- `.env`・鍵・トークンなど秘密情報
- ログや一時ファイル（`*.log`、スクラッチ用のもの）

意図の分からない変更や、今回の作業と無関係な変更が混ざっていたら、入れずに「これは入れていません」と報告する。
音声など大きなバイナリを足したときは、サイズ（`ls -l`）と出どころ（ライセンス）をコミットメッセージか README で追えるようにしておく。

## 4. コミットする

- 履歴の書き方に合わせる。**日本語・短い一行**（例: `カードと半分通過ボーナスを追加`）。
  直近の `git log --oneline` を見て、文体をそろえる。
- 1行目は「何をしたか」。理由が必要なときだけ空行のあとに数行足す。
- 変更が別々の話（例: BGM追加とサイコロ修正）なら、コミットを分ける。
- 末尾にシステムから指示された Co-Authored-By 行を付ける。

```bash
git commit -m "$(cat <<'MSG'
BGMを追加し、2個目のサイコロも転がるようにした

Co-Authored-By: <指示された名前>
MSG
)"
```

pre-commit フックが落ちたら原因を直して**新しくコミットし直す**（`--amend` や `--no-verify` は使わない）。

## 5. push する

```bash
git push origin HEAD
```

- 拒否された（リモートが先に進んでいる）ときは `git pull --rebase origin master` してから再度 push する。
  コンフリクトが出たら自分で解決せず、状況をユーザーに伝えて止まる。
- 認証エラーはユーザーの GitHub 認証の問題。原因を伝えるだけにする。

## 6. 報告する

- コミットのハッシュとメッセージ（`git log --oneline -3`）
- push 先（`origin/master`）と成功したか
- 入れなかったファイルがあれば、その名前と理由
- テストの結果（通った件数）

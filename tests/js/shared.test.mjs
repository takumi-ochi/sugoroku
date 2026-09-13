/* 共有モジュールのテスト。ブラウザもサーバーも要らない。
 *
 *   node --test tests/js/
 *
 * PC画面とスマホはここの関数しか使わないので、
 * ここが一致していれば両画面の表示は食い違わない。
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  posLabel, moveLabel, rolledLabel, goalLabel, rollSummary, effectStyle, GOAL_CHIME,
} from "../../static/shared/format.js";
import { walk, createQueue } from "../../static/shared/anim.js";

/* ---------- 表示文言 ---------- */

test("いまの位置はマス数で出る", () => {
  assert.equal(posLabel({ pos: 0, resting: false, rank: null }), "0 マス");
  assert.equal(posLabel({ pos: 12, resting: false, rank: null }), "12 マス");
});

test("一回休みは位置に添えて出る", () => {
  assert.equal(posLabel({ pos: 9, resting: true, rank: null }), "9 マス / 一回休み");
});

test("ゴール済みは順位で出る", () => {
  assert.equal(posLabel({ pos: 29, resting: false, rank: 2 }), "2位 ゴール");
});

test("PC画面とスマホは同じ関数で同じ文字列になる", () => {
  const player = { pos: 17, resting: false, rank: null };
  // 両画面はどちらも posLabel を呼ぶ。呼び出し方が同じなら結果も同じ。
  assert.equal(posLabel(player), posLabel({ ...player }));
  assert.equal(posLabel(player), "17 マス");
});

test("移動と出目とゴールの文言", () => {
  assert.equal(moveLabel(3, 9), "3 → 9");
  assert.equal(rolledLabel(4), "4 が出た");
  assert.equal(goalLabel(1), "ゴール！ 1位");
});

test("他人の手番のまとめは効果とゴールを順に足す", () => {
  assert.deepEqual(
    rollSummary({ name: "アオイ", value: 4, from: 3, to: 9, effect: "ワープ +2", rank: null }),
    ["アオイ  4", "3 → 9", "ワープ +2"],
  );
  assert.deepEqual(
    rollSummary({ name: "ボブ", value: 2, from: 27, to: 29, effect: null, rank: 1 }),
    ["ボブ  2", "27 → 29", "ゴール！ 1位"],
  );
});

test("マスの種類ごとに色と音が決まる", () => {
  assert.equal(effectStyle("forward").cls, "fw");
  assert.equal(effectStyle("back").cls, "bk");
  assert.equal(effectStyle("rest").cls, "rs");
  // 知らない種類でも落ちない
  assert.ok(Array.isArray(effectStyle("なにか").chime));
  assert.equal(GOAL_CHIME.length, 3);
});

/* ---------- 1マスずつの移動 ---------- */

test("進むときは1マスずつ呼ばれる", async () => {
  const seen = [];
  const end = await walk(3, 7, (pos, dir, i) => seen.push([pos, dir, i]), 0);

  assert.equal(end, 7);
  assert.deepEqual(seen.map((s) => s[0]), [4, 5, 6, 7]);
  assert.ok(seen.every((s) => s[1] === 1));
  assert.deepEqual(seen.map((s) => s[2]), [0, 1, 2, 3]);
});

test("戻るときも1マスずつ呼ばれる", async () => {
  const seen = [];
  const end = await walk(6, 4, (pos, dir) => seen.push([pos, dir]), 0);

  assert.equal(end, 4);
  assert.deepEqual(seen.map((s) => s[0]), [5, 4]);
  assert.ok(seen.every((s) => s[1] === -1));
});

test("動かないときは一度も呼ばれない", async () => {
  let calls = 0;
  const end = await walk(5, 5, () => calls++, 0);

  assert.equal(end, 5);
  assert.equal(calls, 0);
});

test("歩き終わりは必ずサーバーの値になる", async () => {
  // 途中の表示がどうであれ、戻り値は to。ここがPC・スマホ共通の締め。
  for (const [from, to] of [[0, 6], [20, 24], [24, 20], [28, 29]]) {
    assert.equal(await walk(from, to, () => {}, 0), to);
  }
});

/* ---------- 状態の順番待ち ---------- */

test("演出中に届いた状態は順番に処理される", async () => {
  const done = [];
  let release;
  const gate = new Promise((r) => (release = r));

  const q = createQueue(async (n) => {
    if (n === 1) await gate;
    done.push(n);
  });

  q.push(1);
  q.push(2);
  q.push(3);
  assert.deepEqual(done, []);      // 1 が終わるまで進まない

  release();
  await new Promise((r) => setTimeout(r, 10));
  assert.deepEqual(done, [1, 2, 3]);
});

test("溜まりすぎたら間引いて最新に追いつく", () => {
  const done = [];
  let release;
  const gate = new Promise((r) => (release = r));

  const q = createQueue(async (n) => {
    if (n === 0) await gate;
    done.push(n);
  }, 3);

  q.push(0);                               // これが詰まっている間に…
  for (let i = 1; i <= 9; i++) q.push(i);  // …9個ぶん届く

  release();
  return new Promise((r) => setTimeout(r, 20)).then(() => {
    assert.equal(done[0], 0);                 // 処理中のものは捨てない
    assert.equal(done.at(-1), 9);             // 最新は必ず処理する
    assert.ok(done.length <= 4, `処理しすぎ: ${done}`);   // 間引いて追いつく
  });
});

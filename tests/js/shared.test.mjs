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
  posLabel, moneyLabel, deltaLabel, rankLabel, roundLabel, salaryLabel,
  moveLabel, rolledLabel, byRank, winnersLabel, rollSummary, effectStyle,
  SALARY_CHIME, FINISH_CHIME,
} from "../../static/shared/format.js";
import { walk, createQueue } from "../../static/shared/anim.js";

/* ---------- 表示文言 ---------- */

test("いまの位置はマス数で出る", () => {
  assert.equal(posLabel({ pos: 0, resting: false }), "0 マス");
  assert.equal(posLabel({ pos: 12, resting: false }), "12 マス");
});

test("一回休みは位置に添えて出る", () => {
  assert.equal(posLabel({ pos: 9, resting: true }), "9 マス / 一回休み");
});

test("金額は3桁ごとにカンマが入る", () => {
  assert.equal(moneyLabel(0), "0円");
  assert.equal(moneyLabel(900), "900円");
  assert.equal(moneyLabel(1000), "1,000円");
  assert.equal(moneyLabel(1234567), "1,234,567円");
});

test("増減は符号つきで出る", () => {
  assert.equal(deltaLabel(200), "+200円");
  assert.equal(deltaLabel(-1500), "-1,500円");
  assert.equal(salaryLabel(200), "スタート通過 +200円");
});

test("順位とターンの文言", () => {
  assert.equal(rankLabel(2), "2位");
  assert.equal(roundLabel(3, 10), "ターン 3 / 10");
});

test("順位順に並べ、同順位は参加順のまま", () => {
  const players = [
    { name: "A", rank: 3 }, { name: "B", rank: 1 }, { name: "C", rank: 2 }, { name: "D", rank: 1 },
  ];
  assert.deepEqual(byRank(players).map((p) => p.name), ["B", "D", "C", "A"]);
  assert.equal(players[0].name, "A");     // 元の配列は並べ替えない
});

test("優勝者は1位全員の名前", () => {
  assert.equal(winnersLabel([{ name: "A", rank: 1 }, { name: "B", rank: 2 }]), "A");
  assert.equal(winnersLabel([{ name: "A", rank: 1 }, { name: "B", rank: 1 }]), "A・B");
});

test("移動と出目の文言", () => {
  assert.equal(moveLabel(27, 3), "27 → 3");
  assert.equal(rolledLabel(4), "4 が出た");
});

test("他人の手番のまとめは給料と効果を順に足す", () => {
  assert.deepEqual(
    rollSummary({ name: "アオイ", value: 4, from: 3, to: 9, effect: "ワープ +2", salary: 0 }),
    ["アオイ  4", "3 → 9", "ワープ +2"],
  );
  assert.deepEqual(
    rollSummary({ name: "ボブ", value: 5, from: 28, to: 3, effect: "もらう +100円", salary: 200 }),
    ["ボブ  5", "28 → 3", "スタート通過 +200円", "もらう +100円"],
  );
});

test("マスの種類ごとに色と音が決まる", () => {
  assert.equal(effectStyle("forward").cls, "fw");
  assert.equal(effectStyle("back").cls, "bk");
  assert.equal(effectStyle("rest").cls, "rs");
  assert.equal(effectStyle("gain").cls, "gn");
  assert.equal(effectStyle("lose").cls, "ls");
  // 知らない種類でも落ちない
  assert.ok(Array.isArray(effectStyle("なにか").chime));
  assert.equal(SALARY_CHIME.length, 2);
  assert.equal(FINISH_CHIME.length, 3);
});

/* ---------- 1マスずつの移動 ---------- */

test("進むときは1マスずつ呼ばれる", async () => {
  const seen = [];
  const end = await walk(3, 4, 30, (pos, dir, i) => seen.push([pos, dir, i]), 0);

  assert.equal(end, 7);
  assert.deepEqual(seen.map((s) => s[0]), [4, 5, 6, 7]);
  assert.ok(seen.every((s) => s[1] === 1));
  assert.deepEqual(seen.map((s) => s[2]), [0, 1, 2, 3]);
});

test("最後のマスを越えるとスタートに戻る", async () => {
  const seen = [];
  const end = await walk(27, 5, 30, (pos) => seen.push(pos), 0);

  assert.equal(end, 2);
  assert.deepEqual(seen, [28, 29, 0, 1, 2]);
});

test("戻るときも1マスずつ呼ばれ、0の手前は最後のマスになる", async () => {
  const seen = [];
  const end = await walk(1, -3, 30, (pos, dir) => seen.push([pos, dir]), 0);

  assert.equal(end, 28);
  assert.deepEqual(seen.map((s) => s[0]), [0, 29, 28]);
  assert.ok(seen.every((s) => s[1] === -1));
});

test("動かないときは一度も呼ばれない", async () => {
  let calls = 0;
  const end = await walk(5, 0, 30, () => calls++, 0);

  assert.equal(end, 5);
  assert.equal(calls, 0);
});

test("歩き終わりはサーバーと同じ計算の位置になる", async () => {
  for (const [from, steps] of [[0, 6], [20, 4], [24, -4], [28, 6], [2, -4]]) {
    assert.equal(await walk(from, steps, 30, () => {}, 0), (((from + steps) % 30) + 30) % 30);
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

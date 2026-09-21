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
  posLabel, moneyLabel, deltaLabel, rankLabel, roundLabel, roundValue, playersLabel, salaryLabel,
  halfwayLabel, moveLabel, rolledLabel, byRank, winnersLabel, rollSummary, effectStyle,
  cardsLabel, statLabel, drewLabel, guardLabel, armedLabel, overLabel, cardStyle,
  SALARY_CHIME, FINISH_CHIME, CARD_CHIME, GUARD_CHIME, HALFWAY_CHIME,
} from "../../static/shared/format.js";
import { walk, createQueue } from "../../static/shared/anim.js";
import { ringSize, ringLayout } from "../../static/shared/ring.js";

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
  assert.equal(halfwayLabel(500), "はんぶん通過 +500円");
});

test("順位とターンの文言", () => {
  assert.equal(rankLabel(2), "2位");
  assert.equal(roundValue(3, 10), "3 / 10");
  assert.equal(roundLabel(3, 10), "ターン 3 / 10");
  assert.equal(playersLabel(4), "4人中");
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
  assert.equal(rolledLabel({ value: 4, values: [4] }), "4 が出た");
});

test("サイコロ2個とカードのぶんは足し算で出る", () => {
  assert.equal(rolledLabel({ value: 9, values: [4, 5] }), "4 + 5 = 9");
  assert.equal(rolledLabel({ value: 6, values: [4], bonus: 2 }), "4 + カード+2 = 6");
  assert.equal(rolledLabel({ value: 11, values: [4, 5], bonus: 2 }), "4 + 5 + カード+2 = 11");
  // values が無い古い形でも落ちない
  assert.equal(rolledLabel({ value: 3 }), "3 が出た");
});

test("カードの文言", () => {
  assert.equal(cardsLabel(2), "カード 2枚");
  assert.equal(drewLabel({ label: "+2マス" }), "カードをひいた  +2マス");
  assert.equal(guardLabel(300), "おまもり  300円 払わずにすんだ");
  assert.equal(overLabel(1), "カードを 1枚 すててください");
});

test("一覧の1行は位置と枚数を同じ関数が作る", () => {
  assert.equal(statLabel({ pos: 5, cards: 0 }), "5 マス");
  assert.equal(statLabel({ pos: 5, cards: 2 }), "5 マス / カード 2枚");
  assert.equal(statLabel({ pos: 9, resting: true, cards: 1 }), "9 マス / 一回休み / カード 1枚");
});

test("カードの種類ごとに印と色が決まる", () => {
  assert.equal(cardStyle("advance").cls, "advance");
  assert.equal(cardStyle("double").cls, "double");
  assert.equal(cardStyle("guard").cls, "guard");
  // 知らない種類でも札が描ける
  assert.ok(cardStyle("なにか").mark);
});

test("使ったカードの効果は手番の表示に出る", () => {
  assert.equal(armedLabel({ dice: 1, bonus: 0 }), "");
  assert.equal(armedLabel({ dice: 2, bonus: 0 }), "サイコロ2個");
  assert.equal(armedLabel({ dice: 1, bonus: 3 }), "+3マス");
  assert.equal(armedLabel({ dice: 2, bonus: 2 }), "サイコロ2個・+2マス");
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

test("半分の位置を通過したことも他の人に見える", () => {
  assert.deepEqual(
    rollSummary({ name: "アオイ", value: 10, from: 10, to: 20, effect: null, half: 500 }),
    ["アオイ  10", "10 → 20", "はんぶん通過 +500円"],
  );
});

test("おまもりが止めた支払いは他の人にも見える", () => {
  assert.deepEqual(
    rollSummary({ name: "アオイ", value: 3, from: 2, to: 5, effect: "はらう -100円", blocked: 100 }),
    ["アオイ  3", "2 → 5", "はらう -100円", "おまもり  100円 払わずにすんだ"],
  );
});

test("何のカードをひいたかはまとめに出ない", () => {
  // 持ち主以外の画面が使う関数。マスの名前までしか出さない
  const lines = rollSummary({ name: "アオイ", value: 1, from: 0, to: 1, effect: "カードをひく", drew: true });
  assert.deepEqual(lines, ["アオイ  1", "0 → 1", "カードをひく"]);
});

test("マスの種類ごとに色と音が決まる", () => {
  assert.equal(effectStyle("forward").cls, "fw");
  assert.equal(effectStyle("back").cls, "bk");
  assert.equal(effectStyle("rest").cls, "rs");
  assert.equal(effectStyle("gain").cls, "gn");
  assert.equal(effectStyle("lose").cls, "ls");
  assert.equal(effectStyle("card").cls, "cd");
  // 知らない種類でも落ちない
  assert.ok(Array.isArray(effectStyle("なにか").chime));
  assert.equal(SALARY_CHIME.length, 2);
  assert.equal(FINISH_CHIME.length, 3);
  assert.ok(Array.isArray(CARD_CHIME) && Array.isArray(GUARD_CHIME) && Array.isArray(HALFWAY_CHIME));
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

/* ---------- 盤を輪に並べる ---------- */

test("30マスは横10×縦7の外周にちょうど収まる", () => {
  assert.deepEqual(ringSize(30), { cols: 10, rows: 7 });
});

test("輪の配置は外周だけを重ならずに一周する", () => {
  const { cols, rows } = ringSize(30);
  const cells = ringLayout(30);

  assert.equal(cells.length, 30);
  assert.equal(new Set(cells.map((c) => `${c.row},${c.col}`)).size, 30);   // 重ならない
  for (const c of cells) {
    assert.ok(c.row === 1 || c.row === rows || c.col === 1 || c.col === cols, "内側に入っている");
  }
  // 隣り合うマス（最後→最初も含む）は上下左右に1つずれた位置にある
  for (let i = 0; i < 30; i++) {
    const a = cells[i], b = cells[(i + 1) % 30];
    assert.equal(Math.abs(a.row - b.row) + Math.abs(a.col - b.col), 1, `${i} と次のマスが離れている`);
  }
});

test("スタートは左上で、時計回りに並ぶ", () => {
  const cells = ringLayout(30);
  assert.deepEqual(cells[0], { row: 1, col: 1 });
  assert.deepEqual(cells[9], { row: 1, col: 10 });    // 上の辺の右端
  assert.deepEqual(cells[10], { row: 2, col: 10 });   // 右の辺へ下る
  assert.deepEqual(cells[29], { row: 2, col: 1 });    // 最後はスタートの真下
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

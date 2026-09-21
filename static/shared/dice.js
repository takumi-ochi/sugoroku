/* 3Dサイコロ。PC画面とスマホで同じものを使う。
 * 見た目は shared/dice.css 側にある。
 */

import { rattle, thud } from "./sound.js";
import { sleep } from "./anim.js";

// 3x3のどの位置に目を打つか
const PIPS = {
  1: [4],
  2: [0, 8],
  3: [0, 4, 8],
  4: [0, 2, 6, 8],
  5: [0, 2, 4, 6, 8],
  6: [0, 2, 3, 5, 6, 8],
};

// その面を手前に向けるための、立方体そのものの回転
const FACE = { 1: [0, 0], 2: [-90, 0], 3: [0, -90], 4: [0, 90], 5: [90, 0], 6: [0, 180] };

export const ROLL_MS = 1000;

/** el（.cube）の中に6面を作り、操作用の関数を返す。
 *
 * silent を true にすると音を鳴らさない。カードでサイコロが2個になったとき、
 * 2個目をこれで作る。両方が鳴らすと転がる音が二重になって濁る。
 */
export function createDice(el, silent = false) {
  for (const v of [1, 2, 3, 4, 5, 6]) {
    const face = document.createElement("div");
    face.className = "face f" + v;
    for (let i = 0; i < 9; i++) {
      const pip = document.createElement("div");
      pip.className = "pip" + (PIPS[v].includes(i) ? "" : " hide");
      face.append(pip);
    }
    el.append(face);
  }

  // 回すたびに足していく。同じ目が続いても必ず回転させるため。
  let spins = 0;

  function show(value, animate) {
    const [x, y] = FACE[value] || FACE[1];
    // 2個目は直前まで display:none だった。表示にした同じ瞬間に transform を変えると、
    // ブラウザは「変わった」と気づけず、転がらずに最終の面へ飛ぶ。
    // 先に読み取りで描画を確定させて、いまの向きから回り始めさせる。
    if (animate) void el.offsetWidth;
    el.style.transition = animate ? `transform ${ROLL_MS}ms cubic-bezier(.15,.85,.25,1)` : "none";
    el.style.transform = `rotateX(${x + 360 * spins}deg) rotateY(${y + 360 * spins}deg)`;
  }

  async function roll(value) {
    if (!silent) rattle();
    el.classList.add("shake");
    spins += 3 + Math.floor(Math.random() * 2);
    show(value, true);
    await sleep(ROLL_MS);
    el.classList.remove("shake");
    if (!silent) thud();
    await sleep(120);
  }

  show(1, false);
  return { show, roll };
}

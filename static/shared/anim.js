/* 進行の待ちと、1マスずつの移動。 */

export const STEP_MS = 150;      // 1マス進むのにかける時間
export const RESULT_MS = 500;    // 出目を見せてから動き出すまでの間
export const EFFECT_MS = 480;    // マスの効果を見せる間

export function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/** from から to まで1マスずつ進む。
 *
 * 各マスで onStep(位置, 向き, 何歩目) を呼ぶ。描画と音は呼び出し側の仕事。
 * 戻り値は to（= サーバーが言っている位置）なので、ここを使えばズレない。
 */
export async function walk(from, to, onStep, delay = STEP_MS) {
  let pos = from;
  const dir = to > pos ? 1 : -1;
  let i = 0;
  while (pos !== to) {
    pos += dir;
    onStep(pos, dir, i++);
    await sleep(delay);
  }
  return to;
}

/** 受け取った状態を順に処理する。演出中に届いた分は待たせる。
 *
 * 溜まりすぎたら最新だけ残す（端末が遅いときに延々と遅れ続けないように）。
 */
export function createQueue(handler, maxPending = 3) {
  let queue = [];
  let running = false;

  async function pump() {
    running = true;
    try {
      while (queue.length) await handler(queue.shift());
    } finally {
      running = false;
    }
  }

  return {
    push(item) {
      queue.push(item);
      if (queue.length > maxPending) queue = [queue[queue.length - 1]];
      if (!running) pump();
    },
    get busy() {
      return running;
    },
  };
}

/* 画面に出す文字はすべてここで作る。
 *
 * PC画面とスマホで別々に文字列を組み立てると、片方だけ直して食い違う。
 * 実際にそれが起きたので、表示の作り方はこのファイルだけに置く。
 */

/** 参加者一覧やスマホの見出しに出す、いまの位置。 */
export function posLabel(player) {
  if (player.rank) return `${player.rank}位 ゴール`;
  if (player.resting) return `${player.pos} マス / 一回休み`;
  return `${player.pos} マス`;
}

/** 移動の表示。from と to は必ずサーバーから来た値を渡すこと。 */
export function moveLabel(from, to) {
  return `${from} → ${to}`;
}

/** 出目が確定したときの表示。 */
export function rolledLabel(value) {
  return `${value} が出た`;
}

/** ゴールしたときの表示。 */
export function goalLabel(rank) {
  return `ゴール！ ${rank}位`;
}

/** 他の人の手番を眺めているときの、1行まとめ。 */
export function rollSummary(roll) {
  const lines = [`${roll.name}  ${roll.value}`, moveLabel(roll.from, roll.to)];
  if (roll.effect) lines.push(roll.effect);
  if (roll.rank) lines.push(goalLabel(roll.rank));
  return lines;
}

/* ---- マスの種類ごとの見た目と音 ---- */

const SQUARE = {
  forward: { cls: "fw", color: "#81c784", chime: [660, 990] },
  back: { cls: "bk", color: "#ff8a90", chime: [520, 390] },
  rest: { cls: "rs", color: "#ffd54f", chime: [500, 500] },
};

export function effectStyle(kind) {
  return SQUARE[kind] || { cls: "", color: "#ffd54f", chime: [500, 500] };
}

export const GOAL_CHIME = [660, 880, 1320];

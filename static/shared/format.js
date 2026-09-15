/* 画面に出す文字はすべてここで作る。
 *
 * PC画面とスマホで別々に文字列を組み立てると、片方だけ直して食い違う。
 * 実際にそれが起きたので、表示の作り方はこのファイルだけに置く。
 */

/** 参加者一覧やスマホの見出しに出す、いまの位置。 */
export function posLabel(player) {
  if (player.resting) return `${player.pos} マス / 一回休み`;
  return `${player.pos} マス`;
}

/** 金額。3桁ごとにカンマを入れる。 */
export function moneyLabel(amount) {
  return `${String(amount).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}円`;
}

/** 増減の表示。0 以上は + を付ける。 */
export function deltaLabel(amount) {
  return amount < 0 ? `-${moneyLabel(-amount)}` : `+${moneyLabel(amount)}`;
}

/** 順位。 */
export function rankLabel(rank) {
  return `${rank}位`;
}

/** 何ターン目か。 */
export function roundLabel(round, rounds) {
  return `ターン ${round} / ${rounds}`;
}

/** スタートを通過したときの表示。 */
export function salaryLabel(amount) {
  return `スタート通過 ${deltaLabel(amount)}`;
}

/** 移動の表示。from と to は必ずサーバーから来た値を渡すこと。 */
export function moveLabel(from, to) {
  return `${from} → ${to}`;
}

/** 出目が確定したときの表示。 */
export function rolledLabel(value) {
  return `${value} が出た`;
}

/** 順位の順に並べる。同じ順位なら参加順のまま。 */
export function byRank(players) {
  return [...players].sort((a, b) => a.rank - b.rank);
}

/** 優勝者（1位が複数なら全員）の名前。 */
export function winnersLabel(players) {
  return players.filter((p) => p.rank === 1).map((p) => p.name).join("・");
}

/** 他の人の手番を眺めているときの、1行まとめ。 */
export function rollSummary(roll) {
  const lines = [`${roll.name}  ${roll.value}`, moveLabel(roll.from, roll.to)];
  if (roll.salary) lines.push(salaryLabel(roll.salary));
  if (roll.effect) lines.push(roll.effect);
  return lines;
}

/* ---- マスの種類ごとの見た目と音 ---- */

const SQUARE = {
  forward: { cls: "fw", color: "#81c784", chime: [660, 990] },
  back: { cls: "bk", color: "#ff9d5c", chime: [520, 390] },
  rest: { cls: "rs", color: "#ba8cff", chime: [500, 500] },
  gain: { cls: "gn", color: "#ffd54f", chime: [784, 1047] },
  lose: { cls: "ls", color: "#ff6b7a", chime: [440, 330] },
};

export function effectStyle(kind) {
  return SQUARE[kind] || { cls: "", color: "#ffd54f", chime: [500, 500] };
}

export const SALARY_CHIME = [880, 1175];
export const FINISH_CHIME = [660, 880, 1320];

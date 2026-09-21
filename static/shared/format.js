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

/** 何ターン目か。数字だけ（スマホの大きい表示用）。 */
export function roundValue(round, rounds) {
  return `${round} / ${rounds}`;
}

/** 何ターン目か。見出し付き。 */
export function roundLabel(round, rounds) {
  return `ターン ${roundValue(round, rounds)}`;
}

/** 何人中か（順位に添える）。 */
export function playersLabel(count) {
  return `${count}人中`;
}

/** スタートを通過したときの表示。 */
export function salaryLabel(amount) {
  return `スタート通過 ${deltaLabel(amount)}`;
}

/** コースの半分を通過したときの表示。ぴったり止まらなくてももらえる。 */
export function halfwayLabel(amount) {
  return `はんぶん通過 ${deltaLabel(amount)}`;
}

/** 移動の表示。from と to は必ずサーバーから来た値を渡すこと。 */
export function moveLabel(from, to) {
  return `${from} → ${to}`;
}

/** 出目が確定したときの表示。
 *
 * サイコロ2個やカードで足したぶんがあるときは、足し算をそのまま見せる。
 * 引数は last_roll まるごと（value だけでは2個ふったことが分からない）。
 */
export function rolledLabel(roll) {
  const parts = [...(roll.values || [roll.value])];
  if (roll.bonus) parts.push(`カード+${roll.bonus}`);
  if (parts.length === 1) return `${roll.value} が出た`;
  return `${parts.join(" + ")} = ${roll.value}`;
}

/** 手札の枚数。0枚のときは呼ばない（呼び出し側で出し分ける）。 */
export function cardsLabel(count) {
  return `カード ${count}枚`;
}

/** 参加者一覧の1行に添える、位置と手札の枚数。持っていないときは位置だけ。 */
export function statLabel(player) {
  return player.cards ? `${posLabel(player)} / ${cardsLabel(player.cards)}` : posLabel(player);
}

/** カードをひいたときの表示。中身が見えるのは持ち主の画面だけ。 */
export function drewLabel(card) {
  return `カードをひいた  ${card.label}`;
}

/** おまもりで支払いを無効にしたときの表示。 */
export function guardLabel(amount) {
  return `おまもり  ${moneyLabel(amount)} 払わずにすんだ`;
}

/** カードを使って、次にふるときに効くぶん。何も無ければ空文字。 */
export function armedLabel(player) {
  const parts = [];
  if (player.dice > 1) parts.push(`サイコロ${player.dice}個`);
  if (player.bonus) parts.push(`+${player.bonus}マス`);
  return parts.join("・");
}

/** 手札が上限を超えているときの催促。 */
export function overLabel(count) {
  return `カードを ${count}枚 すててください`;
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
  if (roll.half) lines.push(halfwayLabel(roll.half));
  if (roll.effect) lines.push(roll.effect);
  if (roll.blocked) lines.push(guardLabel(roll.blocked));
  return lines;
}

/* ---- マスの種類ごとの見た目と音 ---- */

const SQUARE = {
  forward: { cls: "fw", color: "#81c784", chime: [660, 990] },
  back: { cls: "bk", color: "#ff9d5c", chime: [520, 390] },
  rest: { cls: "rs", color: "#ba8cff", chime: [500, 500] },
  gain: { cls: "gn", color: "#ffd54f", chime: [784, 1047] },
  lose: { cls: "ls", color: "#ff6b7a", chime: [440, 330] },
  card: { cls: "cd", color: "#79b8ff", chime: [700, 1050, 1400] },
};

export function effectStyle(kind) {
  return SQUARE[kind] || { cls: "", color: "#ffd54f", chime: [500, 500] };
}

/* ---- カードの種類ごとの印と色 ---- */

const CARD = {
  advance: { cls: "advance", mark: "⏩" },
  double: { cls: "double", mark: "🎲" },
  guard: { cls: "guard", mark: "🛡" },
};

export function cardStyle(kind) {
  return CARD[kind] || { cls: "", mark: "🂠" };
}

export const SALARY_CHIME = [880, 1175];
export const FINISH_CHIME = [660, 880, 1320];
export const CARD_CHIME = [740, 988, 1319];     // カードを使った
export const GUARD_CHIME = [1047, 784, 1047];   // おまもりが支払いを止めた
export const HALFWAY_CHIME = [660, 988, 1568];  // 半分の位置を通過した（大金なので目立つ音）

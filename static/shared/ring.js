/* 盤を輪（四角い外周）に並べるための配置計算。
 *
 * マス 0 を左上に置き、時計回りに 上の辺 → 右の辺 → 下の辺 → 左の辺 と並べる。
 * 最後のマスの次がマス 0 の隣に来るので、ぐるっと一周してスタートに戻る形になる。
 * マス数は偶数を想定（外周 = 2×横 + 2×縦 - 4）。
 */

/** マス数から、外周に並べるための横と縦のマス数を決める。横長になるようにする。 */
export function ringSize(size) {
  const half = Math.ceil((size + 4) / 2);       // 横 + 縦
  const cols = Math.max(2, Math.round(half * 0.6));
  return { cols, rows: Math.max(2, half - cols) };
}

/** 各マスの CSS grid 上の位置（1始まり）。戻り値は [{row, col}, ...]。 */
export function ringLayout(size) {
  const { cols, rows } = ringSize(size);
  const cells = [];
  for (let i = 0; i < size; i++) {
    let k = i;
    if (k < cols) { cells.push({ row: 1, col: k + 1 }); continue; }          // 上: 左→右
    k -= cols;
    if (k < rows - 2) { cells.push({ row: k + 2, col: cols }); continue; }  // 右: 上→下
    k -= rows - 2;
    if (k < cols) { cells.push({ row: rows, col: cols - k }); continue; }   // 下: 右→左
    k -= cols;
    cells.push({ row: rows - 1 - k, col: 1 });                             // 左: 下→上
  }
  return cells;
}

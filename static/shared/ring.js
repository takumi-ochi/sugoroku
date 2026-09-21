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

/* ---- くねくねした輪（2層目・3層目の盤） ----
 *
 * 四角い外周ではなく、うねりのある閉じた曲線に沿ってマスを並べる。
 * 曲線は 半径 r(θ) = 1 + amp × sin(waves × θ + phase) の楕円ぎみの輪で、
 * amp が大きいほど、waves が多いほどくねくねする。マスは曲線を道のりで等分して置くので、
 * 間隔はどこも同じ。最後のマスの次はマス 0 に戻り、ぐるっと輪になる（ループ）。
 * マス 0 は左上から始まり、時計回りに進む。
 */

/** 階層ごとのうねり方。1層目（四角い輪）には無い。 */
export const WINDING = {
  2: { waves: 5, amp: 0.2, phase: 0 },
  3: { waves: 7, amp: 0.16, phase: 0.6 },
};

/**
 * 盤（w × h ピクセル）にマスを並べる。
 * 戻り値: points = 各マスの中心 [{x, y}]、tile = マスの直径、spacing = 隣のマスとの間隔、
 *         path = 曲線そのもの（道を描くのに使う）。
 * マスは円形で、直径は間隔より小さい（どの向きでも重ならない）。
 */
export function windingLayout(size, w, h, shape) {
  const { waves, amp, phase = 0 } = shape;
  const N = 1600;
  let margin = 40;
  let dense = [], cum = [], spacing = 0, tile = 0;

  // 外周の長さでマスの大きさが決まり、マスの大きさで余白が決まる。数回まわして落ち着かせる。
  for (let pass = 0; pass < 5; pass++) {
    // まず単位の輪を作り、余白を除いた盤いっぱいに広げる（縦横を別々の倍率で引き伸ばしても、
    // 曲線は自分と交わらない）。
    const raw = [];
    for (let i = 0; i < N; i++) {
      const th = (i / N) * 2 * Math.PI - 0.75 * Math.PI;      // 左上から時計回り
      const r = 1 + amp * Math.sin(waves * th + phase);
      raw.push({ x: r * Math.cos(th), y: r * Math.sin(th) });
    }
    const xs = raw.map((q) => q.x), ys = raw.map((q) => q.y);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const sx = (w - 2 * margin) / (x1 - x0), sy = (h - 2 * margin) / (y1 - y0);
    dense = raw.map((q) => ({ x: margin + (q.x - x0) * sx, y: margin + (q.y - y0) * sy }));
    cum = [0];
    for (let i = 1; i <= N; i++) {
      const a = dense[i % N], b = dense[i - 1];
      cum.push(cum[i - 1] + Math.hypot(a.x - b.x, a.y - b.y));
    }
    spacing = cum[N] / size;
    tile = spacing * 0.92;
    margin = tile / 2 + 4;
  }

  const points = [];
  let j = 0;
  for (let k = 0; k < size; k++) {
    const target = k * spacing;
    while (j < N - 1 && cum[j + 1] <= target) j++;
    const seg = cum[j + 1] - cum[j] || 1;
    const t = (target - cum[j]) / seg;
    const a = dense[j], b = dense[(j + 1) % N];
    points.push({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
  }

  // 曲がりのきついところでは、道のりでは離れているマスどうしが近づくことがある。
  // どの2つの中心も直径より離れるように、マスを少し小さくする（縦横比によらず重ならない）。
  let nearest = Infinity;
  for (let a = 0; a < size; a++) {
    for (let b = a + 1; b < size; b++) {
      nearest = Math.min(nearest, Math.hypot(points[a].x - points[b].x, points[a].y - points[b].y));
    }
  }
  return { points, tile: Math.min(tile, nearest * 0.96), spacing, path: dense };
}

/* 効果音。音声ファイルは使わず WebAudio で合成する。
 *
 * ブラウザは画面を触るまで音を鳴らせない（iOSは特に厳しい）。
 * 参加ボタンやクリックの中で enable() を呼んで有効化すること。
 */

let ctx = null;
let noiseBuf = null;
let muted = false;

try {
  muted = localStorage.getItem("mute") === "1";
} catch (e) {
  muted = false;   // プライベートブラウズ等で localStorage が使えないことがある
}

/** 操作の中から呼ぶ。音を鳴らす準備をする。 */
export function enable() {
  if (!ctx) {
    try {
      ctx = new (window.AudioContext || window.webkitAudioContext)();
    } catch (e) {
      return null;
    }
    const len = Math.floor(ctx.sampleRate * 0.4);
    noiseBuf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  }
  if (ctx.state === "suspended") ctx.resume();
  return ctx;
}

function live() {
  const c = enable();
  return muted ? null : c;
}

export function isMuted() {
  return muted;
}

export function toggleMute() {
  muted = !muted;
  try { localStorage.setItem("mute", muted ? "1" : "0"); } catch (e) { /* 保存できなくても続行 */ }
  if (!muted) stepTone(1, 0);
  return muted;
}

/** サイコロを振る音。ノイズを削った短い音を連ねる。 */
export function rattle() {
  const c = live(); if (!c) return;
  const t0 = c.currentTime;
  for (let i = 0; i < 6; i++) {
    const t = t0 + i * 0.105 + Math.random() * 0.02;
    const src = c.createBufferSource(); src.buffer = noiseBuf;
    const bp = c.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1400 + Math.random() * 2200;
    bp.Q.value = 1.4;
    const g = c.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.3, t + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.085);
    src.connect(bp).connect(g).connect(c.destination);
    src.start(t); src.stop(t + 0.1);
  }
}

/** 出目が決まって止まる音。 */
export function thud() {
  const c = live(); if (!c) return;
  const t = c.currentTime;
  const o = c.createOscillator(); o.type = "sine";
  o.frequency.setValueAtTime(220, t);
  o.frequency.exponentialRampToValueAtTime(65, t + 0.2);
  const g = c.createGain();
  g.gain.setValueAtTime(0.4, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + 0.26);
  o.connect(g).connect(c.destination);
  o.start(t); o.stop(t + 0.28);
}

/** 1マス進む音。進むほど高く、戻るほど低くなる。 */
export function stepTone(dir, i) {
  const c = live(); if (!c) return;
  const t = c.currentTime;
  const o = c.createOscillator(); o.type = "triangle";
  o.frequency.value = dir > 0 ? 620 * Math.pow(1.06, i) : 400 / Math.pow(1.06, i);
  const g = c.createGain();
  g.gain.setValueAtTime(0.2, t);
  g.gain.exponentialRampToValueAtTime(0.001, t + 0.11);
  o.connect(g).connect(c.destination);
  o.start(t); o.stop(t + 0.13);
}

/** マスの効果やゴールの知らせ。 */
export function chime(freqs, gap = 0.12) {
  const c = live(); if (!c) return;
  freqs.forEach((f, i) => {
    const t = c.currentTime + i * gap;
    const o = c.createOscillator(); o.type = "triangle"; o.frequency.value = f;
    const g = c.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.26, t + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
    o.connect(g).connect(c.destination);
    o.start(t); o.stop(t + 0.32);
  });
}

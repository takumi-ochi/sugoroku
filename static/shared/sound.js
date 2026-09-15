/* 効果音。音声ファイルは使わず WebAudio で合成する。
 *
 * ブラウザは画面を触るまで音を鳴らせない（iOSは特に厳しい）。読み込み直後の
 * AudioContext は "suspended" で、そのままでは無音のまま進む。
 *
 * 以前はPC画面で最初の pointerdown だけを once で待っていたため、
 * スマホから開始してPCを一度も触らないと無音のままだった
 * （リセットを押すと鳴り出すのがその症状）。いまは armEnable() で
 * 鳴るようになるまで何度でも待ち受ける。
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
    ctx.addEventListener("statechange", announce);
    const len = Math.floor(ctx.sampleRate * 0.4);
    noiseBuf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
  }
  if (ctx.state === "suspended") ctx.resume().catch(() => { /* 操作前は失敗する */ });
  return ctx;
}

/** いま実際に音が鳴る状態か。suspended のうちは鳴らない。 */
export function isReady() {
  return !!ctx && ctx.state === "running";
}

/* ---- 鳴るようになるまで待ち受ける ---- */

const GESTURES = ["pointerdown", "touchstart", "keydown", "click"];
const watchers = new Set();
let armed = false;

function attempt() {
  enable();
  announce();
}

function onVisible() {
  if (!document.hidden) attempt();   // タブに戻ったときに止まっていたら鳴らし直す
}

function disarm() {
  if (!armed) return;
  armed = false;
  GESTURES.forEach((e) => window.removeEventListener(e, attempt, true));
  document.removeEventListener("visibilitychange", onVisible);
}

function announce() {
  const ready = isReady();
  if (ready) disarm();               // 鳴るようになったら待ち受けをやめる
  for (const fn of watchers) fn(ready);
}

/** 画面のどこを触っても音を有効化する。onChange(ready) で状態を受け取れる。
 *
 * 一度きりにしない。最初の操作で有効化できなくても、次の操作でまた試す。
 */
export function armEnable(onChange) {
  if (onChange) {
    watchers.add(onChange);
    onChange(isReady());
  }
  if (!armed) {
    armed = true;
    // capture で拾う。ボタン側が止めても有効化だけは行う。
    GESTURES.forEach((e) => window.addEventListener(e, attempt, true));
    document.addEventListener("visibilitychange", onVisible);
  }
  attempt();                          // 自動再生が許可されていればこれだけで鳴る
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
  announce();     // 表示（音が鳴らない旨の案内）を出し直す
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

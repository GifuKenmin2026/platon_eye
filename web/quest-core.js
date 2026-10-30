// 探究モードの計算（画面に触らない純粋な関数）
export const DEFAULT_LIMIT = 90;

export function remaining(startMs, nowMs, limitSec) {
  return Math.max(0, Math.ceil(limitSec - (nowMs - startMs) / 1000));
}

// シャッターを押した時点で時間が残っていれば有効
export function shotCounts(startMs, shotMs, limitSec) {
  return shotMs - startMs < limitSec * 1000;
}

export function elapsedAtShot(startMs, shotMs) {
  return Math.round((shotMs - startMs) / 100) / 10;
}

export function pickQuest(quests, lastWord, rand = Math.random) {
  const pool = quests.length > 1 ? quests.filter((q) => q.word !== lastWord) : quests;
  return pool[Math.floor(rand() * pool.length) % pool.length];
}

export function limitFromUrl(search) {
  const n = Number(new URLSearchParams(search).get("limit"));
  return Number.isInteger(n) && n >= 1 && n <= 600 ? n : DEFAULT_LIMIT;
}

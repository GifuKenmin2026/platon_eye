// 撮影 → 分析中 → 単語を描く、の共通の流れと、結果の表示
import { $, show } from "./ui.js";
import { captureJpeg } from "./camera.js";
import { composeIdea } from "./compose.js";
import * as api from "./api.js";
import * as db from "./db.js";

export const state = { current: null, busy: false, failUrl: null };

function release(cur) {
  if (!cur) return;
  URL.revokeObjectURL(cur.ideaUrl);
  URL.revokeObjectURL(cur.originalUrl);
}

// 撮影して分析する。送信中は何もしない（連打しても1回だけ）。
// 戻り値：{ result, ideaBlob, ideaUrl, originalBlob, originalUrl, shotAt } / 送信中なら null
export async function analyze({ quest } = {}) {
  if (state.busy) return null;
  state.busy = true;
  try {
    const shotAt = performance.now();
    const originalBlob = await captureJpeg($("#camera"));
    const originalUrl = URL.createObjectURL(originalBlob);
    $("#analyzing .analyzing-photo").src = originalUrl;
    show("analyzing");
    try {
      const result = await api.transmute(originalBlob, quest);
      const { blob: ideaBlob, url: ideaUrl } = await composeIdea(result.erased, result.idea.word, result.anchor);
      release(state.current);
      state.current = { result, ideaBlob, ideaUrl, originalBlob, originalUrl, shotAt };
      return state.current;
    } catch (e) {
      // 失敗画面で「影」として見せるため、写真はすぐ捨てずに次の失敗まで残す
      if (state.failUrl) URL.revokeObjectURL(state.failUrl);
      state.failUrl = originalUrl;
      e.photoUrl = originalUrl;
      throw e;
    }
  } finally {
    state.busy = false;
  }
}

// いまの結果を図鑑に保存する。extra は探究の印 { questWord, questSeconds }
// 同じ結果を2回押しで2枚保存しないよう、保存中の約束をそのまま返す
export function saveCurrent(extra = {}) {
  const cur = state.current;
  if (!cur) return Promise.resolve(null);
  cur.saving ??= (async () => {
    const { idea, label, mode } = cur.result;
    return db.addIdea({
      word: idea.word, reading: idea.reading, greek: idea.greek, greekReading: idea.greek_reading,
      definition: idea.definition, participation: idea.participation,
      label, mode, idea: cur.ideaBlob, original: cur.originalBlob,
      thumb: await shrink(cur.ideaUrl, 400), ...extra,
    });
  })();
  cur.saving.catch(() => { cur.saving = null; });
  return cur.saving;
}

// 画像を長辺 maxSide の JPEG にする（図鑑の札・ランキング用）
export async function shrink(url, maxSide) {
  const img = new Image();
  img.src = url;
  await img.decode();
  const r = Math.min(1, maxSide / Math.max(img.naturalWidth, img.naturalHeight));
  const c = document.createElement("canvas");
  c.width = Math.round(img.naturalWidth * r);
  c.height = Math.round(img.naturalHeight * r);
  c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
  return new Promise((resolve) => c.toBlob(resolve, "image/jpeg", 0.85));
}

// 写真2枚と辞書の札を container に描く
export function renderReading(container, { idea, originalUrl, ideaUrl }) {
  container.replaceChildren($("#tpl-reading").content.cloneNode(true));
  $(".original", container).src = originalUrl;
  $(".idea", container).src = ideaUrl;
  $(".headword", container).textContent = `【${idea.word}】`;
  $(".reading", container).textContent = idea.reading || "";
  $(".greek", container).textContent = idea.greek || "";
  $(".greek-reading", container).textContent = idea.greekReading ?? idea.greek_reading ?? "";
  $(".definition", container).textContent = idea.definition;
  $(".participation", container).textContent = idea.participation || "";
}

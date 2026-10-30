// 画面の切り替え・キー操作・ボタン操作の共通部分
export const keymap = {};   // keymap[screenId] = { "Space": fn, "z": fn, ... }
export const actions = {};  // data-action="name" のボタンが押された時
export const hooks = {};    // hooks[screenId] = { enter(), leave() }

let current = null;
let errorBack = "title";

export const currentScreen = () => current;
export const $ = (sel, root = document) => root.querySelector(sel);

export function show(id) {
  const prev = current;
  if (prev && prev !== id) hooks[prev]?.leave?.(id);
  for (const s of document.querySelectorAll(".screen")) {
    // 詳しい表示は図鑑の上に重ねる
    s.hidden = !(s.id === id || (id === "detail" && s.id === "scroll"));
  }
  current = id;
  hooks[id]?.enter?.(prev);
  const focusable = $(`#${id} [autofocus]`) || $(`#${id} button:not([disabled])`);
  focusable?.focus({ preventScroll: true });
}

export function showError(message, back = "title") {
  errorBack = back;
  $("#error .error-message").textContent = message;
  show("error");
}

// イデア化の失敗：撮った写真を「洞窟の壁の影」として見せる。何かキー・クリックで back へ戻る
export function showIdeaFail(message, back = "observe", photoUrl = "") {
  errorBack = back;
  $("#idea-fail .idea-fail-reason").textContent = message ? `理由：${message}` : "";
  const img = $("#idea-fail .idea-fail-photo");
  img.hidden = !photoUrl;
  if (photoUrl) img.src = photoUrl;
  show("idea-fail");
}

const isDismissScreen = () => current === "error" || current === "idea-fail";

function keyName(e) {
  if (e.key === " ") return "Space";
  const base = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  return e.shiftKey && base === "Delete" ? "Shift+Delete" : base;
}

document.addEventListener("keydown", (e) => {
  if (e.target instanceof HTMLSelectElement) return;
  // 文字を打っている間は、Esc 以外のキー操作を効かせない
  if (e.target instanceof HTMLInputElement && e.key !== "Escape") return;
  if (isDismissScreen()) {
    e.preventDefault();
    if (!e.repeat && !["Shift", "Control", "Alt", "Meta"].includes(e.key)) show(errorBack);
    return;
  }
  const map = keymap[current];
  const fn = map?.[keyName(e)] ?? (["Shift", "Control", "Alt", "Meta"].includes(e.key) ? null : map?.["*"]);
  if (fn) {
    e.preventDefault();
    if (!e.repeat) fn(e);
  }
});

document.addEventListener("click", (e) => {
  if (isDismissScreen()) {
    show(errorBack);
    return;
  }
  const el = e.target.closest("[data-action]");
  if (el && !el.disabled) actions[el.dataset.action]?.(el, e);
});

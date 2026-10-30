// プラトンの眼：入口とタイトル・観測モード
import { $, actions, hooks, keymap, show, showError, showIdeaFail } from "./ui.js";
import { CameraError, listCameras, saveCameraId, savedCameraId, startCamera, stopCamera } from "./camera.js";
import * as api from "./api.js";
import { analyze, renderReading, saveCurrent } from "./flow.js";
import { openScroll } from "./scroll.js";
import { loadQuests, stopQuest, useCamera } from "./quest.js";
import "./analyzing.js";

export { show, showError, keymap };

const video = $("#camera");

// カメラ映像を、その画面の枠へ移して映す
export async function mountCamera(screenId) {
  const slot = $(`#${screenId} .cam-slot`);
  if (video.parentElement !== slot) slot.appendChild(video);
  try {
    await startCamera(video);
    refreshCameraList();
    return true;
  } catch (e) {
    showError(e instanceof CameraError ? e.message : "カメラを起動できませんでした。", "title");
    return false;
  }
}

async function refreshCameraList() {
  const select = $("#camera-select");
  const saved = savedCameraId();
  const cams = await listCameras().catch(() => []);
  select.replaceChildren(new Option("既定のカメラ", ""), ...cams.map((c) => new Option(c.label, c.deviceId)));
  select.value = cams.some((c) => c.deviceId === saved) ? saved : "";
}

// ---------------------------------------------------------------- タイトル
keymap.title = {
  "1": () => actions.observe(),
  "2": () => actions.quest?.(),
  z: () => actions.scroll?.(),
  "Shift+Delete": () => actions["clear-records"]?.(),
};
actions.title = () => show("title");
actions.observe = () => show("observe");
hooks.title = { enter: () => { stopQuest(); stopCamera(); } };
useCamera(mountCamera);

$("#camera-select").addEventListener("change", (e) => {
  saveCameraId(e.target.value);
  stopCamera();
});

// ---------------------------------------------------------------- 観測：撮影
actions.shoot = async () => {
  try {
    const cur = await analyze();
    if (!cur) return;
    renderReading($("#result .reading-room"), { idea: cur.result.idea, originalUrl: cur.originalUrl, ideaUrl: cur.ideaUrl });
    show("result");
  } catch (e) {
    if (e instanceof api.ApiError) return showIdeaFail(e.message, "observe", e.photoUrl);
    showError(e.message || "観測できませんでした。もう一度撮ってください。", "observe");
  }
};
keymap.observe = {
  Space: () => actions.shoot(),
  Enter: () => actions.shoot(),
  Escape: () => show("title"),
  z: () => actions.scroll?.(),
};
hooks.observe = { enter: () => mountCamera("observe") };

// ---------------------------------------------------------------- 観測：結果
actions.discard = () => show("observe");
actions.save = async () => {
  try {
    openScroll(await saveCurrent());
  } catch {
    showError("図鑑に保存できませんでした。ブラウザの空き容量を確認してください。", "observe");
  }
};
keymap.result = {
  y: () => actions.save?.(),
  n: () => actions.discard(),
};

// プラトンの写真は web/img/plato.jpg があるときだけ出す
{
  const fig = $("#title .plato");
  const img = $("img", fig);
  const reveal = () => { fig.hidden = false; };
  if (img.complete && img.naturalWidth) reveal();
  else img.addEventListener("load", reveal, { once: true });
}

// ---------------------------------------------------------------- 起動
(async () => {
  navigator.storage?.persist?.().catch(() => {});  // 図鑑がブラウザに消されにくくする
  const st = await api.status();
  $("#mode-badge").hidden = st.mode !== "demo";
  refreshCameraList();
  await loadQuests();
  show("title");
})();

// カメラ：起動・切り替え・撮影
const STORE_KEY = "platon.camera";
const NOT_FOUND = "カメラが見つかりません。USB の差し込みと、ブラウザのカメラ許可を確認してください。";

export class CameraError extends Error {}

export function cameraMessage(errorName) {
  if (errorName === "NotReadableError" || errorName === "AbortError") {
    return "カメラを開けません。他のアプリ（カメラ、Teams など）がカメラを使っていないか確認してください。";
  }
  if (errorName === "NotAllowedError" || errorName === "SecurityError") {
    return "カメラの使用が許可されていません。アドレスバー左の鍵マークから、カメラを「許可」にしてください。";
  }
  return NOT_FOUND;
}

let stream = null;
let activeId = null;

export function savedCameraId() {
  try { return localStorage.getItem(STORE_KEY) || ""; } catch { return ""; }
}

export function saveCameraId(id) {
  try { id ? localStorage.setItem(STORE_KEY, id) : localStorage.removeItem(STORE_KEY); } catch { /* 保存できなくても動く */ }
}

export async function listCameras() {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices
    .filter((d) => d.kind === "videoinput")
    .map((d, i) => ({ deviceId: d.deviceId, label: d.label || `カメラ ${i + 1}` }));
}

async function open(deviceId) {
  const video = { width: { ideal: 1280 }, height: { ideal: 720 } };
  if (deviceId) video.deviceId = { exact: deviceId };
  return navigator.mediaDevices.getUserMedia({ video, audio: false });
}

export async function startCamera(video, deviceId = savedCameraId()) {
  if (stream && stream.active && activeId === (deviceId || "")) {
    if (video.srcObject !== stream) video.srcObject = stream;
    await video.play().catch(() => {});
    return;
  }
  stopCamera();
  if (!navigator.mediaDevices?.getUserMedia) throw new CameraError(NOT_FOUND);
  try {
    stream = await open(deviceId);
  } catch (e) {
    // 覚えていたカメラが外れていたら、既定のカメラで試す
    if (!deviceId || e?.name !== "OverconstrainedError" && e?.name !== "NotFoundError") {
      throw new CameraError(cameraMessage(e?.name));
    }
    try { stream = await open(""); deviceId = ""; } catch (e2) { throw new CameraError(cameraMessage(e2?.name)); }
  }
  activeId = deviceId || "";
  video.srcObject = stream;
  await video.play().catch(() => {});
  if (!video.videoWidth) {
    await new Promise((resolve) => video.addEventListener("loadedmetadata", resolve, { once: true }));
  }
}

export function stopCamera() {
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
  activeId = null;
}

export async function captureJpeg(video, maxSide = 1600) {
  const w = video.videoWidth, h = video.videoHeight;
  if (!w || !h) throw new CameraError(NOT_FOUND);
  const r = Math.min(1, maxSide / Math.max(w, h));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(w * r);
  canvas.height = Math.round(h * r);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new CameraError(NOT_FOUND))), "image/jpeg", 0.92));
}

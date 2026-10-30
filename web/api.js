// サーバーとの通信
const SERVER_DOWN = "サーバーが動いていません。start.bat を起動してください。";

export class ApiError extends Error {}

export async function status() {
  try {
    const res = await fetch("/api/status");
    return await res.json();
  } catch {
    return { mode: "unknown" };
  }
}

const TOO_SLOW = "時間がかかりすぎています。インターネット接続を確認して、もう一度撮ってください。";

export async function transmute(blob, quest, { timeoutMs = 100000 } = {}) {
  const url = "/api/transmute" + (quest ? `?quest=${encodeURIComponent(quest)}` : "");
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res, data;
  try {
    res = await fetch(url, { method: "POST", headers: { "Content-Type": "image/jpeg" }, body: blob, signal: ctrl.signal });
    data = await res.json();
  } catch (e) {
    throw new ApiError(e?.name === "AbortError" ? TOO_SLOW : SERVER_DOWN);
  } finally {
    clearTimeout(timer);
  }
  if (!data.ok) throw new ApiError(data.error || "処理できませんでした。もう一度撮ってください。");
  return data;
}

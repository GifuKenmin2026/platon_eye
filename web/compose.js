// 消えた場所に、イデアの単語を白い明朝で描く
const FONT = `"Shippori Mincho", "Yu Mincho", "YuMincho", "Hiragino Mincho ProN", "Noto Serif CJK JP", serif`;

export function wordFontSize(imgW, imgH, anchor, chars) {
  const short = Math.min(imgW, imgH);
  const n = Math.max(1, chars);
  const size = Math.min(short * 0.22, (anchor.w * imgW * 0.9) / n, anchor.h * imgH * 0.6);
  return Math.max(size, short * 0.06);
}

function loadImage(url) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("画像を表示できませんでした"));
    img.src = url;
  });
}

export async function composeIdea(erasedUrl, word, anchor) {
  const img = await loadImage(erasedUrl);
  const w = img.naturalWidth, h = img.naturalHeight;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(img, 0, 0);

  const chars = [...word].length;
  const size = wordFontSize(w, h, anchor, chars);
  const font = `600 ${size}px ${FONT}`;
  try { await document.fonts.load(font, word); } catch { /* 代わりの明朝で描く */ }

  ctx.font = font;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const half = ctx.measureText(word).width / 2;
  const margin = Math.min(w, h) * 0.04;
  const x = Math.min(Math.max(anchor.cx * w, half + margin), w - half - margin);
  const y = Math.min(Math.max(anchor.cy * h, size / 2 + margin), h - size / 2 - margin);

  ctx.shadowColor = "rgba(0, 0, 0, .45)";
  ctx.shadowBlur = Math.min(w, h) * 0.02;
  ctx.fillStyle = "#ffffff";
  ctx.fillText(word, x, y);

  const blob = await new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("画像を作れませんでした"))), "image/jpeg", 0.9));
  return { blob, url: URL.createObjectURL(blob) };
}

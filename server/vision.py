"""
画像処理（OpenCV）：写真の物をモザイクで覆う

  1. マスク：Gemini の輪郭ポリゴン → PNG マスク → GrabCut（ボックス）→ GrabCut（画面中央）
  2. 範囲：輪郭と物を囲む四角を合わせて少し広げた四角
  3. モザイク：範囲の中を、物の大きさに合わせたマスで塗り分ける
  4. 文字の位置：範囲の中央
"""
from __future__ import annotations

import base64

import cv2
import numpy as np


# ---------------------------------------------------------------- 入出力

class ImageDecodeError(ValueError):
    """送られてきたデータが画像として読めない"""


def decode_image(data: bytes) -> np.ndarray:
    img = None
    if data:
        try:
            img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        except cv2.error:
            img = None
    if img is None:
        raise ImageDecodeError("画像を読み込めませんでした")
    return img


def encode_jpeg(img: np.ndarray, quality: int = 90) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise ValueError("JPEG に変換できませんでした")
    return buf.tobytes()


def to_data_url(img: np.ndarray, quality: int = 90) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(encode_jpeg(img, quality)).decode("ascii")


def limit_size(img: np.ndarray, max_side: int) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= max_side:
        return img
    r = max_side / max(h, w)
    return cv2.resize(img, (round(w * r), round(h * r)), interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------- マスク

def parse_box(box_2d, w: int, h: int):
    """[ymin, xmin, ymax, xmax]（0-1000）→ (x0, y0, x1, y1)。使えなければ None"""
    try:
        y0, x0, y1, x1 = [float(v) for v in list(box_2d)[:4]]
    except (TypeError, ValueError):
        return None
    if len(list(box_2d)) < 4:
        return None
    y0, y1 = sorted((y0, y1))
    x0, x1 = sorted((x0, x1))
    clip = lambda v, size: int(round(min(max(v, 0.0), 1000.0) / 1000.0 * size))
    box = (clip(x0, w), clip(y0, h), clip(x1, w), clip(y1, h))
    if box[2] - box[0] < 2 or box[3] - box[1] < 2:
        return None
    return box


def _rect_iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area = lambda r: max(0.0, r[2] - r[0]) * max(0.0, r[3] - r[1])
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def polygon_mask(points, box, w: int, h: int):
    """
    ポリゴンの座標は「画像全体基準」と「ボックス内基準」のどちらでも来うる。
    両方で解釈し、ボックスとの重なりが大きい方を使う（0.3 未満なら None）。
    """
    try:
        pts = np.array([[float(p[0]), float(p[1])] for p in points], np.float64)
    except (TypeError, ValueError, IndexError):
        return None
    if len(pts) < 3:
        return None
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    candidates = [
        np.column_stack([pts[:, 0] / 1000 * w, pts[:, 1] / 1000 * h]),
        np.column_stack([x0 + pts[:, 0] / 1000 * bw, y0 + pts[:, 1] / 1000 * bh]),
    ]
    scored = [(_rect_iou((*c.min(axis=0), *c.max(axis=0)), box), c) for c in candidates]
    score, best = max(scored, key=lambda s: s[0])
    if score < 0.3:
        return None
    mask = np.zeros((h, w), np.uint8)
    cv2.fillPoly(mask, [np.round(best).astype(np.int32)], 255)
    return mask if cv2.countNonZero(mask) else None


def png_mask(data: str, box, w: int, h: int):
    """ボックス内の base64 PNG（data URL でも可）"""
    try:
        b64 = data.split(",", 1)[1] if data.startswith("data:") else data
        m = cv2.imdecode(np.frombuffer(base64.b64decode(b64, validate=False), np.uint8), cv2.IMREAD_GRAYSCALE)
    except Exception:
        return None
    if m is None:
        return None
    x0, y0, x1, y1 = box
    m = cv2.resize(m, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR)
    mask = np.zeros((h, w), np.uint8)
    mask[y0:y1, x0:x1] = np.where(m > 127, 255, 0).astype(np.uint8)
    return mask if cv2.countNonZero(mask) else None


def grabcut_mask(img: np.ndarray, box) -> np.ndarray:
    """ボックスの中から物の形を切り抜く。うまくいかなければボックスそのもの"""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    rect_mask = np.zeros((h, w), np.uint8)
    rect_mask[y0:y1, x0:x1] = 255

    scale = min(1.0, 480 / max(h, w))
    small = cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    sx0, sy0, sx1, sy1 = [int(v * scale) for v in box]
    px, py = max(1, (sx1 - sx0) // 40), max(1, (sy1 - sy0) // 40)
    rect = (sx0 + px, sy0 + py, max(4, sx1 - sx0 - 2 * px), max(4, sy1 - sy0 - 2 * py))
    gc = np.zeros(small.shape[:2], np.uint8)
    try:
        cv2.grabCut(small, gc, rect, np.zeros((1, 65)), np.zeros((1, 65)), 4, cv2.GC_INIT_WITH_RECT)
    except cv2.error:
        return rect_mask
    fg = np.isin(gc, (cv2.GC_FGD, cv2.GC_PR_FGD)).astype(np.uint8) * 255
    fg = cv2.resize(fg, (w, h), interpolation=cv2.INTER_NEAREST)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(fg)
    if n <= 1:
        return rect_mask
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    blob = np.where(labels == biggest, 255, 0).astype(np.uint8)
    contours, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(blob)
    cv2.drawContours(filled, contours, -1, 255, -1)
    if cv2.countNonZero(filled) < 0.12 * (x1 - x0) * (y1 - y0):
        return rect_mask
    return filled


def build_mask(img: np.ndarray, target: dict | None):
    """戻り値: (mask, mask_method)"""
    h, w = img.shape[:2]
    box = parse_box(target.get("box_2d"), w, h) if isinstance(target, dict) else None
    if box is None:
        center = (int(w * 0.2), int(h * 0.15), int(w * 0.8), int(h * 0.9))
        return grabcut_mask(img, center), "grabcut-center"

    raw = target.get("mask")
    if isinstance(raw, list):
        mask = polygon_mask(raw, box, w, h)
        if mask is not None:
            return mask, "gemini-polygon"
    elif isinstance(raw, str) and raw:
        mask = png_mask(raw, box, w, h)
        if mask is not None:
            return mask, "gemini-png"
    return grabcut_mask(img, box), "grabcut-box"


def expand_mask(mask: np.ndarray) -> np.ndarray:
    """取りこぼしと影を消すため少し太らせる"""
    k = max(5, int(round(max(mask.shape) * 0.018)) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    return cv2.dilate(cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel), kernel)


# ---------------------------------------------------------------- モザイク

def mosaic_block(w: int, h: int) -> int:
    """モザイクのマスの大きさ：物の長い辺の 1/12、最小 16px"""
    return max(16, round(max(w, h) / 12))


def mosaic_region(img: np.ndarray, mask: np.ndarray, box) -> tuple:
    """
    輪郭（太らせたマスク）と物を囲む四角を合わせ、少し広げた四角を返す。
    輪郭が物の一部しか取れていなくても、物全体が入るようにする。
    """
    h, w = img.shape[:2]
    xs0, ys0, xs1, ys1 = [], [], [], []
    ys, xs = np.nonzero(mask)
    if len(xs):
        xs0.append(xs.min()); ys0.append(ys.min()); xs1.append(xs.max() + 1); ys1.append(ys.max() + 1)
    if box:
        xs0.append(box[0]); ys0.append(box[1]); xs1.append(box[2]); ys1.append(box[3])
    if not xs0:
        return (int(w * 0.3), int(h * 0.3), int(w * 0.7), int(h * 0.7))
    pad = round(max(h, w) * 0.02)
    return (max(0, int(min(xs0)) - pad), max(0, int(min(ys0)) - pad),
            min(w, int(max(xs1)) + pad), min(h, int(max(ys1)) + pad))


def pixelate(img: np.ndarray, rect, block: int) -> np.ndarray:
    """rect の中を block 四方のマスに塗り分ける（マスは rect の左上から並ぶ）"""
    x0, y0, x1, y1 = rect
    out = img.copy()
    crop = img[y0:y1, x0:x1]
    ch, cw = crop.shape[:2]
    if ch == 0 or cw == 0:
        return out
    nx, ny = -(-cw // block), -(-ch // block)
    small = cv2.resize(crop, (nx, ny), interpolation=cv2.INTER_AREA)
    big = cv2.resize(small, (nx * block, ny * block), interpolation=cv2.INTER_NEAREST)
    out[y0:y1, x0:x1] = big[:ch, :cw]
    return out


# ---------------------------------------------------------------- 文字の位置

def anchor_of(mask: np.ndarray) -> dict:
    h, w = mask.shape[:2]
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return {"cx": 0.5, "cy": 0.5, "w": 0.4, "h": 0.4}
    dist = cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)
    _, _, _, (mx, my) = cv2.minMaxLoc(dist)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    return {
        "cx": round(float((mx + (x0 + x1) / 2) / 2 / w), 4),
        "cy": round(float((my + (y0 + y1) / 2) / 2 / h), 4),
        "w": round(float((x1 - x0) / w), 4),
        "h": round(float((y1 - y0) / h), 4),
    }


def erase_object(img: np.ndarray, target: dict | None) -> dict:
    """物を囲む四角い範囲をモザイクで覆う"""
    h, w = img.shape[:2]
    mask, method = build_mask(img, target)
    mask = expand_mask(mask)
    box = parse_box(target.get("box_2d"), w, h) if isinstance(target, dict) else None
    region = mosaic_region(img, mask, box)
    x0, y0, x1, y1 = region
    block = mosaic_block(x1 - x0, y1 - y0)
    area = np.zeros((h, w), np.uint8)
    area[y0:y1, x0:x1] = 255
    return {
        "erased": pixelate(img, region, block),
        "mask": area,
        "mask_method": method,
        "region": region,
        "block": block,
        "anchor": anchor_of(area),
        "coverage": round((x1 - x0) * (y1 - y0) / (w * h), 4),
    }

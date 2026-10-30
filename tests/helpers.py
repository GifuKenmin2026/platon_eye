"""テスト用の合成写真"""
import cv2
import numpy as np

W, H = 1280, 720
CAN = (560, 180, 720, 560)  # x0, y0, x1, y1


def synthetic_scene():
    """
    上が明るい壁、下が木目の机、中央に赤い缶。
    戻り値: (img, box_2d, polygon_full)
      box_2d       … [ymin, xmin, ymax, xmax] 0-1000
      polygon_full … 画像全体基準の [x, y] 0-1000
    """
    rng = np.random.default_rng(0)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    img = np.dstack([
        120 + 40 * np.sin(x / 37.0) + y * 0.05,
        90 + 30 * np.sin(x / 37.0 + 0.3) + y * 0.04,
        60 + 20 * np.sin(x / 41.0),
    ])
    img[:300] = (200, 205, 210)
    img += rng.normal(0, 4, img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)

    x0, y0, x1, y1 = CAN
    cv2.rectangle(img, (x0, y0), (x1, y1), (30, 40, 200), -1)  # BGR: 赤

    nx = lambda v: round(v / W * 1000)
    ny = lambda v: round(v / H * 1000)
    box_2d = [ny(y0), nx(x0), ny(y1), nx(x1)]
    polygon = [[nx(x0), ny(y0)], [nx(x1), ny(y0)], [nx(x1), ny(y1)], [nx(x0), ny(y1)]]
    return img, box_2d, polygon


def redness(img, rect=CAN):
    """範囲内の (R - G) の平均。缶が残っていれば大きい"""
    x0, y0, x1, y1 = rect
    roi = img[y0:y1, x0:x1].astype(np.float32)
    return float(np.mean(roi[..., 2] - roi[..., 1]))


def iou(a, b):
    a, b = a > 0, b > 0
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0

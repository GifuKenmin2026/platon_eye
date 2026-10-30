import base64
import time
import unittest

import cv2
import numpy as np

import vision
from tests.helpers import CAN, H, W, iou, synthetic_scene


class EraseObjectTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.img, cls.box, cls.poly = synthetic_scene()

    def box_mask(self):
        m = np.zeros((H, W), np.uint8)
        x0, y0, x1, y1 = CAN
        m[y0:y1, x0:x1] = 255
        return m

    def test_polygon_full_image_basis(self):
        r = vision.erase_object(self.img, {"box_2d": self.box, "mask": self.poly})
        self.assertEqual(r["mask_method"], "gemini-polygon")
        self.assertGreater(r["mask"][370, 640], 0)

    def test_polygon_box_basis(self):
        rel = [[0, 0], [1000, 0], [1000, 1000], [0, 1000]]
        mask, method = vision.build_mask(self.img, {"box_2d": self.box, "mask": rel})
        self.assertEqual(method, "gemini-polygon")
        self.assertGreater(iou(mask, self.box_mask()), 0.9)

    def test_polygon_too_far_from_box_is_ignored(self):
        far = [[0, 0], [100, 0], [100, 100], [0, 100]]
        r = vision.erase_object(self.img, {"box_2d": self.box, "mask": far})
        self.assertEqual(r["mask_method"], "grabcut-box")

    def test_png_mask(self):
        x0, y0, x1, y1 = CAN
        ok, png = cv2.imencode(".png", np.full((y1 - y0, x1 - x0), 255, np.uint8))
        url = "data:image/png;base64," + base64.b64encode(png.tobytes()).decode()
        r = vision.erase_object(self.img, {"box_2d": self.box, "mask": url})
        self.assertEqual(r["mask_method"], "gemini-png")

    def test_box_only_uses_grabcut(self):
        r = vision.erase_object(self.img, {"box_2d": self.box, "mask": []})
        self.assertEqual(r["mask_method"], "grabcut-box")

    def test_none_uses_center_grabcut(self):
        r = vision.erase_object(self.img, None)
        self.assertEqual(r["mask_method"], "grabcut-center")

    def test_broken_inputs_do_not_raise(self):
        y0, x0, y1, x1 = self.box
        for target in (
            {"box_2d": self.box, "mask": [[1]]},
            {"box_2d": self.box, "mask": "xx"},
            {"box_2d": [0, 0], "mask": []},
            {"box_2d": ["a", "b", "c", "d"], "mask": []},
            {"box_2d": [y1, x1, y0, x0], "mask": []},
            {},
        ):
            with self.subTest(target=target):
                r = vision.erase_object(self.img, target)
                self.assertEqual(r["erased"].shape, self.img.shape)

    def blocks_in(self, out, rect, block):
        """rect の中が block 四方のマスだけでできているか（各マスの中が1色）"""
        x0, y0, x1, y1 = rect
        for y in range(y0, y1, block):
            for x in range(x0, x1, block):
                cell = out[y:min(y + block, y1), x:min(x + block, x1)].reshape(-1, 3)
                if (cell != cell[0]).any():
                    return False
        return True

    def test_whole_box_is_mosaic_even_if_outline_is_partial(self):
        # 輪郭が缶の上 1/3 しか取れていなくても、四角い範囲ぜんぶがモザイクになる
        x0, y0, x1, y1 = CAN
        top = y0 + (y1 - y0) // 3
        nx = lambda v: round(v / W * 1000)
        ny = lambda v: round(v / H * 1000)
        partial = [[nx(x0), ny(y0)], [nx(x1), ny(y0)], [nx(x1), ny(top)], [nx(x0), ny(top)]]
        r = vision.erase_object(self.img, {"box_2d": self.box, "mask": partial})
        rx0, ry0, rx1, ry1 = r["region"]
        self.assertTrue(rx0 <= x0 and ry0 <= y0 and rx1 >= x1 and ry1 >= y1, r["region"])
        self.assertTrue(self.blocks_in(r["erased"], r["region"], r["block"]))

    def test_outside_region_is_untouched(self):
        r = vision.erase_object(self.img, {"box_2d": self.box, "mask": self.poly})
        rx0, ry0, rx1, ry1 = r["region"]
        out = r["erased"]
        self.assertTrue((out[:, :rx0] == self.img[:, :rx0]).all())
        self.assertTrue((out[:, rx1:] == self.img[:, rx1:]).all())
        self.assertTrue((out[:ry0] == self.img[:ry0]).all())

    def test_mosaic_block_size(self):
        self.assertEqual(vision.mosaic_block(240, 480), 40)   # 長い辺 ÷ 12
        self.assertEqual(vision.mosaic_block(60, 90), 16)     # 小さい物でも 16px 以上
        r = vision.erase_object(self.img, {"box_2d": self.box, "mask": self.poly})
        rx0, ry0, rx1, ry1 = r["region"]
        self.assertEqual(r["block"], vision.mosaic_block(rx1 - rx0, ry1 - ry0))

    def test_every_fallback_gives_mosaic(self):
        for target in ({"box_2d": self.box, "mask": self.poly}, {"box_2d": self.box, "mask": []}, None):
            with self.subTest(target=bool(target)):
                r = vision.erase_object(self.img, target)
                self.assertTrue(self.blocks_in(r["erased"], r["region"], r["block"]))

    def test_runs_under_one_second(self):
        t = time.perf_counter()
        vision.erase_object(self.img, {"box_2d": self.box, "mask": self.poly})
        self.assertLess(time.perf_counter() - t, 1.0)

    def test_anchor_inside_object(self):
        a = vision.erase_object(self.img, {"box_2d": self.box, "mask": self.poly})["anchor"]
        self.assertTrue(0.44 <= a["cx"] <= 0.56, a)
        self.assertTrue(0.25 <= a["cy"] <= 0.75, a)
        self.assertIsInstance(a["cx"], float)


class CodecTest(unittest.TestCase):
    def test_decode_garbage_raises_value_error(self):
        with self.assertRaises(vision.ImageDecodeError):
            vision.decode_image(b"hello")
        self.assertTrue(issubclass(vision.ImageDecodeError, ValueError))

    def test_jpeg_round_trip_and_limit(self):
        img = np.zeros((2000, 3000, 3), np.uint8)
        small = vision.limit_size(img, 1600)
        self.assertEqual(max(small.shape[:2]), 1600)
        back = vision.decode_image(vision.encode_jpeg(small))
        self.assertEqual(back.shape, small.shape)
        self.assertTrue(vision.to_data_url(small).startswith("data:image/jpeg;base64,"))


if __name__ == "__main__":
    unittest.main()

import base64
import unittest
from unittest import mock

import numpy as np

import gemini
import pipeline
import vision
from tests.helpers import synthetic_scene

DEMO = {"api_key": "", "model": "m", "port": 8000, "demo": True}
LIVE = {"api_key": "k", "model": "m", "port": 8000, "demo": False}
IDEA = {"word": "庇護", "reading": "ひご", "greek": "σκέπη", "greek_reading": "スケペー",
        "definition": "外からの厳しさをさえぎり、内にあるものを保つはたらきそのもの。",
        "participation": "この物は、庇護を分有している。"}
KEYS = {"ok", "mode", "label", "idea", "anchor", "mask_method", "original", "erased", "seconds"}


def jpeg_of(img):
    return vision.encode_jpeg(img)


def decode_data_url(url):
    return vision.decode_image(base64.b64decode(url.split(",", 1)[1]))


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        img, cls.box, cls.poly = synthetic_scene()
        cls.jpeg = jpeg_of(img)

    def test_demo_mode_shape(self):
        r = pipeline.transmute(self.jpeg, DEMO)
        self.assertTrue(KEYS <= set(r), KEYS - set(r))
        self.assertIs(r["ok"], True)
        self.assertEqual(r["mode"], "demo")
        self.assertTrue(r["original"].startswith("data:image/jpeg;base64,"))
        self.assertTrue(r["erased"].startswith("data:image/jpeg;base64,"))
        self.assertNotIn("quest", r)
        self.assertNotIn("quest", r["idea"])
        self.assertTrue(r["idea"]["word"])

    def test_demo_mode_with_quest(self):
        r = pipeline.transmute(self.jpeg, DEMO, quest="庇護")
        self.assertEqual(r["quest"]["word"], "庇護")
        self.assertIsInstance(r["quest"]["match"], bool)
        self.assertIn("お試し", r["quest"]["reason"])

    def test_live_mode_uses_gemini(self):
        target = {"box_2d": self.box, "mask": self.poly, "label": "缶"}
        idea = {**IDEA, "quest": {"word": "庇護", "match": True, "reason": "r"}}
        with mock.patch.object(gemini, "segment", return_value=target), \
             mock.patch.object(gemini, "idealize", return_value=idea) as ide:
            r = pipeline.transmute(self.jpeg, LIVE, quest="庇護")
        self.assertEqual(r["mode"], "gemini")
        self.assertEqual(r["label"], "缶")
        self.assertEqual(r["mask_method"], "gemini-polygon")
        self.assertEqual(r["quest"], {"word": "庇護", "match": True, "reason": "r"})
        self.assertNotIn("quest", r["idea"])
        self.assertEqual(ide.call_args.kwargs.get("quest"), "庇護")

    def test_segment_failure_falls_back_to_grabcut(self):
        with mock.patch.object(gemini, "segment", side_effect=gemini.GeminiError("HTTP 500 x")), \
             mock.patch.object(gemini, "idealize", return_value=dict(IDEA)):
            r = pipeline.transmute(self.jpeg, LIVE)
        self.assertTrue(r["mask_method"].startswith("grabcut-"))

    def test_idea_failure_raises_user_facing(self):
        with mock.patch.object(gemini, "segment", return_value=None), \
             mock.patch.object(gemini, "idealize", side_effect=gemini.GeminiError("HTTP 500 boom")):
            with self.assertRaises(pipeline.UserFacingError) as cm:
                pipeline.transmute(self.jpeg, LIVE)
        self.assertTrue(str(cm.exception).startswith("イデアを取り出せませんでした。もう一度撮ってください"))

    def test_network_error_message(self):
        err = gemini.GeminiError("接続できませんでした: no route")
        with mock.patch.object(gemini, "segment", side_effect=err), \
             mock.patch.object(gemini, "idealize", side_effect=err):
            with self.assertRaises(pipeline.UserFacingError) as cm:
                pipeline.transmute(self.jpeg, LIVE)
        self.assertIn("インターネットにつながっていません", str(cm.exception))

    def test_rate_limit_message(self):
        for code in ("429", "503"):
            with self.subTest(code=code), \
                 mock.patch.object(gemini, "segment", return_value=None), \
                 mock.patch.object(gemini, "idealize", side_effect=gemini.GeminiError(f'HTTP {code}: {{"error": 1}}')):
                with self.assertRaises(pipeline.UserFacingError) as cm:
                    pipeline.transmute(self.jpeg, LIVE)
                self.assertIn("混み合っています", str(cm.exception))
                self.assertNotIn("{", str(cm.exception))

    def test_key_error_message(self):
        err = gemini.GeminiError("APIキーが無効です。.env の GEMINI_API_KEY を確認してください。")
        with mock.patch.object(gemini, "segment", side_effect=err), \
             mock.patch.object(gemini, "idealize") as ide:
            with self.assertRaises(pipeline.UserFacingError) as cm:
                pipeline.transmute(self.jpeg, LIVE)
        self.assertIn(".env", str(cm.exception))
        ide.assert_not_called()

    def test_large_image_is_limited(self):
        big = jpeg_of(np.full((2000, 3000, 3), 128, np.uint8))
        r = pipeline.transmute(big, DEMO)
        self.assertEqual(max(decode_data_url(r["original"]).shape[:2]), 1600)

    def test_demo_match_switch(self):
        for value, expected in (("always", True), ("never", False)):
            with self.subTest(value=value), mock.patch.dict("os.environ", {"PLATON_DEMO_MATCH": value}):
                for _ in range(5):
                    self.assertIs(pipeline.transmute(self.jpeg, DEMO, quest="庇護")["quest"]["match"], expected)

    def test_demo_delay_switch(self):
        with mock.patch.dict("os.environ", {"PLATON_DEMO_DELAY": "0.3"}), \
             mock.patch.object(pipeline.time, "sleep") as sleep:
            pipeline.transmute(self.jpeg, DEMO)
        sleep.assert_called_once_with(0.3)

    def test_garbage_raises_value_error(self):
        with self.assertRaises(ValueError):
            pipeline.transmute(b"hello", DEMO)


if __name__ == "__main__":
    unittest.main()

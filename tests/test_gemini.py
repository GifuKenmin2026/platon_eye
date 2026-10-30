import json
import unittest
from unittest import mock

import gemini

CFG = {"api_key": "k", "model": "gemini-3.8-flash"}
JPEG = b"\xff\xd8fake"


def gen(obj_or_text):
    text = obj_or_text if isinstance(obj_or_text, str) else json.dumps(obj_or_text, ensure_ascii=False)
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


class FakePost:
    """_post の代わり。返す値（dict）か投げる例外を順に並べる"""

    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = []

    def __call__(self, url, key, body, timeout):
        self.calls.append({"url": url, "body": body})
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


IDEA = {
    "word": "庇護", "reading": "ひご", "greek": "σκέπη", "greek_reading": "スケペー",
    "definition": "外からの厳しさをさえぎり、内にあるものをそのままに保つはたらきそのもの。",
    "participation": "この上着は、庇護を分有している。",
}


class AskJsonTest(unittest.TestCase):
    def ask(self, fake, minimal=True):
        with mock.patch.object(gemini, "_post", fake):
            return gemini.ask_json(CFG, "p", JPEG, {"type": "OBJECT"}, minimal_thinking=minimal)

    def test_generate_content_text_is_parsed(self):
        fake = FakePost({"candidates": [{"content": {"parts": [{"thought": True, "text": "x"}, {"text": '{"a":1}'}]}}]})
        self.assertEqual(self.ask(fake), {"a": 1})
        self.assertIn(":generateContent", fake.calls[0]["url"])

    def test_code_fence_json_is_parsed(self):
        self.assertEqual(self.ask(FakePost(gen('```json\n{"a": 2}\n```'))), {"a": 2})

    def test_thinking_level_steps_down_on_400(self):
        bad = gemini.GeminiError("HTTP 400: thinking level not supported")
        fake = FakePost(bad, bad, gen({"a": 3}))
        self.assertEqual(self.ask(fake), {"a": 3})
        levels = [c["body"]["generationConfig"].get("thinkingConfig", {}).get("thinkingLevel") for c in fake.calls]
        self.assertEqual(levels, ["minimal", "low", None])

    def test_interactions_steps_shape(self):
        fake = FakePost(gemini.GeminiError("HTTP 404: not found"), {"steps": [
            {"type": "user_input", "content": [{"type": "text", "text": "p"}]},
            {"type": "model_output", "content": [{"type": "text", "text": '{"a": 5}'}]},
        ]})
        self.assertEqual(self.ask(fake), {"a": 5})

    def test_connection_error_skips_interactions(self):
        fake = FakePost(gemini.GeminiError("接続できませんでした: timed out"))
        with self.assertRaises(gemini.GeminiError):
            self.ask(fake)
        self.assertEqual(len(fake.calls), 1)

    def test_falls_back_to_interactions(self):
        fake = FakePost(gemini.GeminiError("HTTP 404: not found"),
                        {"outputs": [{"type": "text", "text": '{"a": 4}'}]})
        self.assertEqual(self.ask(fake), {"a": 4})
        self.assertTrue(fake.calls[1]["url"].endswith("/interactions"))

    def test_401_raises_key_message(self):
        with self.assertRaises(gemini.GeminiError) as cm:
            self.ask(FakePost(gemini.GeminiError("HTTP 401: bad")))
        self.assertIn("APIキー", str(cm.exception))

    def test_url_error_message(self):
        err = gemini.GeminiError("接続できませんでした: name resolution")
        with self.assertRaises(gemini.GeminiError) as cm:
            self.ask(FakePost(err, err))
        self.assertIn("接続できませんでした", str(cm.exception))


class PostTest(unittest.TestCase):
    def test_non_json_reply_becomes_gemini_error(self):
        res = mock.MagicMock()
        res.__enter__.return_value.read.return_value = b"<html>captive portal</html>"
        with mock.patch("urllib.request.urlopen", return_value=res):
            with self.assertRaises(gemini.GeminiError):
                gemini._post("https://x", "k", {}, 1)

    def test_incomplete_read_becomes_gemini_error(self):
        import http.client
        with mock.patch("urllib.request.urlopen", side_effect=http.client.IncompleteRead(b"")):
            with self.assertRaises(gemini.GeminiError) as cm:
                gemini._post("https://x", "k", {}, 1)
        self.assertIn("接続できませんでした", str(cm.exception))


class SegmentTest(unittest.TestCase):
    def test_segment_picks_largest_and_skips_invalid(self):
        boxes = {"boxes": [
            {"box_2d": [0, 0, 100, 100], "mask": [], "label": "小"},
            {"box_2d": [0, 0], "mask": [], "label": "壊れ"},
            {"box_2d": [100, 100, 900, 900], "mask": [], "label": "大"},
        ]}
        with mock.patch.object(gemini, "_post", FakePost(gen(boxes))):
            self.assertEqual(gemini.segment(CFG, JPEG)["label"], "大")

    def test_segment_empty_is_none(self):
        with mock.patch.object(gemini, "_post", FakePost(gen({"boxes": []}))):
            self.assertIsNone(gemini.segment(CFG, JPEG))


class IdealizeTest(unittest.TestCase):
    def run_idealize(self, reply, quest=None):
        fake = FakePost(gen(reply))
        with mock.patch.object(gemini, "_post", fake):
            return gemini.idealize(CFG, JPEG, "上着", quest=quest), fake.calls[0]["body"]

    def test_idealize_strips_brackets_and_truncates(self):
        idea, _ = self.run_idealize({**IDEA, "word": "【活力そのものの本質】"})
        self.assertEqual(idea["word"], "活力そのものの本")

    def test_idealize_empty_word_or_definition_raises(self):
        for broken in ({**IDEA, "word": " 【】 "}, {**IDEA, "definition": ""}):
            with self.subTest(broken=broken):
                with self.assertRaises(gemini.GeminiError):
                    self.run_idealize(broken)

    def test_idealize_without_quest_has_no_quest_fields(self):
        idea, body = self.run_idealize(IDEA)
        schema = body["generationConfig"]["responseSchema"]
        self.assertNotIn("quest_match", schema["properties"])
        self.assertNotIn("quest", idea)
        self.assertEqual(idea["definition"], IDEA["definition"])

    def test_idealize_with_quest(self):
        reply = {**IDEA, "quest_match": True, "quest_reason": "雨や寒さから身を包み守るはたらきを持つため。"}
        idea, body = self.run_idealize(reply, quest="庇護")
        prompt = body["contents"][0]["parts"][0]["text"]
        schema = body["generationConfig"]["responseSchema"]
        self.assertIn("『庇護』", prompt)
        self.assertIn("quest_match", schema["required"])
        self.assertIn("quest_reason", schema["required"])
        self.assertEqual(idea["quest"], {"word": "庇護", "match": True, "reason": reply["quest_reason"]})


if __name__ == "__main__":
    unittest.main()

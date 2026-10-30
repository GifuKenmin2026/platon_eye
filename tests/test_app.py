import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import app
import vision
from tests.helpers import synthetic_scene

DEMO = {"api_key": "", "model": "gemini-3.8-flash", "port": 0, "demo": True}


class AppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        web = Path(cls._tmp.name) / "web"
        web.mkdir()
        (web / "index.html").write_text("<title>プラトンの眼</title>", encoding="utf-8")
        (web / "a.js").write_text("export const x = 1;", encoding="utf-8")
        (web / "q.json").write_text("[]", encoding="utf-8")
        (Path(cls._tmp.name) / "secret.txt").write_text("secret", encoding="utf-8")
        cls.server = app.make_server(DEMO, port=0, web_root=web)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.jpeg = vision.encode_jpeg(synthetic_scene()[0])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request(method, path, body=body, headers=headers or {})
        res = conn.getresponse()
        data = res.read()
        conn.close()
        return res.status, res.getheader("Content-Type", ""), data

    def post_jpeg(self, path, body):
        return self.request("POST", path, body, {"Content-Type": "image/jpeg"})

    def test_status(self):
        status, ctype, data = self.request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data), {"mode": "demo", "model": "gemini-3.8-flash"})

    def test_index_served(self):
        status, ctype, data = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("プラトンの眼", data.decode("utf-8"))

    def test_js_content_type(self):
        status, ctype, _ = self.request("GET", "/a.js")
        self.assertEqual(ctype, "text/javascript; charset=utf-8")
        _, ctype, _ = self.request("GET", "/q.json")
        self.assertEqual(ctype, "application/json; charset=utf-8")

    def test_404(self):
        self.assertEqual(self.request("GET", "/nope.html")[0], 404)

    def test_path_traversal_404(self):
        self.assertEqual(self.request("GET", "/../secret.txt")[0], 404)
        self.assertEqual(self.request("GET", "/%2e%2e/secret.txt")[0], 404)

    def test_transmute_ok(self):
        status, _, data = self.post_jpeg("/api/transmute", self.jpeg)
        self.assertEqual(status, 200)
        self.assertIs(json.loads(data)["ok"], True)

    def test_transmute_quest_japanese(self):
        status, _, data = self.post_jpeg("/api/transmute?quest=%E5%BA%87%E8%AD%B7", self.jpeg)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["quest"]["word"], "庇護")

    def test_quest_too_long_400(self):
        status, _, data = self.post_jpeg("/api/transmute?quest=" + "a" * 21, self.jpeg)
        self.assertEqual(status, 400)
        self.assertIs(json.loads(data)["ok"], False)

    def test_empty_body_400(self):
        self.assertEqual(self.post_jpeg("/api/transmute", b"")[0], 400)

    def test_garbage_body_400(self):
        status, _, data = self.post_jpeg("/api/transmute", b"hello")
        self.assertEqual(status, 400)
        self.assertIn("画像", json.loads(data)["error"])

    def test_unexpected_value_error_is_500_not_image_error(self):
        from unittest import mock
        import pipeline
        with mock.patch.object(pipeline, "transmute", side_effect=ValueError("json broke")):
            status, _, data = self.post_jpeg("/api/transmute", self.jpeg)
        self.assertEqual(status, 500)
        self.assertNotIn("画像を読み込めませんでした", json.loads(data)["error"])

    def test_too_large_400(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.putrequest("POST", "/api/transmute")
        conn.putheader("Content-Length", str(21 * 1024 * 1024))
        conn.endheaders()
        res = conn.getresponse()
        self.assertEqual(res.status, 400)
        conn.close()


if __name__ == "__main__":
    unittest.main()

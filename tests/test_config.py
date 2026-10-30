import tempfile
import unittest
from pathlib import Path

from config import load_config


class LoadConfigTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_env(self, text):
        (self.root / ".env").write_text(text, encoding="utf-8-sig")

    def test_defaults_without_env_file(self):
        cfg = load_config(self.root, {})
        self.assertEqual(cfg["model"], "gemini-3.8-flash")
        self.assertEqual(cfg["port"], 8000)
        self.assertIs(cfg["demo"], True)

    def test_reads_env_file_with_bom_and_quotes(self):
        self.write_env('GEMINI_API_KEY="abc"\nPORT=8123\n# c\n')
        cfg = load_config(self.root, {})
        self.assertEqual(cfg["api_key"], "abc")
        self.assertEqual(cfg["port"], 8123)
        self.assertIs(cfg["demo"], False)

    def test_placeholder_key_is_demo(self):
        self.write_env("GEMINI_API_KEY=ここにキーを貼る\n")
        self.assertIs(load_config(self.root, {})["demo"], True)

    def test_environ_overrides_file(self):
        self.write_env("GEMINI_MODEL=from-file\n")
        cfg = load_config(self.root, {"GEMINI_MODEL": "from-env"})
        self.assertEqual(cfg["model"], "from-env")

    def test_reads_shift_jis_env(self):
        (self.root / ".env").write_bytes("# 日本語のコメント\nGEMINI_API_KEY=abc\n".encode("cp932"))
        self.assertEqual(load_config(self.root, {})["api_key"], "abc")

    def test_bad_port_falls_back(self):
        self.write_env("PORT=abc\n")
        self.assertEqual(load_config(self.root, {})["port"], 8000)


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class BatchFileTest(unittest.TestCase):
    """Windows の cmd は UTF-8 の .bat に多バイト文字があると行を読み違えるため、英数字だけにする"""

    def test_bat_files_are_ascii_and_crlf(self):
        for name in ("setup.bat", "start.bat"):
            with self.subTest(name=name):
                data = (ROOT / name).read_bytes()
                bad = [ln for ln in data.split(b"\r\n") if any(b > 127 for b in ln)]
                self.assertEqual(bad, [], f"{name} に英数字以外: {bad[:2]}")
                self.assertNotIn(b"\n", data.replace(b"\r\n", b""), f"{name} が CRLF でない")
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"), f"{name} に BOM")


if __name__ == "__main__":
    unittest.main()

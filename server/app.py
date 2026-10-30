"""
プラトンの眼 — ローカルサーバー（標準ライブラリ＋OpenCV＋NumPy）

  python server/app.py   →  http://localhost:8000
"""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pipeline  # noqa: E402
import vision  # noqa: E402
from config import load_config  # noqa: E402

MAX_BODY = 20 * 1024 * 1024
MAX_QUEST = 20
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
}


def make_server(cfg: dict, host: str = "127.0.0.1", port: int = 0, web_root: Path | None = None) -> ThreadingHTTPServer:
    web = Path(web_root or ROOT / "web").resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "PlatonEye/1.0"

        def log_message(self, fmt, *args):
            pass

        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj: dict):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"), TYPES[".json"])

        def _fail(self, code: int, message: str):
            self.close_connection = True
            self._json(code, {"ok": False, "error": message})

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path == "/api/status":
                return self._json(200, {"mode": "demo" if cfg["demo"] else "gemini", "model": cfg["model"]})
            if path.endswith("/"):
                path += "index.html"
            file = (web / path.lstrip("/")).resolve()
            if web not in file.parents or not file.is_file():
                return self._send(404, "見つかりません".encode("utf-8"), "text/plain; charset=utf-8")
            ctype = TYPES.get(file.suffix.lower()) or mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            self._send(200, file.read_bytes(), ctype)

        def do_POST(self):
            url = urlsplit(self.path)
            if url.path != "/api/transmute":
                return self._send(404, "見つかりません".encode("utf-8"), "text/plain; charset=utf-8")
            quest = (parse_qs(url.query).get("quest") or [""])[0].strip() or None
            if quest and len(quest) > MAX_QUEST:
                return self._fail(400, "お題が長すぎます（20文字まで）")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0:
                return self._fail(400, "画像が届いていません。もう一度撮ってください。")
            if length > MAX_BODY:
                return self._fail(400, "画像が大きすぎます（20MB まで）")
            body = self.rfile.read(length)
            try:
                result = pipeline.transmute(body, cfg, quest=quest)
            except vision.ImageDecodeError:
                return self._fail(400, "画像を読み込めませんでした。もう一度撮ってください。")
            except pipeline.UserFacingError as e:
                return self._fail(500, str(e))
            except Exception as e:  # 展示中は止めない
                traceback.print_exc()
                return self._fail(500, f"処理中に問題が起きました。もう一度撮ってください。（{type(e).__name__}）")
            self._json(200, result)

    return QuietServer((host, port), Handler)


class QuietServer(ThreadingHTTPServer):
    """ブラウザが先に切った時のエラーは出さない（ほかのエラーはそのまま出す）"""

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


def main():
    cfg = load_config(ROOT, os.environ)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    line = "=" * 56
    print(line)
    print(" Ὁ ὀφθαλμὸς τοῦ Πλάτωνος — プラトンの眼")
    print(line)
    if cfg["demo"]:
        print(" お試しモードで動いています（.env に GEMINI_API_KEY がありません）")
        print(" 物を消す処理は本物。イデアは用意した10語から選びます。")
    else:
        print(f" Gemini モデル: {cfg['model']}")
    print(f" ブラウザで開く: http://localhost:{cfg['port']}")
    print(" 終了するには、このウィンドウで Ctrl + C")
    print(line, flush=True)
    server = make_server(cfg, "127.0.0.1", cfg["port"])
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("終了しました。")


if __name__ == "__main__":
    main()

"""
Gemini につながるかを確かめる（check.bat から呼ぶ）

  python server/check_net.py
"""
from __future__ import annotations

import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import gemini  # noqa: E402
from config import load_config  # noqa: E402

HOST = "generativelanguage.googleapis.com"


def run(cfg: dict, proxies: dict) -> list[str]:
    out = []
    out.append(f"プロキシ設定: {proxies or 'なし'}")
    if cfg["demo"]:
        out.append("APIキー: なし（お試しモード）。.env に GEMINI_API_KEY を入れてください。")
        return out
    out.append(f"APIキー: あり（先頭 {cfg['api_key'][:4]}…）　モデル: {cfg['model']}")

    t = time.perf_counter()
    try:
        socket.getaddrinfo(HOST, 443)
        out.append(f"1. 名前の解決（{HOST}）: OK")
    except OSError as e:
        out.append(f"1. 名前の解決（{HOST}）: 失敗 … {e}")
        out.append("   → インターネットにつながっていないか、DNS が止められています。")
        return out

    t = time.perf_counter()
    try:
        data = gemini._post_get(f"{gemini.API_ROOT}/models?pageSize=200", cfg["api_key"], timeout=20)
    except gemini.GeminiError as e:
        out.append(f"2. Gemini への接続（{time.perf_counter() - t:.1f}秒）: 失敗 … {e}")
        msg = str(e)
        if "HTTP 401" in msg or "HTTP 403" in msg or "API key" in msg:
            out.append("   → APIキーが無効です。.env を確認してください。")
        elif "CERTIFICATE" in msg.upper() or "SSL" in msg.upper():
            out.append("   → 証明書の確認で止まっています。学校・会社のネットワークの検査（SSL）が原因の可能性があります。")
        elif "timed out" in msg or "10060" in msg:
            out.append("   → 時間切れです。ネットワークの管理者が外部への接続を止めている可能性があります。")
        else:
            out.append("   → 別のネットワーク（スマホのテザリングなど）で試すと、原因の切り分けになります。")
        return out
    names = [m.get("name", "").split("/")[-1] for m in data.get("models", [])]
    out.append(f"2. Gemini への接続（{time.perf_counter() - t:.1f}秒）: OK")
    if cfg["model"] in names:
        out.append(f"3. モデル {cfg['model']}: 使えます")
    else:
        out.append(f"3. モデル {cfg['model']}: 一覧にありません。.env の GEMINI_MODEL を確認してください。")
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    cfg = load_config(HERE.parent, os.environ)
    print("=" * 56)
    print(" プラトンの眼  ネットワークの確認")
    print("=" * 56)
    for line in run(cfg, urllib.request.getproxies()):
        print(line)
    print("=" * 56)


if __name__ == "__main__":
    main()

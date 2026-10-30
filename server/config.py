"""設定（.env と環境変数）を読む"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_PORT = 8000
KEYS = ("GEMINI_API_KEY", "GEMINI_MODEL", "PORT")


def _read_env_file(path: Path) -> dict:
    values = {}
    if not path.is_file():
        return values
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:  # メモ帳で Shift_JIS（ANSI）保存された場合
        text = raw.decode("cp932", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config(root: Path, environ: Mapping[str, str]) -> dict:
    values = _read_env_file(Path(root) / ".env")
    for key in KEYS:
        if environ.get(key):
            values[key] = environ[key]

    api_key = values.get("GEMINI_API_KEY", "").strip()
    try:
        port = int(values.get("PORT", DEFAULT_PORT))
    except ValueError:
        port = DEFAULT_PORT

    return {
        "api_key": api_key,
        "model": values.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL,
        "port": port,
        "demo": not api_key or api_key.startswith("ここに"),
    }

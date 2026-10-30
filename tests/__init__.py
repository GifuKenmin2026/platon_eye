import sys
from pathlib import Path

# server/ のモジュールを「import vision」のように読めるようにする
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "server"))

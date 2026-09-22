"""起動用エントリポイント。

  PC画面   : http://localhost:8000/host
  スマホ画面: http://<LAN IP>:8000/   （起動時に表示されるQRコードで開く）

構成:
  game/       すごろくのルールと状態（通信を知らない）
  mobilelink  スマホ連携（../game_common）。ゲームのルールを知らない
"""

from __future__ import annotations

from pathlib import Path

from mobilelink import serve

from game.logic import Game

STATIC_DIR = Path(__file__).parent / "static"


if __name__ == "__main__":
    serve(Game(), STATIC_DIR)

"""設定値と、スマホから見えるこのPCのアドレス。"""

from __future__ import annotations

import socket
from pathlib import Path

PORT = 8000
STATIC_DIR = Path(__file__).parent / "static"


def get_lan_ip() -> str:
    """同じWi-Fi上のスマホから見える、このPCのIPアドレスを調べる。

    実際にパケットは送らない。OSのルーティングテーブルを引かせて、
    「外に出ていくときに使うNICのIP」を取得しているだけ。
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


LAN_IP = get_lan_ip()
JOIN_URL = f"http://{LAN_IP}:{PORT}/"

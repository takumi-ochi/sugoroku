"""起動用エントリポイント。

  PC画面   : http://localhost:8000/host
  スマホ画面: http://<LAN IP>:8000/   （起動時に表示されるQRコードで開く）

構成:
  game/  ゲームのルールと状態（通信を知らない）
  net/   WebSocketとHTTP（ゲームのルールを知らない）
"""

from __future__ import annotations

import sys

import qrcode

from config import JOIN_URL, PORT
from net.server import create_app

app = create_app()


def print_qr(url: str) -> None:
    """URLのQRコードをターミナルに描く。

    日本語WindowsのコンソールはUTF-8でないこと（cp932）があり、
    ブロック文字をそのまま出すと UnicodeEncodeError で落ちる。
    出せない環境ではANSIの反転表示で代用する。
    """
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)

    block = chr(0x2588)
    try:
        block.encode(sys.stdout.encoding or "ascii")
    except (UnicodeEncodeError, LookupError):
        for row in qr.get_matrix():
            # 明モジュールを反転（＝明るく）して描く。暗モジュールは背景のまま。
            print("".join("  " if dark else "\x1b[7m  \x1b[0m" for dark in row))
    else:
        qr.print_ascii(invert=True)


def print_banner() -> None:
    print()
    print_qr(JOIN_URL)
    print(f"  スマホ  :  {JOIN_URL}")
    print(f"  PC画面  :  http://localhost:{PORT}/host")
    print()
    print("  ※ スマホはPCと同じWi-Fiに接続してください（モバイル回線では繋がりません）")
    print("  ※ 繋がらない場合は setup-firewall.ps1 を管理者PowerShellで実行")
    print()


if __name__ == "__main__":
    import uvicorn

    print_banner()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")

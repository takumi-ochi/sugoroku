"""
親機（Windows PC）で動かすゲームサーバー。

  PC画面   : http://<LAN IP>:8000/host
  スマホ画面: http://<LAN IP>:8000/      （起動時に表示されるQRコードで開く）

起動:
  python main.py
"""

from __future__ import annotations

import io
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path

import qrcode
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from qrcode.image.svg import SvgPathImage

PORT = 8000
STATIC_DIR = Path(__file__).parent / "static"

# 参加者に順番に割り当てる色
COLORS = ["#ff5c7c", "#4dd0e1", "#ffd54f", "#81c784", "#ba8cff", "#ff9d5c"]


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


@dataclass
class Player:
    id: str
    name: str
    color: str
    ws: WebSocket
    taps: int = 0

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "color": self.color, "taps": self.taps}


@dataclass
class Hub:
    """接続中のPC画面と参加者をまとめて持つ。"""

    hosts: set[WebSocket] = field(default_factory=set)
    players: dict[str, Player] = field(default_factory=dict)
    _seq: int = 0

    def next_player(self, name: str, ws: WebSocket) -> Player:
        self._seq += 1
        pid = f"p{self._seq}"
        color = COLORS[(self._seq - 1) % len(COLORS)]
        player = Player(id=pid, name=name or f"プレイヤー{self._seq}", color=color, ws=ws)
        self.players[pid] = player
        return player

    def roster(self) -> dict:
        return {"type": "roster", "players": [p.to_dict() for p in self.players.values()]}

    async def to_hosts(self, message: dict) -> None:
        """PC画面へ配信。切れているソケットは取り除く。"""
        dead = set()
        for ws in self.hosts:
            try:
                await ws.send_json(message)
            except (WebSocketDisconnect, RuntimeError):
                dead.add(ws)
        self.hosts -= dead


hub = Hub()
app = FastAPI()


@app.get("/")
def player_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "player.html")


@app.get("/host")
def host_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "host.html")


@app.get("/qr.svg")
def qr_svg() -> Response:
    """参加用URLのQRコード。PC画面に出してスマホで読ませる。"""
    img = qrcode.make(JOIN_URL, image_factory=SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")


@app.websocket("/ws/host")
async def ws_host(ws: WebSocket) -> None:
    await ws.accept()
    hub.hosts.add(ws)
    await ws.send_json({"type": "welcome", "join_url": JOIN_URL})
    await ws.send_json(hub.roster())
    try:
        while True:
            # PC画面からの受信は今は使わないが、切断検知のために読み続ける
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.hosts.discard(ws)


@app.websocket("/ws/player")
async def ws_player(ws: WebSocket, name: str = "") -> None:
    await ws.accept()
    player = hub.next_player(name.strip()[:12], ws)
    await ws.send_json({"type": "joined", "you": player.to_dict()})
    await hub.to_hosts({"type": "join", "player": player.to_dict()})
    await hub.to_hosts(hub.roster())
    print(f"[+] {player.name} ({player.id}) が参加しました", flush=True)

    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "tap":
                player.taps += 1
                await hub.to_hosts({"type": "tap", "player": player.to_dict()})
                await ws.send_json({"type": "ack", "taps": player.taps})
    except WebSocketDisconnect:
        pass
    finally:
        hub.players.pop(player.id, None)
        await hub.to_hosts({"type": "leave", "player": player.to_dict()})
        await hub.to_hosts(hub.roster())
        print(f"[-] {player.name} ({player.id}) が退出しました", flush=True)


def print_qr(url: str) -> None:
    """URLのQRコードをターミナルに描く。

    日本語WindowsのコンソールはUTF-8でないこと（cp932）があり、
    ブロック文字'█'をそのまま出すと UnicodeEncodeError で落ちる。
    出せない環境ではANSIの反転表示で代用する。
    """
    qr = qrcode.QRCode(border=2)
    qr.add_data(url)
    qr.make(fit=True)

    try:
        "█".encode(sys.stdout.encoding or "ascii")
    except (UnicodeEncodeError, LookupError):
        for row in qr.get_matrix():
            # 明モジュールを反転（＝明るく）して描く。暗モジュールは背景のまま。
            print("".join("  " if dark else "[7m  [0m" for dark in row))
    else:
        qr.print_ascii(invert=True)


def print_banner() -> None:
    print()
    print_qr(JOIN_URL)
    print(f"  スマホ  :  {JOIN_URL}")
    print(f"  PC画面  :  http://localhost:{PORT}/host")
    print()
    print("  ※ スマホはPCと同じWi-Fiに接続してください（モバイル回線では繋がりません）")
    print("  ※ 初回起動時のファイアウォール確認では「プライベート ネットワーク」を許可してください")
    print()


if __name__ == "__main__":
    import uvicorn

    print_banner()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")

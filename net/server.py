"""HTTPとWebSocketの入り口。スマホ・PC画面との接続だけを扱う。"""

from __future__ import annotations

import io

import qrcode
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from qrcode.image.svg import SvgPathImage

from config import JOIN_URL, STATIC_DIR
from game.logic import Game

from .hub import Hub


# 画面を書き換えたのにブラウザが古いJSを持ち続ける事故を防ぐ。
# 配信するのは自分のPCなので、毎回読み直させても遅くならない。
NO_CACHE = {"Cache-Control": "no-store, must-revalidate"}

# WindowsのPythonは .js をレジストリ由来で text/plain と判定することがある。
# そうなるとESモジュールの読み込みがブラウザに拒否されるので、明示する。
MEDIA_TYPES = {
    ".js": "text/javascript",
    ".css": "text/css",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json",
}


def create_app() -> FastAPI:
    app = FastAPI()
    hub = Hub(Game())

    @app.get("/")
    def player_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "player.html", headers=NO_CACHE)

    @app.get("/host")
    def host_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "host.html", headers=NO_CACHE)

    @app.get("/static/{path:path}")
    def static_file(path: str) -> FileResponse:
        """共有のJS・CSSを配る。親ディレクトリを指す指定で外へ出られないようにする。"""
        root = STATIC_DIR.resolve()
        target = (root / path).resolve()
        if root not in target.parents or not target.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(
            target,
            media_type=MEDIA_TYPES.get(target.suffix.lower()),
            headers=NO_CACHE,
        )

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
        await hub.add_host(ws)
        await ws.send_json({"type": "welcome", "join_url": JOIN_URL})
        await ws.send_json(hub.game.state())
        try:
            while True:
                # PC画面からの操作（参加者の切断など）を受け取る
                await hub.on_host_message(await ws.receive_json())
        except WebSocketDisconnect:
            pass
        finally:
            hub.remove_host(ws)

    @app.websocket("/ws/player")
    async def ws_player(ws: WebSocket, name: str = "") -> None:
        await ws.accept()
        player = await hub.join(ws, name)
        print(f"[+] {player.name} ({player.id}) が参加しました", flush=True)
        try:
            while True:
                await hub.on_message(player.id, await ws.receive_json())
        except WebSocketDisconnect:
            pass
        finally:
            await hub.leave(player.id)
            print(f"[-] {player.name} ({player.id}) が退出しました", flush=True)

    return app

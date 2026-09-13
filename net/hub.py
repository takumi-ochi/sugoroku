"""WebSocket接続の保持と、ゲームが出したイベントの配信。

ゲームのルールはここには書かない。ここがやるのは
「誰が繋がっているか」と「イベントを実際に送る」ことだけ。
"""

from __future__ import annotations

from fastapi import WebSocket

from game.events import HOSTS, PLAYERS, Event
from game.logic import Game, Player


class Hub:
    def __init__(self, game: Game) -> None:
        self.game = game
        self.hosts: set[WebSocket] = set()
        self.players: dict[str, WebSocket] = {}

    # ---- 配信 ----------------------------------------------------------

    async def _send(self, ws: WebSocket, payload: dict) -> bool:
        try:
            await ws.send_json(payload)
            return True
        except Exception:
            return False  # 切断済み。呼び出し側で片付ける。

    async def dispatch(self, events: list[Event]) -> None:
        """ゲームが返したイベントを、宛先に応じて実際に送る。

        close が立っているイベントは、送信後にその接続を閉じる。
        切断そのものは通信層の仕事なので、ゲーム側には現れない。
        """
        for event in events:
            if event.to == HOSTS:
                dead = {ws for ws in self.hosts if not await self._send(ws, event.payload)}
                self.hosts -= dead
            elif event.to == PLAYERS:
                for ws in list(self.players.values()):
                    await self._send(ws, event.payload)
            else:
                ws = self.players.get(event.to)
                if ws is None:
                    continue
                await self._send(ws, event.payload)
                if event.close:
                    self.players.pop(event.to, None)
                    await self._close(ws)

    async def _close(self, ws: WebSocket) -> None:
        try:
            await ws.close()
        except Exception:
            pass  # 既に切れている

    # ---- PC画面 --------------------------------------------------------

    async def add_host(self, ws: WebSocket) -> None:
        self.hosts.add(ws)

    def remove_host(self, ws: WebSocket) -> None:
        self.hosts.discard(ws)

    # ---- 参加者 --------------------------------------------------------

    async def join(self, ws: WebSocket, name: str) -> Player:
        player, events = self.game.add_player(name)
        self.players[player.id] = ws     # dispatchより先に登録する（本人宛が届かなくなるため）
        await self.dispatch(events)
        return player

    async def leave(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        await self.dispatch(self.game.remove_player(player_id))

    async def on_message(self, player_id: str, message: dict) -> None:
        await self.dispatch(self.game.handle(player_id, message))

    async def on_host_message(self, message: dict) -> None:
        """PC画面からの操作（参加者の切断など）。"""
        await self.dispatch(self.game.handle_host(message))

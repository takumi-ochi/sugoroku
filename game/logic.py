"""すごろくのルールと状態。

通信層から切り離してあるので、WebSocketもFastAPIも起動せずに
このファイルだけで挙動を検証できる（tests/test_game.py 参照）。

    game = Game(rng=random.Random(0))
    player, _ = game.add_player("タロウ")
    game.handle_host({"type": "start"})
    game.handle(player.id, {"type": "roll"})
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import board
from .events import Event, to_hosts, to_player, to_players

# 参加者に順番に割り当てる色
COLORS = ["#ff5c7c", "#4dd0e1", "#ffd54f", "#81c784", "#ba8cff", "#ff9d5c"]

WAITING = "waiting"    # 開始待ち
PLAYING = "playing"
FINISHED = "finished"


@dataclass
class Player:
    id: str
    name: str
    color: str
    pos: int = 0
    resting: bool = False      # 次の番を休む
    rank: int | None = None    # ゴールした順位。未ゴールは None

    @property
    def finished(self) -> bool:
        return self.rank is not None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "pos": self.pos,
            "resting": self.resting,
            "rank": self.rank,
        }


@dataclass
class Game:
    rng: random.Random = field(default_factory=random.Random)
    players: dict[str, Player] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)   # 手番の順（参加順）
    phase: str = WAITING
    current: str | None = None                       # 今の手番のプレイヤーID
    last_roll: dict | None = None                    # 直前の出目と移動の記録
    _seq: int = 0
    _rolls: int = 0                                  # サイコロを振った通し番号

    # ---- 状態の受け渡し ------------------------------------------------

    def state(self) -> dict:
        """PC画面・スマホの両方へ送る、いまの全状態。

        差分ではなく毎回まるごと送る。表示がずれないのと、
        後から画面を開いた人にもそのまま使えるのが理由。
        """
        return {
            "type": "state",
            "phase": self.phase,
            "goal": board.GOAL,
            "board": board.to_dict(),
            "turn": self.current,
            "last_roll": self.last_roll,
            "players": [self.players[pid].to_dict() for pid in self.order],
        }

    def _broadcast(self) -> list[Event]:
        state = self.state()
        return [to_hosts(state), to_players(state)]

    # ---- 参加と退出 ----------------------------------------------------

    def add_player(self, name: str) -> tuple[Player, list[Event]]:
        self._seq += 1
        player = Player(
            id=f"p{self._seq}",
            name=(name or "").strip()[:12] or f"プレイヤー{self._seq}",
            color=COLORS[(self._seq - 1) % len(COLORS)],
        )
        self.players[player.id] = player
        self.order.append(player.id)
        return player, [
            to_player(player.id, {"type": "joined", "you": player.to_dict()}),
            *self._broadcast(),
        ]

    def remove_player(self, player_id: str) -> list[Event]:
        if player_id not in self.players:
            return []

        index = self.order.index(player_id)
        was_current = self.current == player_id
        del self.players[player_id]
        self.order.pop(index)

        if not self.order:
            self.phase = WAITING
            self.current = None
            self.last_roll = None
        elif was_current:
            # 手番の人が抜けた。抜けた位置の「ひとつ前」から次を探す。
            self._advance(index - 1)

        return self._broadcast()

    # ---- プレイヤーからの入力 ------------------------------------------

    def handle(self, player_id: str, message: dict) -> list[Event]:
        """スマホから届いたメッセージ1件を処理し、送るべきイベントを返す。"""
        player = self.players.get(player_id)
        if player is None:
            return []

        kind = message.get("type")

        if kind == "roll":
            return self._roll(player)

        if kind == "leave":
            # 本人が退出ボタンを押した
            return [
                to_player(player.id, {"type": "left"}, close=True),
                *self.remove_player(player.id),
            ]

        return []

    # ---- PC画面からの操作 ----------------------------------------------

    def handle_host(self, message: dict) -> list[Event]:
        kind = message.get("type")

        if kind == "start":
            return self.start()
        if kind == "reset":
            return self.reset()
        if kind == "kick":
            return self.kick(message.get("id", ""))
        return []

    def kick(self, player_id: str) -> list[Event]:
        """PC画面から参加者を切断する。"""
        if player_id not in self.players:
            return []
        return [
            to_player(player_id, {"type": "kicked"}, close=True),
            *self.remove_player(player_id),
        ]

    # ---- 進行 ----------------------------------------------------------

    def start(self) -> list[Event]:
        if not self.order:
            return []
        self._reset_players()
        self.phase = PLAYING
        self.current = self.order[0]
        self.last_roll = None
        return self._broadcast()

    def reset(self) -> list[Event]:
        self._reset_players()
        self.phase = WAITING
        self.current = None
        self.last_roll = None
        return self._broadcast()

    def _reset_players(self) -> None:
        for player in self.players.values():
            player.pos = 0
            player.resting = False
            player.rank = None

    def _roll(self, player: Player) -> list[Event]:
        if self.phase != PLAYING or self.current != player.id:
            return []   # 自分の番でなければ何もしない

        value = self.rng.randint(1, 6)
        start = player.pos
        player.pos = min(player.pos + value, board.GOAL)
        land = player.pos          # マスの効果を受ける前。ここまでを1マスずつ進む。

        effect = None
        if player.pos < board.GOAL:
            effect = self._apply_square(player)

        if player.pos >= board.GOAL:
            player.rank = sum(1 for p in self.players.values() if p.finished) + 1

        self._rolls += 1
        self.last_roll = {
            "seq": self._rolls,    # 画面側が「新しい出目か」を判定するための通し番号
            "id": player.id,
            "name": player.name,
            "value": value,
            "from": start,
            "land": land,
            "to": player.pos,
            "effect": effect,
            "rank": player.rank,
        }

        self._advance(self.order.index(player.id))
        return self._broadcast()

    def _apply_square(self, player: Player) -> str | None:
        """止まったマスの効果を適用し、何が起きたかを返す。"""
        square = board.BOARD[player.pos]

        if square.kind == "forward":
            player.pos = min(player.pos + square.value, board.GOAL)
        elif square.kind == "back":
            player.pos = max(player.pos - square.value, 0)
        elif square.kind == "rest":
            player.resting = True
        else:
            return None

        return square.label

    def _advance(self, from_index: int) -> None:
        """from_index の次から、番が回せる人を探す。

        ゴール済みは飛ばす。一回休みの人は、休みを消化して飛ばす。
        """
        count = len(self.order)
        if count == 0:
            self.phase = FINISHED if self.players else WAITING
            self.current = None
            return

        # 2周ぶん見る。1周目で休みを消化した人を2周目で拾えるようにするため
        # （残り1人が休みのときに手番が消えるのを防ぐ）。
        for step in range(1, count * 2 + 1):
            candidate = self.players[self.order[(from_index + step) % count]]
            if candidate.finished:
                continue
            if candidate.resting:
                candidate.resting = False
                continue
            self.current = candidate.id
            return

        # 全員ゴール
        self.phase = FINISHED
        self.current = None

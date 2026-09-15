"""すごろくのルールと状態。

通信層から切り離してあるので、WebSocketもFastAPIも起動せずに
このファイルだけで挙動を検証できる（tests/test_game.py 参照）。

    game = Game(rng=random.Random(0))
    player, _ = game.add_player("タロウ")
    game.handle_host({"type": "start", "rounds": 10})
    game.handle(player.id, {"type": "roll"})

ゴールは無い。盤をぐるぐる回ってお金を集め、
決めたターン数が終わった時点で所持金の多い人が勝つ。
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

DEFAULT_ROUNDS = 10    # ターン数の指定が無いとき
MAX_ROUNDS = 50


def parse_rounds(value: object, default: int = DEFAULT_ROUNDS) -> int:
    """PC画面から来たターン数を 1〜MAX_ROUNDS に収める。読めなければ default。"""
    try:
        rounds = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(1, min(rounds, MAX_ROUNDS))


@dataclass
class Player:
    id: str
    name: str
    color: str
    pos: int = 0
    money: int = board.START_MONEY
    resting: bool = False      # 次の番を休む

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "pos": self.pos,
            "money": self.money,
            "resting": self.resting,
        }


@dataclass
class Game:
    rng: random.Random = field(default_factory=random.Random)
    players: dict[str, Player] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)   # 手番の順（参加順）
    phase: str = WAITING
    current: str | None = None                       # 今の手番のプレイヤーID
    round: int = 0                                   # 今が何ターン目か（1始まり。開始前は0）
    rounds: int = DEFAULT_ROUNDS                     # 全部で何ターン遊ぶか
    last_roll: dict | None = None                    # 直前の出目と移動の記録
    _seq: int = 0
    _rolls: int = 0                                  # サイコロを振った通し番号

    # ---- 状態の受け渡し ------------------------------------------------

    def state(self) -> dict:
        """PC画面・スマホの両方へ送る、いまの全状態。

        差分ではなく毎回まるごと送る。表示がずれないのと、
        後から画面を開いた人にもそのまま使えるのが理由。
        """
        ranks = self.ranks()
        return {
            "type": "state",
            "phase": self.phase,
            "size": board.SIZE,
            "salary": board.SALARY,
            "board": board.to_dict(),
            "turn": self.current,
            "round": self.round,
            "rounds": self.rounds,
            "last_roll": self.last_roll,
            "players": [
                {**self.players[pid].to_dict(), "rank": ranks[pid]} for pid in self.order
            ],
        }

    def ranks(self) -> dict[str, int]:
        """所持金の多い順の順位。同じ額なら同じ順位（1位, 1位, 3位 のように飛ぶ）。"""
        return {
            pid: 1 + sum(1 for other in self.players.values() if other.money > p.money)
            for pid, p in self.players.items()
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
            self.round = 0
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

        # 開始と終了はスマホからもできる。PC画面の前に人がいなくても遊べるように。
        if kind == "start":
            return self.start(message.get("rounds"))

        if kind == "finish":
            return self.finish()

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
            return self.start(message.get("rounds"))
        if kind == "finish":
            return self.finish()
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

    def start(self, rounds: object = None) -> list[Event]:
        """ゲーム開始。rounds を省くと前回と同じターン数で遊ぶ。

        遊んでいる最中は受け付けない（スマホの誤操作で進行が消えないように）。
        """
        if not self.order or self.phase == PLAYING:
            return []
        self.rounds = parse_rounds(rounds, default=self.rounds)
        self._reset_players()
        self.phase = PLAYING
        self.current = self.order[0]
        self.round = 1
        self.last_roll = None
        return self._broadcast()

    def finish(self) -> list[Event]:
        """ターンの途中でも、その時点の所持金で順位を決めて終わる。"""
        if self.phase != PLAYING:
            return []
        self.phase = FINISHED
        self.current = None
        return self._broadcast()

    def reset(self) -> list[Event]:
        self._reset_players()
        self.phase = WAITING
        self.current = None
        self.round = 0
        self.last_roll = None
        return self._broadcast()

    def _reset_players(self) -> None:
        for player in self.players.values():
            player.pos = 0
            player.money = board.START_MONEY
            player.resting = False

    def _roll(self, player: Player) -> list[Event]:
        if self.phase != PLAYING or self.current != player.id:
            return []   # 自分の番でなければ何もしない

        value = self.rng.randint(1, 6)
        start = player.pos
        before = player.money

        salary = self._move(player, value)
        land = player.pos          # マスの効果を受ける前。ここまでを1マスずつ進む。

        square = board.BOARD[land]
        effect = square.label if square.kind not in ("start", "normal") else None
        shift = 0                  # マスの効果で動いた歩数（戻るときは負）
        gain = 0                   # マスの効果で増減した金額

        if square.kind == "forward":
            shift = square.value
            salary += self._move(player, shift)
        elif square.kind == "back":
            shift = -square.value
            self._move(player, shift)
        elif square.kind == "rest":
            player.resting = True
        elif square.kind == "gain":
            gain = self._earn(player, square.value)
        elif square.kind == "lose":
            gain = self._earn(player, -square.value)

        self._rolls += 1
        self.last_roll = {
            "seq": self._rolls,    # 画面側が「新しい出目か」を判定するための通し番号
            "id": player.id,
            "name": player.name,
            "value": value,
            "from": start,
            "land": land,
            "to": player.pos,
            "shift": shift,
            "effect": effect,
            "before": before,      # 振る前の所持金
            "salary": salary,      # スタート通過でもらった合計
            "gain": gain,          # マスの効果による増減（実際に動いた額）
            "money": player.money,
            "round": self.round,
        }

        self._advance(self.order.index(player.id))
        return self._broadcast()

    def _move(self, player: Player, steps: int) -> int:
        """steps だけ動かす（負なら戻る）。盤は一周つながっている。

        前向きにスタートを越えた（ちょうど止まった場合も含む）回数だけ給料を払い、
        その額を返す。戻ってスタートを越えても給料は出ない。
        """
        total = player.pos + steps
        player.pos = total % board.SIZE
        if steps <= 0:
            return 0
        return self._earn(player, (total // board.SIZE) * board.SALARY)

    def _earn(self, player: Player, amount: int) -> int:
        """所持金を増減する。0円より下にはならない。実際に動いた額を返す。"""
        after = max(player.money + amount, 0)
        delta = after - player.money
        player.money = after
        return delta

    def _advance(self, from_index: int) -> None:
        """from_index の次から、番が回せる人を探す。

        参加順の最後から先頭に戻ったら1ターン終わり。決めたターン数を
        越えたらゲーム終了。一回休みの人は、休みを消化して飛ばす。
        """
        count = len(self.order)
        if count == 0:
            self.phase = WAITING
            self.current = None
            return

        # 2周ぶん見る。1周目で休みを消化した人を2周目で拾えるようにするため
        # （残り1人が休みのときに手番が消えるのを防ぐ）。
        for step in range(1, count * 2 + 1):
            index = from_index + step
            if index > 0 and index % count == 0:
                # 全員の番が一巡した
                if self.round >= self.rounds:
                    self.phase = FINISHED
                    self.current = None
                    return
                self.round += 1

            candidate = self.players[self.order[index % count]]
            if candidate.resting:
                candidate.resting = False
                continue
            self.current = candidate.id
            return

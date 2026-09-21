"""ゲームロジックが通信層に渡す「送信指示」。

ゲーム側は『誰に・何を』送るかだけを決める。
WebSocketで実際に送る方法は通信層（net/）の責務なので、ここには現れない。
"""

from __future__ import annotations

from dataclasses import dataclass

HOSTS = "@hosts"      # PC画面すべて
PLAYERS = "@players"  # 参加者すべて


@dataclass(frozen=True)
class Event:
    to: str            # HOSTS / PLAYERS / プレイヤーID
    payload: dict
    close: bool = False
    """送信後にその接続を閉じる。退出・キックで使う。

    「閉じる」という意思表示だけをここで行い、実際の切断は通信層がやる。
    """


def to_hosts(payload: dict) -> Event:
    return Event(HOSTS, payload)


def to_players(payload: dict) -> Event:
    """全員に同じ内容を配る。

    いまのゲームは使っていない。手札を持ち主にしか見せないので、
    参加者へは1人ずつ内容を変えて送っている（game/logic.py の _broadcast）。
    """
    return Event(PLAYERS, payload)


def to_player(player_id: str, payload: dict, *, close: bool = False) -> Event:
    return Event(player_id, payload, close=close)

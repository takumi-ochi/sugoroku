"""すごろくの盤面。

マスの数と効果はここだけで決まる。盤を変えたいときはこのファイルを触る。
"""

from __future__ import annotations

from dataclasses import dataclass

SIZE = 30           # マスの総数
GOAL = SIZE - 1     # ゴールのマス番号


@dataclass(frozen=True)
class Square:
    kind: str        # start / normal / forward / back / rest / goal
    value: int = 0   # forward・back で進む/戻る数
    label: str = ""


# 特殊マス。ここに無いマスはすべて normal。
SPECIALS: dict[int, Square] = {
    3: Square("forward", 2, "ワープ +2"),
    6: Square("back", 2, "もどる -2"),
    9: Square("rest", 0, "一回休み"),
    12: Square("forward", 3, "ワープ +3"),
    15: Square("back", 3, "もどる -3"),
    18: Square("rest", 0, "一回休み"),
    21: Square("forward", 2, "ワープ +2"),
    24: Square("back", 4, "もどる -4"),
    27: Square("forward", 1, "ワープ +1"),
}


def _build() -> list[Square]:
    squares = []
    for i in range(SIZE):
        if i == 0:
            squares.append(Square("start", label="スタート"))
        elif i == GOAL:
            squares.append(Square("goal", label="ゴール"))
        else:
            squares.append(SPECIALS.get(i, Square("normal")))
    return squares


BOARD: list[Square] = _build()


def to_dict() -> list[dict]:
    """PC画面へ送る形。盤面は変化しないので毎回同じ内容になる。"""
    return [{"kind": s.kind, "value": s.value, "label": s.label} for s in BOARD]

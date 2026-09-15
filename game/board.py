"""すごろくの盤面とお金の決まり。

マスの数と効果、お金の額はここだけで決まる。盤を変えたいときはこのファイルを触る。
盤はぐるっと一周つながっていて、最後のマスの次はスタートに戻る。
"""

from __future__ import annotations

from dataclasses import dataclass

SIZE = 30            # マスの総数。SIZE-1 の次は 0（スタート）に戻る
START_MONEY = 1000   # 開始時の所持金
SALARY = 200         # スタートを通過する（または止まる）たびにもらえる額


@dataclass(frozen=True)
class Square:
    kind: str        # start / normal / forward / back / rest / gain / lose
    value: int = 0   # forward・back は進む/戻る数、gain・lose は金額
    label: str = ""


def _gain(amount: int) -> Square:
    return Square("gain", amount, f"もらう +{amount}円")


def _lose(amount: int) -> Square:
    return Square("lose", amount, f"はらう -{amount}円")


# 特殊マス。ここに無いマスはすべて normal。
SPECIALS: dict[int, Square] = {
    1: _gain(100),
    3: Square("forward", 2, "ワープ +2"),
    4: _gain(200),
    5: _lose(100),
    6: Square("back", 2, "もどる -2"),
    8: _gain(100),
    9: Square("rest", 0, "一回休み"),
    10: _gain(300),
    11: _lose(200),
    12: Square("forward", 3, "ワープ +3"),
    14: _gain(100),
    15: Square("back", 3, "もどる -3"),
    16: _gain(200),
    17: _lose(300),
    18: Square("rest", 0, "一回休み"),
    20: _gain(100),
    21: Square("forward", 2, "ワープ +2"),
    22: _gain(500),
    23: _lose(200),
    24: Square("back", 4, "もどる -4"),
    25: _gain(200),
    26: _lose(100),
    27: Square("forward", 3, "ワープ +3"),   # スタートを越える
    28: _gain(300),
    29: Square("lose", 500, "ぜいきん -500円"),
}


def _build() -> list[Square]:
    squares = []
    for i in range(SIZE):
        if i == 0:
            squares.append(Square("start", label="スタート"))
        else:
            squares.append(SPECIALS.get(i, Square("normal")))
    return squares


BOARD: list[Square] = _build()


def to_dict() -> list[dict]:
    """PC画面へ送る形。盤面は変化しないので毎回同じ内容になる。"""
    return [{"kind": s.kind, "value": s.value, "label": s.label} for s in BOARD]

"""すごろくの盤面とお金の決まり。

マスの数と効果、お金の額はここだけで決まる。盤を変えたいときはこのファイルを触る。
盤はぐるっと一周つながっていて、最後のマスの次はスタートに戻る。
"""

from __future__ import annotations

from dataclasses import dataclass

SIZE = 30            # マスの総数。SIZE-1 の次は 0（スタート）に戻る
START_MONEY = 1000   # 開始時の所持金
SALARY = 200         # スタートを通過する（または止まる）たびにもらえる額

HALF = SIZE // 2     # コースの半分の位置。ここを通過する（ちょうど止まるのも含む）と HALF_BONUS がもらえる
HALF_BONUS = 500     # 半分の位置を通過するともらえる大金


@dataclass(frozen=True)
class Square:
    kind: str        # start / normal / forward / back / rest / gain / lose / card
    value: int = 0   # forward・back は進む/戻る数、gain・lose は金額
    label: str = ""


def _gain(amount: int) -> Square:
    return Square("gain", amount, f"もらう +{amount}円")


def _lose(amount: int) -> Square:
    return Square("lose", amount, f"はらう -{amount}円")


def _card() -> Square:
    """止まるとカードを1枚もらえるマス。カードの中身は game/cards.py で決まる。"""
    return Square("card", 0, "カードをひく")


# 特殊マス。ここに無いマスはすべて normal。
# カードマスは 1, 7, 8, 13, 14, 19, 20, 25 の8つ（元の1,8,14,20,25に、
# 何も起きないだけだった normal を3つ足した）。マス2だけは normal のまま残す。
SPECIALS: dict[int, Square] = {
    1: _card(),
    3: Square("forward", 2, "ワープ +2"),
    4: _gain(200),
    5: _lose(100),
    6: Square("back", 2, "もどる -2"),
    7: _card(),
    8: _card(),
    9: Square("rest", 0, "一回休み"),
    10: _gain(300),
    11: _lose(200),
    12: Square("forward", 3, "ワープ +3"),
    13: _card(),
    14: _card(),
    15: Square("back", 3, "もどる -3"),
    16: _gain(200),
    17: _lose(300),
    18: Square("rest", 0, "一回休み"),
    19: _card(),
    20: _card(),
    21: Square("forward", 2, "ワープ +2"),
    22: _gain(500),
    23: _lose(200),
    24: Square("back", 4, "もどる -4"),
    25: _card(),
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

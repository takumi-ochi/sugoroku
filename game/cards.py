"""カードの種類と山札。

マスの効果と同じで、カードを増やしたり出やすさを変えたいときはこのファイルだけを触る。

持っているカードは持ち主にしか見えない。公開する state には枚数だけを入れ、
手札の中身は本人宛のメッセージにだけ入れる（game/logic.py の _private）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass

LIMIT = 3   # 手札の上限。これを超えたぶんは自分で選んで捨てる


@dataclass(frozen=True)
class Card:
    kind: str          # advance / double / guard
    label: str         # カードの名前
    desc: str          # 効果の説明。カードを押したときに出す
    short: str = ""    # カードの表に出す一言。desc は長すぎて札に載らない
    value: int = 0     # advance は足す歩数、double はサイコロの数
    passive: bool = False
    """持っているだけで自動で発動する。使うボタンは出ない。"""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "desc": self.desc,
            "short": self.short,
            "value": self.value,
            "passive": self.passive,
        }


@dataclass
class Held:
    """手札の1枚。

    同じカードを2枚持てるので、1枚ずつに uid を振る。画面から
    「この1枚を使う・捨てる」と指すための番号。並び順（添字）で指すと、
    指示が届くまでに手札が変わったとき別のカードを捨ててしまう。
    """

    uid: str
    card: Card

    def to_dict(self) -> dict:
        return {"uid": self.uid, **self.card.to_dict()}


ADVANCE_1 = Card("advance", "+1マス", "つぎにサイコロをふるとき、出た目に 1 マス足して進む",
                 short="次の出目に足す", value=1)
ADVANCE_2 = Card("advance", "+2マス", "つぎにサイコロをふるとき、出た目に 2 マス足して進む",
                 short="次の出目に足す", value=2)
ADVANCE_3 = Card("advance", "+3マス", "つぎにサイコロをふるとき、出た目に 3 マス足して進む",
                 short="次の出目に足す", value=3)
DOUBLE = Card("double", "サイコロ2個", "つぎにサイコロをふるとき、2個ふって合計だけ進む",
              short="合計だけ進む", value=2)
GUARD = Card(
    "guard",
    "おまもり",
    "はらうマスに止まっても、1回だけ払わずにすむ。持っているだけで自動でつかわれる",
    short="1回はらわない",
    passive=True,
)

# 山札は減らない（引いても山から消えない）。ここの重複がそのまま出やすさになる。
DECK: list[Card] = [
    ADVANCE_1, ADVANCE_1,
    ADVANCE_2, ADVANCE_2,
    ADVANCE_3,
    DOUBLE, DOUBLE,
    GUARD, GUARD, GUARD,
]


def draw(rng: random.Random) -> Card:
    """山札から1枚えらぶ。"""
    return rng.choice(DECK)

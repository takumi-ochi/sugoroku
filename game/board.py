"""すごろくの盤面とお金の決まり。

マスの数と効果、お金の額はここだけで決まる。盤を変えたいときはこのファイルを触る。
盤はぐるっと一周つながっていて、最後のマスの次はスタートに戻る。

盤は階層（地上・天空・宇宙）ごとに3枚ある。マスの内容が違い、
上の階層ほどマスの数が増え（SIZES）、お金の桁も1つ増える（SCALES）。
スタートは0マス目、半周のマスは各階層のちょうど真ん中（size // 2）にある。
"""

from __future__ import annotations

from dataclasses import dataclass

# 階層ごとのマスの総数。最後のマスの次は 0（スタート）に戻る。
# 盤を輪に並べる都合（shared/ring.js）で、偶数にすること。
SIZES = [30, 40, 50]
START_MONEY = 1000   # 開始時の所持金
SALARY = 200         # スタートを通過する（または止まる）たびにもらえる額（地上での額）

HALF_BONUS = 1000    # 半周のマスを通過する（ちょうど止まるのも含む）ともらえる額（地上での額）

# 登っていく階層。1つ目が地上、最後が最上階。最上階でパーツを3種類そろえると天国へ旅立ってクリア。
STAGES: list[tuple[str, str]] = [("地上", "🌍"), ("天空", "☁️"), ("宇宙", "🚀")]
TOP_LAYER = len(STAGES)

SIZE = SIZES[0]      # 地上のマス数。階層を指定しない古い呼び方のため
HALF = SIZE // 2     # 地上の半周のマスの位置

# 階層ごとのお金の倍率。1つ上がるごとに桁が1つ増える。
# 給料・半周ボーナス・マスの金額のすべてにかかる（所持金の初期値にはかからない）。
SCALES = [1, 10, 100]


@dataclass(frozen=True)
class Square:
    kind: str        # start / half / normal / forward / back / rest / gain / lose / card
    value: int = 0   # forward・back は進む/戻る数、gain・lose は金額（倍率をかけたあと）
    label: str = ""


def scale(layer: int) -> int:
    return SCALES[layer - 1]


def size(layer: int) -> int:
    """その階層の盤のマス数。"""
    return SIZES[layer - 1]


def half(layer: int) -> int:
    """その階層の半周のマスの位置。盤のちょうど真ん中。"""
    return SIZES[layer - 1] // 2


def salary(layer: int) -> int:
    """その階層でスタートを通過したときにもらえる額。"""
    return SALARY * scale(layer)


def half_bonus(layer: int) -> int:
    """その階層で半周のマスを通過したときにもらえる額。"""
    return HALF_BONUS * scale(layer)


def _money(amount: int) -> str:
    return f"{amount:,}"


# 階層ごとのマスの呼び名。効果は同じで、名前だけが階層らしくなる。
NAMES = [
    {"gain": "もらう", "lose": "はらう", "forward": "ワープ", "back": "もどる", "rest": "一回休み"},
    {"gain": "たから", "lose": "おとしもの", "forward": "おいかぜ", "back": "むかいかぜ", "rest": "くもで休み"},
    {"gain": "ほうせき", "lose": "いんせき", "forward": "ワープ", "back": "ブラックホール", "rest": "むじゅうりょく"},
]

# 特殊マスの設計図。(種類, 値) で、gain・lose の値は「倍率をかける前」の額。
# ここに無いマスはすべて normal。0 はスタート、half(layer) は半周のマス（ここには書かない）。
C = ("card", 0)
LAYOUTS: list[dict[int, tuple[str, int]]] = [
    # 1 地上（30マス、半周は15）: 小さな金額。カードマスは 1, 7, 8, 13, 14, 19, 20, 25 の8つ。マス2は何も起きない。
    {
        1: C, 3: ("forward", 2), 4: ("gain", 200), 5: ("lose", 100), 6: ("back", 2),
        7: C, 8: C, 9: ("rest", 0), 10: ("gain", 300), 11: ("lose", 200),
        12: ("forward", 3), 13: C, 14: C,
        16: ("gain", 200), 17: ("lose", 300), 18: ("rest", 0), 19: C, 20: C,
        21: ("forward", 2), 22: ("gain", 500), 23: ("lose", 200), 24: ("back", 4), 25: C,
        26: ("lose", 100), 27: ("forward", 3), 28: ("gain", 300), 29: ("lose", 500),
    },
    # 2 天空（40マス、半周は20）: 追い風と向かい風で大きく動く。カードマスは 1, 5, 8, 13, 18, 22, 26, 30, 35 の9つ。
    {
        1: C, 2: ("gain", 300), 3: ("forward", 3), 4: ("lose", 200), 5: C, 6: ("back", 3),
        7: ("gain", 200), 8: C, 9: ("rest", 0), 10: ("lose", 300), 11: ("gain", 500),
        12: ("forward", 4), 13: C, 14: ("back", 2), 15: ("gain", 300), 16: ("lose", 400),
        17: ("forward", 2), 18: C, 19: ("gain", 200),
        21: ("gain", 300), 22: C, 23: ("rest", 0), 24: ("lose", 500), 25: ("forward", 3),
        26: C, 27: ("gain", 400), 28: ("lose", 300), 29: ("back", 5), 30: C,
        31: ("gain", 200), 32: ("forward", 3), 33: ("lose", 400), 34: ("back", 3), 35: C,
        36: ("gain", 500), 37: ("rest", 0), 38: ("forward", 2), 39: ("gain", 500),
    },
    # 3 宇宙（50マス、半周は25）: 当たり外れが大きい。カードマスは 1, 7, 12, 15, 20, 28, 33, 37, 41, 45 の10。
    {
        1: C, 2: ("lose", 300), 3: ("forward", 5), 4: ("gain", 500), 5: ("lose", 400), 6: ("back", 4),
        7: C, 8: ("gain", 300), 9: ("rest", 0), 10: ("gain", 600), 11: ("lose", 500),
        12: C, 13: ("back", 6), 14: ("forward", 3), 15: C, 16: ("gain", 400), 17: ("lose", 600),
        18: ("back", 3), 19: ("gain", 500), 20: C, 21: ("rest", 0), 22: ("lose", 300),
        23: ("forward", 4), 24: ("gain", 700),
        26: ("gain", 500), 27: ("lose", 600), 28: C, 29: ("forward", 3), 30: ("back", 5),
        31: ("gain", 800), 32: ("rest", 0), 33: C, 34: ("lose", 700), 35: ("gain", 400),
        36: ("back", 4), 37: C, 38: ("forward", 5), 39: ("lose", 500), 40: ("gain", 600),
        41: C, 42: ("rest", 0), 43: ("lose", 400), 44: ("back", 6), 45: C,
        46: ("gain", 700), 47: ("forward", 4), 48: ("lose", 800), 49: ("gain", 1000),
    },
]


def _build(layer: int) -> list[Square]:
    """layer 階層（1始まり）の盤を作る。金額には倍率をかけ、ラベルにも反映する。"""
    names, factor = NAMES[layer - 1], scale(layer)
    squares = []
    for i in range(size(layer)):
        if i == 0:
            squares.append(Square("start", label="スタート"))
        elif i == half(layer):
            squares.append(Square("half", label=f"半周 +{_money(half_bonus(layer))}円"))
        elif i in LAYOUTS[layer - 1]:
            kind, value = LAYOUTS[layer - 1][i]
            if kind == "card":
                squares.append(Square("card", 0, "カードをひく"))
            elif kind == "gain":
                squares.append(Square("gain", value * factor, f"{names['gain']} +{_money(value * factor)}円"))
            elif kind == "lose":
                squares.append(Square("lose", value * factor, f"{names['lose']} -{_money(value * factor)}円"))
            elif kind == "forward":
                squares.append(Square("forward", value, f"{names['forward']} +{value}"))
            elif kind == "back":
                squares.append(Square("back", value, f"{names['back']} -{value}"))
            else:
                squares.append(Square("rest", 0, names["rest"]))
        else:
            squares.append(Square("normal"))
    return squares


assert all(n % 2 == 0 for n in SIZES), "マス数は偶数（盤を輪に並べるため）"
BOARDS: list[list[Square]] = [_build(layer) for layer in range(1, TOP_LAYER + 1)]
BOARD: list[Square] = BOARDS[0]   # 地上の盤。階層を指定しない古い呼び方のため


def square(layer: int, index: int) -> Square:
    return BOARDS[layer - 1][index]


def to_dict() -> list[dict]:
    """PC画面へ送る形。階層ごとの盤と、その階層のマス数・半周の位置・給料・半周ボーナス。盤面は変化しない。"""
    return [
        {
            "size": size(layer),           # マス数
            "half_pos": half(layer),       # 半周のマスの位置
            "salary": salary(layer),
            "half_bonus": half_bonus(layer),
            "squares": [{"kind": s.kind, "value": s.value, "label": s.label} for s in BOARDS[layer - 1]],
        }
        for layer in range(1, TOP_LAYER + 1)
    ]


def stages_to_dict() -> list[dict]:
    """階層の名前と印。画面は名前をここから受け取るので、階層を増やしても画面は直さなくてよい。"""
    return [{"name": name, "mark": mark} for name, mark in STAGES]

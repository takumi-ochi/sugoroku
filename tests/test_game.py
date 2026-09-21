"""すごろくのルールの単体テスト。

サーバーもWebSocketも起動しない。通信層と分離してあるからこれができる。
サイコロは差し替えられるので、出目を固定して検証する。

    .venv/Scripts/python.exe -m unittest discover -s tests -t . -v
"""

import unittest

from game import board, cards
from game.events import HOSTS
from game.logic import (
    COLORS, DEFAULT_ROUNDS, FINISHED, MAX_ROUNDS, PLAYING, WAITING, Game, parse_rounds,
)


class FixedDice:
    """指定した順に出目を返すサイコロ。尽きたら最後の値を返し続ける。

    カードの抽選（rng.choice）にも使う。引かせたいカードを cards= で指定する。
    指定しなければ山札の先頭が出る。
    """

    def __init__(self, *values: int, cards: list | None = None) -> None:
        self.values = list(values)
        self.cards = list(cards or [])

    def randint(self, a: int, b: int) -> int:
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]

    def choice(self, seq: list):
        if not self.cards:
            return seq[0]
        return self.cards.pop(0) if len(self.cards) > 1 else self.cards[0]


def solo(*rolls: int, rounds: int = 99, cards: list | None = None) -> tuple[Game, object]:
    game = Game(rng=FixedDice(*rolls, cards=cards))
    player, _ = game.add_player("ひとり")
    game.handle_host({"type": "start", "rounds": min(rounds, MAX_ROUNDS)})
    return game, player


class TestBoard(unittest.TestCase):
    """テストが前提にしているマス。盤を変えたらここが先に落ちる。"""

    def test_前提のマス(self) -> None:
        self.assertEqual(board.BOARD[0].kind, "start")
        self.assertEqual(board.BOARD[1].kind, "card")
        self.assertEqual(board.BOARD[2].kind, "normal")   # 基準になる「何も起きない」マス
        self.assertEqual((board.BOARD[3].kind, board.BOARD[3].value), ("forward", 2))
        self.assertEqual((board.BOARD[5].kind, board.BOARD[5].value), ("lose", 100))
        self.assertEqual((board.BOARD[6].kind, board.BOARD[6].value), ("back", 2))
        self.assertEqual(board.BOARD[7].kind, "card")
        self.assertEqual(board.BOARD[9].kind, "rest")
        self.assertEqual((board.BOARD[27].kind, board.BOARD[27].value), ("forward", 3))
        self.assertEqual((board.BOARD[29].kind, board.BOARD[29].value), ("lose", 500))
        self.assertNotIn("goal", {s.kind for s in board.BOARD})

    def test_カードマスは8つある(self) -> None:
        self.assertEqual([i for i, s in enumerate(board.BOARD) if s.kind == "card"],
                         [1, 7, 8, 13, 14, 19, 20, 25])


class TestJoinLeave(unittest.TestCase):
    def setUp(self) -> None:
        self.game = Game()

    def test_参加すると本人と全員に通知される(self) -> None:
        player, events = self.game.add_player("タロウ")

        self.assertEqual(player.name, "タロウ")
        self.assertEqual(player.pos, 0)
        self.assertEqual(player.money, board.START_MONEY)
        self.assertEqual(
            [(e.to, e.payload["type"]) for e in events],
            [(player.id, "joined"), (HOSTS, "state"), (player.id, "state")],
        )

    def test_名前が空なら自動で割り当てられる(self) -> None:
        player, _ = self.game.add_player("   ")
        self.assertEqual(player.name, "プレイヤー1")

    def test_名前は12文字に切り詰められる(self) -> None:
        player, _ = self.game.add_player("あ" * 30)
        self.assertEqual(len(player.name), 12)

    def test_色は順番に配られ一周して戻る(self) -> None:
        colors = [self.game.add_player(f"P{i}")[0].color for i in range(len(COLORS) + 1)]
        self.assertEqual(colors[: len(COLORS)], COLORS)
        self.assertEqual(colors[len(COLORS)], COLORS[0])

    def test_自分で退出すると本人に通知され接続が閉じられる(self) -> None:
        player, _ = self.game.add_player("タロウ")

        events = self.game.handle(player.id, {"type": "leave"})

        self.assertEqual(events[0].payload, {"type": "left"})
        self.assertTrue(events[0].close)          # 通信層に切断を指示している
        self.assertEqual(self.game.order, [])

    def test_PC画面からキックできる(self) -> None:
        a, _ = self.game.add_player("A")
        b, _ = self.game.add_player("B")

        events = self.game.handle_host({"type": "kick", "id": a.id})

        self.assertEqual(events[0].payload, {"type": "kicked"})
        self.assertTrue(events[0].close)
        self.assertEqual(self.game.order, [b.id])

    def test_いないプレイヤーへの操作は無視される(self) -> None:
        self.assertEqual(self.game.handle_host({"type": "kick", "id": "無効"}), [])
        self.assertEqual(self.game.handle("無効", {"type": "roll"}), [])
        self.assertEqual(self.game.handle_host({"type": "未実装"}), [])


class TestTurn(unittest.TestCase):
    def setUp(self) -> None:
        self.game = Game(rng=FixedDice(2))    # 2 は通常マス
        self.a, _ = self.game.add_player("A")
        self.b, _ = self.game.add_player("B")

    def test_開始前はふれない(self) -> None:
        self.assertEqual(self.game.phase, WAITING)
        self.assertEqual(self.game.handle(self.a.id, {"type": "roll"}), [])
        self.assertEqual(self.a.pos, 0)

    def test_開始すると参加順の先頭が手番になり1ターン目になる(self) -> None:
        self.game.handle_host({"type": "start", "rounds": 5})

        self.assertEqual(self.game.phase, PLAYING)
        self.assertEqual(self.game.current, self.a.id)
        self.assertEqual((self.game.round, self.game.rounds), (1, 5))

    def test_参加者がいなければ開始できない(self) -> None:
        empty = Game()
        self.assertEqual(empty.handle_host({"type": "start"}), [])
        self.assertEqual(empty.phase, WAITING)

    def test_自分の番でなければふれない(self) -> None:
        self.game.handle_host({"type": "start"})

        self.assertEqual(self.game.handle(self.b.id, {"type": "roll"}), [])
        self.assertEqual(self.b.pos, 0)
        self.assertEqual(self.game.current, self.a.id)

    def test_ふると進んで手番が次に移る(self) -> None:
        self.game.handle_host({"type": "start"})

        self.game.handle(self.a.id, {"type": "roll"})

        self.assertEqual(self.a.pos, 2)
        self.assertEqual(self.game.current, self.b.id)
        self.assertEqual(self.game.last_roll["value"], 2)
        self.assertEqual(self.game.last_roll["from"], 0)
        self.assertEqual(self.game.last_roll["to"], 2)

    def test_手番の人が抜けたら次の人に移る(self) -> None:
        self.game.handle_host({"type": "start"})

        self.game.remove_player(self.a.id)

        self.assertEqual(self.game.current, self.b.id)
        self.assertEqual(self.game.round, 1)

    def test_全員抜けたら開始前に戻る(self) -> None:
        self.game.handle_host({"type": "start"})
        self.game.remove_player(self.a.id)
        self.game.remove_player(self.b.id)

        self.assertEqual(self.game.phase, WAITING)
        self.assertIsNone(self.game.current)
        self.assertEqual(self.game.round, 0)


class TestRounds(unittest.TestCase):
    def test_全員が1回ずつふると次のターンになる(self) -> None:
        game = Game(rng=FixedDice(2))
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start", "rounds": 3})

        game.handle(a.id, {"type": "roll"})
        self.assertEqual(game.round, 1)
        game.handle(b.id, {"type": "roll"})
        self.assertEqual(game.round, 2)
        self.assertEqual(game.current, a.id)

    def test_決めたターン数が終わるとゲーム終了(self) -> None:
        game = Game(rng=FixedDice(2, 5, 2, 5))
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start", "rounds": 2})

        for pid in (a.id, b.id, a.id):
            game.handle(pid, {"type": "roll"})
            self.assertEqual(game.phase, PLAYING)

        game.handle(b.id, {"type": "roll"})

        self.assertEqual(game.phase, FINISHED)
        self.assertIsNone(game.current)
        self.assertEqual(game.round, 2)                      # 3 にはならない
        self.assertEqual(game.handle(a.id, {"type": "roll"}), [])   # 終了後はふれない

    def test_最後の番の人が抜けても次のターンに進む(self) -> None:
        game = Game(rng=FixedDice(2))
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start", "rounds": 3})
        game.handle(a.id, {"type": "roll"})     # 次は B（最後の人）

        game.remove_player(b.id)

        self.assertEqual(game.current, a.id)
        self.assertEqual(game.round, 2)

    def test_最終ターンの休みの人も飛ばされて終了する(self) -> None:
        game = Game(rng=FixedDice(9, 2))
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start", "rounds": 2})
        game.handle(a.id, {"type": "roll"})     # A は一回休み
        game.handle(b.id, {"type": "roll"})     # 2ターン目、A を飛ばして B

        self.assertEqual((game.round, game.current), (2, b.id))

        game.handle(b.id, {"type": "roll"})

        self.assertEqual(game.phase, FINISHED)

    def test_ターン数は範囲に収められる(self) -> None:
        self.assertEqual(parse_rounds(0), 1)
        self.assertEqual(parse_rounds(999), MAX_ROUNDS)
        self.assertEqual(parse_rounds("7"), 7)
        self.assertEqual(parse_rounds("あ"), DEFAULT_ROUNDS)
        self.assertEqual(parse_rounds(None), DEFAULT_ROUNDS)

    def test_ターン数を省くと前回と同じ(self) -> None:
        game = Game()
        game.add_player("A")
        game.handle_host({"type": "start", "rounds": 4})

        game.handle_host({"type": "start"})

        self.assertEqual(game.rounds, 4)


class TestLoop(unittest.TestCase):
    def test_最後のマスを越えるとスタートに戻り給料がもらえる(self) -> None:
        game, p = solo(4)
        p.pos = 28                              # 28 + 4 = 32 → 2（通常マス）

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.pos, 2)
        self.assertEqual(p.money, board.START_MONEY + board.SALARY)
        r = game.last_roll
        self.assertEqual((r["from"], r["land"], r["to"]), (28, 2, 2))
        self.assertEqual(r["salary"], board.SALARY)

    def test_スタートにちょうど止まっても給料がもらえる(self) -> None:
        game, p = solo(2)
        p.pos = 28

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.pos, 0)
        self.assertEqual(p.money, board.START_MONEY + board.SALARY)

    def test_ワープでスタートを越えても給料がもらえる(self) -> None:
        game, p = solo(2)
        p.pos = 25                              # 27 に止まる → ワープ +3 → 0

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertEqual((r["land"], r["to"], r["shift"]), (27, 0, 3))
        self.assertEqual(r["salary"], board.SALARY)
        self.assertEqual(p.money, board.START_MONEY + board.SALARY)

    def test_戻ってスタートを越えても給料は出ない(self) -> None:
        game, p = solo(2)
        p.pos = 1

        salary = game._move(p, -3)              # 1 → 0 → 29 → 28

        self.assertEqual(p.pos, 28)
        self.assertEqual(salary, 0)
        self.assertEqual(p.money, board.START_MONEY)

    def test_ぴったり止まらなくても半分の位置を通過すると大金がもらえる(self) -> None:
        game, p = solo(10)
        p.pos = 10                              # 10 + 10 = 20。15（半分）を通過する

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertEqual(r["to"], 20)
        self.assertEqual(r["half"], board.HALF_BONUS)
        self.assertEqual(p.money, board.START_MONEY + board.HALF_BONUS)

    def test_半分の位置にちょうど止まっても大金がもらえる(self) -> None:
        game, p = solo(5)
        p.pos = 10                              # 15（半分）にちょうど止まる。ここは「もどる-3」でもある

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertEqual(r["land"], board.HALF)
        self.assertEqual(r["half"], board.HALF_BONUS)
        self.assertEqual(r["shift"], -3)        # 半分ボーナスとマスの効果は両方乗る

    def test_半分の位置を通過しなければ大金は出ない(self) -> None:
        game, p = solo(3)
        p.pos = 10                              # 13どまり。15には届かない

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(game.last_roll["half"], 0)
        self.assertEqual(p.money, board.START_MONEY)

    def test_ワープで半分の位置を越えても大金がもらえる(self) -> None:
        game, p = solo(2)
        p.pos = 10                              # 12（ワープ+3）に止まる → 15まで進む

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertEqual((r["land"], r["to"], r["shift"]), (12, 15, 3))
        self.assertEqual(r["half"], board.HALF_BONUS)

    def test_戻って半分の位置を通っても大金は出ない(self) -> None:
        game, p = solo(2)
        p.pos = 17

        game._move(p, -3)                       # 17 → 14。半分(15)を逆向きに通る

        self.assertEqual(p.money, board.START_MONEY)

    def test_半分とスタートを同時に越えても両方もらえる(self) -> None:
        game, p = solo(20)
        p.pos = 10                              # 10 + 20 = 30 → 0。15とスタートの両方を越える

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertEqual(r["to"], 0)
        self.assertEqual(r["salary"], board.SALARY)
        self.assertEqual(r["half"], board.HALF_BONUS)
        self.assertEqual(p.money, board.START_MONEY + board.SALARY + board.HALF_BONUS)

    def test_位置はつねに盤の中に収まる(self) -> None:
        game, p = solo(6, 5, 4, 3, 2, 1)
        for _ in range(40):
            while p.over:      # 溢れたカードを捨てないと振れない
                game.handle(p.id, {"type": "discard", "uid": p.hand[0].uid})
            game.handle(p.id, {"type": "roll"})
            self.assertTrue(0 <= p.pos < board.SIZE)


class TestSquares(unittest.TestCase):
    def test_進むマスで追加で進む(self) -> None:
        game, p = solo(3)          # 3 は「ワープ +2」

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.pos, 5)
        self.assertEqual(game.last_roll["effect"], board.BOARD[3].label)
        self.assertEqual(game.last_roll["shift"], 2)

    def test_戻るマスで下がる(self) -> None:
        game, p = solo(6)          # 6 は「もどる -2」

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.pos, 4)
        self.assertEqual(game.last_roll["shift"], -2)

    def test_もらうマスでお金が増える(self) -> None:
        game, p = solo(4)          # 4 は「+200円」

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.money, board.START_MONEY + 200)
        self.assertEqual(game.last_roll["gain"], 200)
        self.assertEqual(game.last_roll["before"], board.START_MONEY)
        self.assertEqual(game.last_roll["money"], p.money)

    def test_はらうマスでお金が減る(self) -> None:
        game, p = solo(5)          # 5 は「-100円」

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.money, board.START_MONEY - 100)
        self.assertEqual(game.last_roll["gain"], -100)

    def test_所持金はマイナスにならない(self) -> None:
        game, p = solo(5)
        p.money = 30

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.money, 0)
        self.assertEqual(game.last_roll["gain"], -30)   # 実際に減った額

    def test_通常マスでは何も起きない(self) -> None:
        game, p = solo(2)

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertIsNone(r["effect"])
        self.assertEqual((r["shift"], r["gain"], r["salary"]), (0, 0, 0))
        self.assertEqual(p.money, board.START_MONEY)

    def test_休みマスは次の番を飛ばす(self) -> None:
        game = Game(rng=FixedDice(9, 2))
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start"})

        game.handle(a.id, {"type": "roll"})   # A が 9（一回休み）に止まる

        self.assertTrue(a.resting)
        self.assertEqual(game.current, b.id)

        game.handle(b.id, {"type": "roll"})   # B の番。次は A を飛ばして B に戻る

        self.assertFalse(a.resting)           # 休みを消化した
        self.assertEqual(game.current, b.id)

    def test_ひとりでも休みで手番が消えない(self) -> None:
        game, p = solo(9, 2)

        game.handle(p.id, {"type": "roll"})   # 一回休みに止まる

        self.assertEqual(game.current, p.id)  # 他に誰もいないので自分に戻る
        self.assertFalse(p.resting)
        self.assertEqual(game.phase, PLAYING)
        self.assertEqual(game.round, 3)       # 休んだぶんのターンも進む


class TestStartFinishFromPhone(unittest.TestCase):
    """開始と終了はPC画面からでもスマホからでもできる。"""

    def setUp(self) -> None:
        self.game = Game(rng=FixedDice(2))
        self.a, _ = self.game.add_player("A")
        self.b, _ = self.game.add_player("B")

    def test_スマホから開始できる(self) -> None:
        events = self.game.handle(self.b.id, {"type": "start", "rounds": 4})

        self.assertEqual(self.game.phase, PLAYING)
        self.assertEqual((self.game.round, self.game.rounds), (1, 4))
        self.assertEqual(self.game.current, self.a.id)      # 手番は参加順の先頭から
        self.assertEqual([e.to for e in events], [HOSTS, self.a.id, self.b.id])

    def test_遊んでいる最中の開始は無視される(self) -> None:
        self.game.handle_host({"type": "start", "rounds": 4})
        self.game.handle(self.a.id, {"type": "roll"})

        self.assertEqual(self.game.handle(self.b.id, {"type": "start"}), [])
        self.assertEqual(self.game.handle_host({"type": "start"}), [])
        self.assertEqual(self.a.pos, 2)                      # 進行が消えていない
        self.assertEqual(self.game.current, self.b.id)

    def test_スマホから終了できその時点の所持金で順位がつく(self) -> None:
        self.game.handle_host({"type": "start", "rounds": 10})
        self.a.money = 1500

        events = self.game.handle(self.b.id, {"type": "finish"})

        self.assertEqual(self.game.phase, FINISHED)
        self.assertIsNone(self.game.current)
        self.assertEqual(self.game.ranks(), {self.a.id: 1, self.b.id: 2})
        self.assertEqual([e.to for e in events], [HOSTS, self.a.id, self.b.id])

    def test_PC画面からも終了できる(self) -> None:
        self.game.handle_host({"type": "start"})

        self.game.handle_host({"type": "finish"})

        self.assertEqual(self.game.phase, FINISHED)

    def test_遊んでいないときの終了は無視される(self) -> None:
        self.assertEqual(self.game.handle(self.a.id, {"type": "finish"}), [])
        self.assertEqual(self.game.phase, WAITING)

        self.game.handle_host({"type": "start"})
        self.game.handle_host({"type": "finish"})

        self.assertEqual(self.game.handle_host({"type": "finish"}), [])

    def test_終了後にスマホから再開できる(self) -> None:
        self.game.handle_host({"type": "start", "rounds": 10})
        self.game.handle(self.a.id, {"type": "roll"})
        self.game.handle_host({"type": "finish"})

        self.game.handle(self.b.id, {"type": "start", "rounds": 2})

        self.assertEqual(self.game.phase, PLAYING)
        self.assertEqual(self.a.pos, 0)
        self.assertEqual(self.a.money, board.START_MONEY)
        self.assertEqual((self.game.round, self.game.rounds), (1, 2))


class TestRanking(unittest.TestCase):
    def test_所持金の多い順に順位がつく(self) -> None:
        game = Game()
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        c, _ = game.add_player("C")
        a.money, b.money, c.money = 500, 1500, 900

        ranks = {p["id"]: p["rank"] for p in game.state()["players"]}

        self.assertEqual(ranks, {b.id: 1, c.id: 2, a.id: 3})

    def test_同じ額なら同じ順位で次は飛ぶ(self) -> None:
        game = Game()
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        c, _ = game.add_player("C")
        a.money, b.money, c.money = 800, 800, 300

        self.assertEqual(game.ranks(), {a.id: 1, b.id: 1, c.id: 3})

    def test_終了時に一番多い人が1位(self) -> None:
        game = Game(rng=FixedDice(4, 5))       # A は +200円、B は -100円
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start", "rounds": 1})

        game.handle(a.id, {"type": "roll"})
        game.handle(b.id, {"type": "roll"})

        self.assertEqual(game.phase, FINISHED)
        self.assertEqual(game.ranks(), {a.id: 1, b.id: 2})


class TestRestart(unittest.TestCase):
    def test_リセットで全員スタートに戻り所持金も戻る(self) -> None:
        game, p = solo(4)
        game.handle(p.id, {"type": "roll"})

        game.handle_host({"type": "reset"})

        self.assertEqual(p.pos, 0)
        self.assertEqual(p.money, board.START_MONEY)
        self.assertEqual(game.phase, WAITING)
        self.assertEqual(game.round, 0)
        self.assertIsNone(game.last_roll)

    def test_もう一度開始すると位置も所持金もターンも初期化される(self) -> None:
        game, p = solo(4, rounds=1)
        game.handle(p.id, {"type": "roll"})
        self.assertEqual(game.phase, FINISHED)

        game.handle_host({"type": "start", "rounds": 3})

        self.assertEqual(p.pos, 0)
        self.assertEqual(p.money, board.START_MONEY)
        self.assertEqual(game.phase, PLAYING)
        self.assertEqual((game.round, game.rounds), (1, 3))
        self.assertEqual(game.current, p.id)


class TestState(unittest.TestCase):
    def test_stateに盤面と全員の位置と所持金と順位が入る(self) -> None:
        game = Game()
        a, _ = game.add_player("A")

        state = game.state()

        self.assertEqual(state["type"], "state")
        self.assertEqual(state["size"], board.SIZE)
        self.assertEqual(state["salary"], board.SALARY)
        self.assertEqual(state["half_pos"], board.HALF)
        self.assertEqual(state["half_bonus"], board.HALF_BONUS)
        self.assertEqual(state["card_limit"], cards.LIMIT)
        self.assertEqual(len(state["board"]), board.SIZE)
        self.assertEqual((state["round"], state["rounds"]), (0, DEFAULT_ROUNDS))
        player = state["players"][0]
        self.assertEqual(player["id"], a.id)
        self.assertEqual(player["money"], board.START_MONEY)
        self.assertEqual(player["rank"], 1)

    def test_stateはPC画面と参加者ひとりずつへ送られる(self) -> None:
        game = Game()
        a, _ = game.add_player("A")
        b, events = game.add_player("B")

        # 手札を持ち主にしか見せないので、参加者には同じものを配れない
        self.assertEqual([e.to for e in events[1:]], [HOSTS, a.id, b.id])


class TestRollPayload(unittest.TestCase):
    """画面のアニメーションが使う情報。

    land = サイコロの出目ぶん進んだ位置（マスの効果を受ける前）
    to   = マスの効果まで反映した最終位置
    この2つが分かれていないと「1マスずつ進んでから効果で動く」が描けない。
    """

    def test_効果のないマスではlandとtoが一致する(self) -> None:
        game, _ = solo(2)
        game.handle(game.current, {"type": "roll"})

        r = game.last_roll
        self.assertEqual((r["from"], r["land"], r["to"]), (0, 2, 2))
        self.assertIsNone(r["effect"])

    def test_進むマスではlandとtoが分かれる(self) -> None:
        game, _ = solo(3)
        game.handle(game.current, {"type": "roll"})

        r = game.last_roll
        self.assertEqual((r["from"], r["land"], r["to"]), (0, 3, 5))

    def test_戻るマスではtoがlandより手前になる(self) -> None:
        game, _ = solo(6)
        game.handle(game.current, {"type": "roll"})

        r = game.last_roll
        self.assertEqual((r["from"], r["land"], r["to"]), (0, 6, 4))

    def test_seqは振るたびに増える(self) -> None:
        game, p = solo(2)

        seqs = []
        for _ in range(3):
            game.handle(p.id, {"type": "roll"})
            seqs.append(game.last_roll["seq"])

        self.assertEqual(seqs, [1, 2, 3])

    def test_金額の記録は画面の足し算と一致する(self) -> None:
        # 画面は before に salary・half・gain を足しながら表示し、最後に money で締める
        for rolls, start in [((1,), 0), ((4,), 28), ((2,), 25), ((5,), 0), ((10,), 10)]:
            game, p = solo(*rolls)
            p.pos = start
            game.handle(p.id, {"type": "roll"})
            r = game.last_roll
            self.assertEqual(r["before"] + r["salary"] + r["half"] + r["gain"], r["money"])

    def test_リセットするとlast_rollが消える(self) -> None:
        game, p = solo(2)
        game.handle(p.id, {"type": "roll"})

        game.handle_host({"type": "reset"})

        self.assertIsNone(game.last_roll)


class TestCards(unittest.TestCase):
    """カード。ひく・使う・捨てる・持っているだけで効く。"""

    def test_カードマスに止まると1枚もらえる(self) -> None:
        game, p = solo(1, cards=[cards.ADVANCE_2])      # 1 はカードマス

        game.handle(p.id, {"type": "roll"})

        self.assertEqual([h.card for h in p.hand], [cards.ADVANCE_2])
        self.assertTrue(game.last_roll["drew"])
        self.assertEqual(game.last_roll["effect"], board.BOARD[1].label)

    def test_カードマス以外ではひかない(self) -> None:
        game, p = solo(2)                               # 2 は通常マス

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.hand, [])
        self.assertFalse(game.last_roll["drew"])

    def test_手札の中身は本人にしか届かない(self) -> None:
        game = Game(rng=FixedDice(1, cards=[cards.ADVANCE_2]))
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start"})

        events = game.handle(a.id, {"type": "roll"})

        # PC画面と全員に配る分には、枚数しか入っていない
        public = next(e.payload for e in events if e.to == HOSTS)
        self.assertNotIn("you", public)
        self.assertTrue(all("hand" not in pl for pl in public["players"]))
        self.assertEqual([pl["cards"] for pl in public["players"]], [1, 0])

        # 本人にだけ中身が届く
        mine = next(e.payload for e in events if e.to == a.id)
        self.assertEqual([c["label"] for c in mine["you"]["hand"]], [cards.ADVANCE_2.label])
        self.assertEqual(mine["you"]["drew"]["label"], cards.ADVANCE_2.label)

        # 他の人には自分の手札（空）だけが届く
        theirs = next(e.payload for e in events if e.to == b.id)
        self.assertEqual(theirs["you"]["hand"], [])
        self.assertIsNone(theirs["you"]["drew"])

    def test_進むカードは出目に足される(self) -> None:
        game, p = solo(1, 2, cards=[cards.ADVANCE_2])
        game.handle(p.id, {"type": "roll"})             # 1 でカードをひく

        game.handle(p.id, {"type": "use", "uid": p.hand[0].uid})

        self.assertEqual((p.bonus, p.hand), (2, []))    # 使ったカードは消える

        game.handle(p.id, {"type": "roll"})             # 出目2 + カード2 = 4

        r = game.last_roll
        self.assertEqual((r["values"], r["bonus"], r["value"]), ([2], 2, 4))
        self.assertEqual(p.pos, 5)
        self.assertEqual(p.bonus, 0)                    # 1回で使い切る

    def test_サイコロ2個のカードで2個ふる(self) -> None:
        game, p = solo(1, 3, 4, cards=[cards.DOUBLE])
        game.handle(p.id, {"type": "roll"})

        game.handle(p.id, {"type": "use", "uid": p.hand[0].uid})

        self.assertEqual(p.dice, 2)

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertEqual((r["values"], r["value"]), ([3, 4], 7))
        self.assertEqual(p.dice, 1)                     # 1回で戻る

    def test_サイコロが2個なら2枚目は手札に残る(self) -> None:
        game, p = solo(1, cards=[cards.DOUBLE])
        game.handle(p.id, {"type": "roll"})
        game._draw(p)                                   # 同じカードを2枚持つ

        game.handle(p.id, {"type": "use", "uid": p.hand[0].uid})
        self.assertEqual(p.dice, 2)

        self.assertEqual(game.handle(p.id, {"type": "use", "uid": p.hand[0].uid}), [])
        self.assertEqual(len(p.hand), 1)                # 無駄にならない

    def test_おまもりは持っているだけで支払いを無効にする(self) -> None:
        game, p = solo(1, 4, cards=[cards.GUARD])
        game.handle(p.id, {"type": "roll"})             # 1 でおまもりをひく

        game.handle(p.id, {"type": "roll"})             # 1 → 5 は「はらう -100円」

        self.assertEqual(p.money, board.START_MONEY)
        self.assertEqual(game.last_roll["blocked"], 100)
        self.assertEqual(game.last_roll["gain"], 0)
        self.assertEqual(p.hand, [])                    # 1回で消える

    def test_おまもりが無ければ払う(self) -> None:
        game, p = solo(5)

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.money, board.START_MONEY - 100)
        self.assertEqual(game.last_roll["blocked"], 0)

    def test_おまもりは手では使えない(self) -> None:
        game, p = solo(1, cards=[cards.GUARD])
        game.handle(p.id, {"type": "roll"})

        self.assertEqual(game.handle(p.id, {"type": "use", "uid": p.hand[0].uid}), [])
        self.assertEqual(len(p.hand), 1)

    def test_自分の番でなければ使えない(self) -> None:
        game = Game(rng=FixedDice(1, cards=[cards.ADVANCE_2]))
        a, _ = game.add_player("A")
        game.add_player("B")
        game.handle_host({"type": "start"})
        game.handle(a.id, {"type": "roll"})             # 手番は B に移った

        self.assertEqual(game.handle(a.id, {"type": "use", "uid": a.hand[0].uid}), [])
        self.assertEqual(len(a.hand), 1)

    def test_上限を超えたら捨てるまで何もできない(self) -> None:
        game, p = solo(2, cards=[cards.ADVANCE_1])
        for _ in range(cards.LIMIT + 1):
            game._draw(p)

        self.assertEqual(p.over, 1)
        self.assertEqual(game.handle(p.id, {"type": "roll"}), [])
        self.assertEqual(game.handle(p.id, {"type": "use", "uid": p.hand[0].uid}), [])

        game.handle(p.id, {"type": "discard", "uid": p.hand[0].uid})

        self.assertEqual((p.over, len(p.hand)), (0, cards.LIMIT))
        self.assertNotEqual(game.handle(p.id, {"type": "roll"}), [])

    def test_捨てるカードは自分で選ぶ(self) -> None:
        deck = [cards.ADVANCE_1, cards.ADVANCE_2, cards.ADVANCE_3, cards.DOUBLE]
        game, p = solo(2, cards=deck)
        for _ in range(4):
            game._draw(p)

        game.handle(p.id, {"type": "discard", "uid": p.hand[1].uid})   # 2枚目を選ぶ

        self.assertEqual([h.card for h in p.hand],
                         [cards.ADVANCE_1, cards.ADVANCE_3, cards.DOUBLE])

    def test_溢れていなければ捨てられない(self) -> None:
        game, p = solo(1, cards=[cards.ADVANCE_1])
        game.handle(p.id, {"type": "roll"})

        self.assertEqual(game.handle(p.id, {"type": "discard", "uid": p.hand[0].uid}), [])
        self.assertEqual(len(p.hand), 1)

    def test_いないカードの指定は無視される(self) -> None:
        game, p = solo(1, cards=[cards.ADVANCE_1])
        game.handle(p.id, {"type": "roll"})

        self.assertEqual(game.handle(p.id, {"type": "use", "uid": "無効"}), [])
        self.assertEqual(game.handle(p.id, {"type": "discard", "uid": "無効"}), [])
        self.assertEqual(len(p.hand), 1)

    def test_リセットで手札と使いかけの効果が消える(self) -> None:
        game, p = solo(1, 2, cards=[cards.DOUBLE])
        game.handle(p.id, {"type": "roll"})
        game.handle(p.id, {"type": "use", "uid": p.hand[0].uid})
        game._draw(p)
        self.assertEqual((p.dice, len(p.hand)), (2, 1))

        events = game.handle_host({"type": "reset"})

        self.assertEqual((p.hand, p.bonus, p.dice), ([], 0, 1))
        mine = next(e.payload for e in events if e.to == p.id)
        self.assertIsNone(mine["you"]["drew"])          # ひいた記録も消える

    def test_もう一度あそぶと手札も消える(self) -> None:
        game, p = solo(1, rounds=1, cards=[cards.ADVANCE_2])
        game.handle(p.id, {"type": "roll"})      # 1ターンだけなのでここで終了する
        self.assertEqual((game.phase, len(p.hand)), (FINISHED, 1))

        game.handle_host({"type": "start", "rounds": 3})

        self.assertEqual(p.hand, [])

    def test_山札のカードは使い道が揃っている(self) -> None:
        kinds = {c.kind for c in cards.DECK}
        self.assertEqual(kinds, {"advance", "double", "guard"})
        # 自動で発動するのはおまもりだけ
        self.assertEqual({c.label for c in cards.DECK if c.passive}, {cards.GUARD.label})
        for card in cards.DECK:
            # 画面に出す文字が欠けていない（label と short は札の表、desc は押したとき）
            self.assertTrue(card.label and card.short and card.desc)


if __name__ == "__main__":
    unittest.main()

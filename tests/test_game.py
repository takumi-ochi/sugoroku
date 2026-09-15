"""すごろくのルールの単体テスト。

サーバーもWebSocketも起動しない。通信層と分離してあるからこれができる。
サイコロは差し替えられるので、出目を固定して検証する。

    .venv/Scripts/python.exe -m unittest discover -s tests -t . -v
"""

import unittest

from game import board
from game.events import HOSTS, PLAYERS
from game.logic import (
    COLORS, DEFAULT_ROUNDS, FINISHED, MAX_ROUNDS, PLAYING, WAITING, Game, parse_rounds,
)


class FixedDice:
    """指定した順に出目を返すサイコロ。尽きたら最後の値を返し続ける。"""

    def __init__(self, *values: int) -> None:
        self.values = list(values)

    def randint(self, a: int, b: int) -> int:
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


def solo(*rolls: int, rounds: int = 99) -> tuple[Game, object]:
    game = Game(rng=FixedDice(*rolls))
    player, _ = game.add_player("ひとり")
    game.handle_host({"type": "start", "rounds": min(rounds, MAX_ROUNDS)})
    return game, player


class TestBoard(unittest.TestCase):
    """テストが前提にしているマス。盤を変えたらここが先に落ちる。"""

    def test_前提のマス(self) -> None:
        self.assertEqual(board.BOARD[0].kind, "start")
        self.assertEqual((board.BOARD[1].kind, board.BOARD[1].value), ("gain", 100))
        self.assertEqual(board.BOARD[2].kind, "normal")
        self.assertEqual((board.BOARD[3].kind, board.BOARD[3].value), ("forward", 2))
        self.assertEqual((board.BOARD[5].kind, board.BOARD[5].value), ("lose", 100))
        self.assertEqual((board.BOARD[6].kind, board.BOARD[6].value), ("back", 2))
        self.assertEqual(board.BOARD[7].kind, "normal")
        self.assertEqual(board.BOARD[9].kind, "rest")
        self.assertEqual((board.BOARD[27].kind, board.BOARD[27].value), ("forward", 3))
        self.assertEqual((board.BOARD[29].kind, board.BOARD[29].value), ("lose", 500))
        self.assertNotIn("goal", {s.kind for s in board.BOARD})


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
            [(player.id, "joined"), (HOSTS, "state"), (PLAYERS, "state")],
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

    def test_位置はつねに盤の中に収まる(self) -> None:
        game, p = solo(6, 5, 4, 3, 2, 1)
        for _ in range(40):
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
        game, p = solo(1)          # 1 は「+100円」

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.money, board.START_MONEY + 100)
        self.assertEqual(game.last_roll["gain"], 100)
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
        game = Game(rng=FixedDice(1, 5))       # A は +100円、B は -100円
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start", "rounds": 1})

        game.handle(a.id, {"type": "roll"})
        game.handle(b.id, {"type": "roll"})

        self.assertEqual(game.phase, FINISHED)
        self.assertEqual(game.ranks(), {a.id: 1, b.id: 2})


class TestRestart(unittest.TestCase):
    def test_リセットで全員スタートに戻り所持金も戻る(self) -> None:
        game, p = solo(1)
        game.handle(p.id, {"type": "roll"})

        game.handle_host({"type": "reset"})

        self.assertEqual(p.pos, 0)
        self.assertEqual(p.money, board.START_MONEY)
        self.assertEqual(game.phase, WAITING)
        self.assertEqual(game.round, 0)
        self.assertIsNone(game.last_roll)

    def test_もう一度開始すると位置も所持金もターンも初期化される(self) -> None:
        game, p = solo(1, rounds=1)
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
        self.assertEqual(len(state["board"]), board.SIZE)
        self.assertEqual((state["round"], state["rounds"]), (0, DEFAULT_ROUNDS))
        player = state["players"][0]
        self.assertEqual(player["id"], a.id)
        self.assertEqual(player["money"], board.START_MONEY)
        self.assertEqual(player["rank"], 1)

    def test_stateはPC画面とスマホの両方へ送られる(self) -> None:
        game = Game()
        _, events = game.add_player("A")

        self.assertEqual([e.to for e in events[1:]], [HOSTS, PLAYERS])


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
        # 画面は before に salary と gain を足しながら表示し、最後に money で締める
        for rolls, start in [((1,), 0), ((4,), 28), ((2,), 25), ((5,), 0)]:
            game, p = solo(*rolls)
            p.pos = start
            game.handle(p.id, {"type": "roll"})
            r = game.last_roll
            self.assertEqual(r["before"] + r["salary"] + r["gain"], r["money"])

    def test_リセットするとlast_rollが消える(self) -> None:
        game, p = solo(2)
        game.handle(p.id, {"type": "roll"})

        game.handle_host({"type": "reset"})

        self.assertIsNone(game.last_roll)


if __name__ == "__main__":
    unittest.main()

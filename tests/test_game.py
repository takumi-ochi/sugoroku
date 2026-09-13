"""すごろくのルールの単体テスト。

サーバーもWebSocketも起動しない。通信層と分離してあるからこれができる。
サイコロは差し替えられるので、出目を固定して検証する。

    .venv/Scripts/python.exe -m unittest discover -s tests -t . -v
"""

import unittest

from game import board
from game.events import HOSTS, PLAYERS
from game.logic import COLORS, FINISHED, PLAYING, WAITING, Game


class FixedDice:
    """指定した順に出目を返すサイコロ。尽きたら最後の値を返し続ける。"""

    def __init__(self, *values: int) -> None:
        self.values = list(values)

    def randint(self, a: int, b: int) -> int:
        return self.values.pop(0) if len(self.values) > 1 else self.values[0]


class TestJoinLeave(unittest.TestCase):
    def setUp(self) -> None:
        self.game = Game()

    def test_参加すると本人と全員に通知される(self) -> None:
        player, events = self.game.add_player("タロウ")

        self.assertEqual(player.name, "タロウ")
        self.assertEqual(player.pos, 0)
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
        self.game = Game(rng=FixedDice(1))
        self.a, _ = self.game.add_player("A")
        self.b, _ = self.game.add_player("B")

    def test_開始前はふれない(self) -> None:
        self.assertEqual(self.game.phase, WAITING)
        self.assertEqual(self.game.handle(self.a.id, {"type": "roll"}), [])
        self.assertEqual(self.a.pos, 0)

    def test_開始すると参加順の先頭が手番になる(self) -> None:
        self.game.handle_host({"type": "start"})

        self.assertEqual(self.game.phase, PLAYING)
        self.assertEqual(self.game.current, self.a.id)

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

        self.assertEqual(self.a.pos, 1)
        self.assertEqual(self.game.current, self.b.id)
        self.assertEqual(self.game.last_roll["value"], 1)
        self.assertEqual(self.game.last_roll["from"], 0)
        self.assertEqual(self.game.last_roll["to"], 1)

    def test_手番の人が抜けたら次の人に移る(self) -> None:
        self.game.handle_host({"type": "start"})

        self.game.remove_player(self.a.id)

        self.assertEqual(self.game.current, self.b.id)

    def test_全員抜けたら開始前に戻る(self) -> None:
        self.game.handle_host({"type": "start"})
        self.game.remove_player(self.a.id)
        self.game.remove_player(self.b.id)

        self.assertEqual(self.game.phase, WAITING)
        self.assertIsNone(self.game.current)


class TestSquares(unittest.TestCase):
    def _solo(self, *rolls: int) -> tuple[Game, object]:
        game = Game(rng=FixedDice(*rolls))
        player, _ = game.add_player("ひとり")
        game.handle_host({"type": "start"})
        return game, player

    def test_進むマスで追加で進む(self) -> None:
        game, p = self._solo(3)          # 3 は「ワープ +2」

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.pos, 5)
        self.assertEqual(game.last_roll["effect"], board.BOARD[3].label)

    def test_戻るマスで下がる(self) -> None:
        game, p = self._solo(6)          # 6 は「もどる -2」

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.pos, 4)

    def test_休みマスは次の番を飛ばす(self) -> None:
        game = Game(rng=FixedDice(9, 1))
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
        game, p = self._solo(9, 1)

        game.handle(p.id, {"type": "roll"})   # 一回休みに止まる

        self.assertEqual(game.current, p.id)  # 他に誰もいないので自分に戻る
        self.assertFalse(p.resting)
        self.assertEqual(game.phase, PLAYING)

    def test_戻るマスでもマイナスにならない(self) -> None:
        game = Game(rng=FixedDice(6, 4))
        p, _ = game.add_player("ひとり")
        game.handle_host({"type": "start"})
        game.handle(p.id, {"type": "roll"})   # 6 -> もどる -2 -> 4
        game.handle(p.id, {"type": "roll"})   # 8 は通常マス

        self.assertGreaterEqual(p.pos, 0)


class TestGoal(unittest.TestCase):
    def test_出目が余ってもゴールで止まる(self) -> None:
        game = Game(rng=FixedDice(6))
        p, _ = game.add_player("ひとり")
        p_start = board.GOAL - 2
        game.handle_host({"type": "start"})
        p.pos = p_start

        game.handle(p.id, {"type": "roll"})

        self.assertEqual(p.pos, board.GOAL)
        self.assertEqual(p.rank, 1)

    def test_ゴール順に順位がつき全員終わると終了する(self) -> None:
        game = Game(rng=FixedDice(6))
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start"})
        a.pos = board.GOAL - 1
        b.pos = board.GOAL - 1

        game.handle(a.id, {"type": "roll"})
        self.assertEqual(a.rank, 1)
        self.assertEqual(game.current, b.id)
        self.assertEqual(game.phase, PLAYING)

        game.handle(b.id, {"type": "roll"})
        self.assertEqual(b.rank, 2)
        self.assertEqual(game.phase, FINISHED)
        self.assertIsNone(game.current)

    def test_ゴール済みの人は飛ばされる(self) -> None:
        game = Game(rng=FixedDice(1))
        a, _ = game.add_player("A")
        b, _ = game.add_player("B")
        game.handle_host({"type": "start"})
        a.rank = 1
        a.pos = board.GOAL
        game.current = b.id

        game.handle(b.id, {"type": "roll"})

        self.assertEqual(game.current, b.id)   # A は飛ばされ B に戻る


class TestRestart(unittest.TestCase):
    def test_リセットで全員スタートに戻る(self) -> None:
        game = Game(rng=FixedDice(3))
        p, _ = game.add_player("A")
        game.handle_host({"type": "start"})
        game.handle(p.id, {"type": "roll"})

        game.handle_host({"type": "reset"})

        self.assertEqual(p.pos, 0)
        self.assertIsNone(p.rank)
        self.assertEqual(game.phase, WAITING)
        self.assertIsNone(game.last_roll)

    def test_もう一度開始すると位置も順位も初期化される(self) -> None:
        game = Game(rng=FixedDice(6))
        p, _ = game.add_player("A")
        game.handle_host({"type": "start"})
        p.pos = board.GOAL - 1
        game.handle(p.id, {"type": "roll"})
        self.assertEqual(game.phase, FINISHED)

        game.handle_host({"type": "start"})

        self.assertEqual(p.pos, 0)
        self.assertIsNone(p.rank)
        self.assertEqual(game.phase, PLAYING)
        self.assertEqual(game.current, p.id)


class TestState(unittest.TestCase):
    def test_stateに盤面と全員の位置が入る(self) -> None:
        game = Game()
        a, _ = game.add_player("A")

        state = game.state()

        self.assertEqual(state["type"], "state")
        self.assertEqual(state["goal"], board.GOAL)
        self.assertEqual(len(state["board"]), board.SIZE)
        self.assertEqual([p["id"] for p in state["players"]], [a.id])

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
        game = Game(rng=FixedDice(1))
        p, _ = game.add_player("A")
        game.handle_host({"type": "start"})

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertEqual((r["from"], r["land"], r["to"]), (0, 1, 1))
        self.assertIsNone(r["effect"])

    def test_進むマスではlandとtoが分かれる(self) -> None:
        game = Game(rng=FixedDice(3))          # 3 は「ワープ +2」
        p, _ = game.add_player("A")
        game.handle_host({"type": "start"})

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertEqual((r["from"], r["land"], r["to"]), (0, 3, 5))

    def test_戻るマスではtoがlandより手前になる(self) -> None:
        game = Game(rng=FixedDice(6))          # 6 は「もどる -2」
        p, _ = game.add_player("A")
        game.handle_host({"type": "start"})

        game.handle(p.id, {"type": "roll"})

        r = game.last_roll
        self.assertEqual((r["from"], r["land"], r["to"]), (0, 6, 4))

    def test_seqは振るたびに増える(self) -> None:
        game = Game(rng=FixedDice(1))
        p, _ = game.add_player("A")
        game.handle_host({"type": "start"})

        seqs = []
        for _ in range(3):
            game.handle(p.id, {"type": "roll"})
            seqs.append(game.last_roll["seq"])

        self.assertEqual(seqs, [1, 2, 3])

    def test_リセットするとlast_rollが消える(self) -> None:
        game = Game(rng=FixedDice(1))
        p, _ = game.add_player("A")
        game.handle_host({"type": "start"})
        game.handle(p.id, {"type": "roll"})

        game.handle_host({"type": "reset"})

        self.assertIsNone(game.last_roll)


if __name__ == "__main__":
    unittest.main()

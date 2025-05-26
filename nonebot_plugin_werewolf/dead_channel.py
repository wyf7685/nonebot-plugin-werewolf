import contextlib
from typing import NoReturn

import anyio
import anyio.lowlevel
from nonebot_plugin_alconna import UniMessage

from .config import GameBehavior
from .player import Player
from .player_set import PlayerSet


class DeadChannel:
    players: PlayerSet
    finished: anyio.Event
    counter: dict[str, int]

    def __init__(self, players: PlayerSet, finished: anyio.Event) -> None:
        self.players = players
        self.finished = finished
        self.counter = {p.user_id: 0 for p in players}

    async def _decrease(self, user_id: str) -> None:
        await anyio.sleep(60)
        self.counter[user_id] -= 1

    async def _wait_finished(self) -> None:
        await self.finished.wait()
        self._task_group.cancel_scope.cancel()

    async def _broadcast(self) -> NoReturn:
        stream = self.stream[1]
        while True:
            player, msg = await stream.receive()
            msg = UniMessage.text(f"玩家 {player.name}:\n") + msg
            target = self.players.killed().exclude(player)
            try:
                await target.broadcast(msg)
            except Exception as err:
                with contextlib.suppress(Exception):
                    await player.send(f"消息转发失败: {err!r}")

    async def _receive(self, player: Player) -> NoReturn:
        await player.killed.wait()
        await anyio.lowlevel.checkpoint()
        user_id = player.user_id
        stream = self.stream[0]

        await player.send(
            "ℹ️你已加入死者频道，请勿在群组内继续发言\n"
            "私聊发送消息将转发至其他已死亡玩家",
        )
        await (
            self.players.killed()
            .exclude(player)
            .broadcast(f"ℹ️玩家 {player.name} 加入了死者频道")
        )

        while True:
            msg = await player.receive()
            self.counter[user_id] += 1
            self._task_group.start_soon(self._decrease, user_id)

            # 发言频率限制
            if self.counter[user_id] > GameBehavior.get().dead_channel_rate_limit:
                await player.send("❌发言频率超过限制, 该消息被屏蔽")
                continue

            # 推送消息
            await stream.send((player, msg))

    async def run(self) -> None:
        self.stream = anyio.create_memory_object_stream[tuple[Player, UniMessage]](16)
        send, recv = self.stream
        async with send, recv, anyio.create_task_group() as self._task_group:
            self._task_group.start_soon(self._wait_finished)
            self._task_group.start_soon(self._broadcast)
            for p in self.players:
                self._task_group.start_soon(self._receive, p)

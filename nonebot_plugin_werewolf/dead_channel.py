import contextlib

import anyio
import anyio.lowlevel
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
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

    async def _broadcast(
        self, stream: MemoryObjectReceiveStream[tuple[Player, UniMessage]]
    ) -> None:
        async for player, msg in stream:
            try:
                await self.players.killed().exclude(player).broadcast(msg)
            except Exception as exc:
                with contextlib.suppress(Exception):
                    await player.send(f"消息转发失败: {exc!r}")

    async def _receive(
        self,
        player: Player,
        stream: MemoryObjectSendStream[tuple[Player, UniMessage]],
    ) -> None:
        await player.killed.wait()
        await anyio.lowlevel.checkpoint()
        user_id = player.user_id

        await player.send(
            "ℹ️你已加入死者频道，请勿在群组内继续发言\n"
            "私聊发送消息将转发至其他已死亡玩家",
        )
        await stream.send(
            (player, UniMessage.text(f"ℹ️玩家 {player.name} 加入了死者频道"))
        )

        async with stream:
            while True:
                msg = await player.receive()
                self.counter[user_id] += 1
                self._task_group.start_soon(self._decrease, user_id)

                # 发言频率限制
                if self.counter[user_id] > GameBehavior.get().dead_channel_rate_limit:
                    await player.send("❌发言频率超过限制, 该消息被屏蔽")
                    continue

                # 推送消息
                msg = UniMessage.text(f"玩家 {player.name}:\n") + msg
                await stream.send((player, msg))

    async def run(self) -> None:
        send, recv = anyio.create_memory_object_stream[tuple[Player, UniMessage]](16)
        async with anyio.create_task_group() as self._task_group:
            for p in self.players:
                self._task_group.start_soon(self._receive, p, send.clone())
            send.close()
            self._task_group.start_soon(self._broadcast, recv)
            await self.finished.wait()
            self._task_group.cancel_scope.cancel()

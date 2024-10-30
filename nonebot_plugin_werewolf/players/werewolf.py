from typing import TYPE_CHECKING

import anyio
import anyio.lowlevel
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from nonebot_plugin_alconna.uniseg import UniMessage
from typing_extensions import override

from ..constant import STOP_COMMAND, STOP_COMMAND_PROMPT
from ..models import Role, RoleGroup
from ..utils import check_index
from .player import Player

if TYPE_CHECKING:
    from ..player_set import PlayerSet


@Player.register_role(Role.Werewolf, RoleGroup.Werewolf)
class Werewolf(Player):
    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        partners = self.game.players.alive().select(RoleGroup.Werewolf).exclude(self)
        if partners:
            await self.send(
                "🐺你的队友:\n"
                + "\n".join(f"  {p.role_name}: {p.name}" for p in partners)
            )

    async def _handle_interact(
        self,
        players: "PlayerSet",
        stream: MemoryObjectSendStream[str | UniMessage],
        finished: anyio.Event,
    ) -> None:
        self.selected = None

        while True:
            input_msg = await self.receive()
            text = input_msg.extract_plain_text()
            index = check_index(text, len(players))
            if index is not None:
                self.selected = players[index - 1]
                msg = f"当前选择玩家: {self.selected.name}"
                await self.send(f"🎯{msg}\n发送 “{STOP_COMMAND_PROMPT}” 结束回合")
                await stream.send(f"📝队友 {self.name} {msg}")
            if text == STOP_COMMAND:
                if self.selected is not None:
                    await self.send("✅你已结束当前回合")
                    await stream.send(f"📝队友 {self.name} 结束当前回合")
                    finished.set()
                    return
                await self.send("⚠️当前未选择玩家，无法结束回合")
            else:
                await stream.send(UniMessage.text(f"💬队友 {self.name}:\n") + input_msg)

    async def _handle_broadcast(
        self,
        partners: "PlayerSet",
        stream: MemoryObjectReceiveStream[str | UniMessage],
        finished: anyio.Event,
    ) -> None:
        while True:
            if finished.is_set():
                return
            if not stream.statistics().tasks_waiting_receive:
                await anyio.lowlevel.checkpoint()
                continue
            message = await stream.receive()
            await partners.broadcast(message)

    @override
    async def interact(self) -> None:
        players = self.game.players.alive()
        partners = players.select(RoleGroup.Werewolf).exclude(self)

        msg = UniMessage()
        if partners:
            msg = (
                msg.text("🐺你的队友:\n")
                .text("\n".join(f"  {p.role_name}: {p.name}" for p in partners))
                .text("\n所有私聊消息将被转发至队友\n\n")
            )
        await self.send(
            msg.text("💫请选择今晚的目标:\n")
            .text(players.show())
            .text("\n\n🔪发送编号选择玩家")
            .text(f"\n❌发送 “{STOP_COMMAND_PROMPT}” 结束回合")
            .text("\n\n⚠️意见未统一将空刀")
        )

        send, recv = anyio.create_memory_object_stream[str | UniMessage](8)
        finished = anyio.Event()

        async with anyio.create_task_group() as tg:
            tg.start_soon(self._handle_interact, players, send, finished)
            tg.start_soon(self._handle_broadcast, partners, recv, finished)

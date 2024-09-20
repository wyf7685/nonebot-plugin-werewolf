from __future__ import annotations

import asyncio

from nonebot_plugin_alconna.uniseg import UniMessage
from typing_extensions import override

from ..constant import Role, RoleGroup
from ..utils import check_index
from .player import Player, register_role


@register_role(Role.Werewolf, RoleGroup.Werewolf)
class Werewolf(Player):
    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        partners = self.game.players.alive().select(RoleGroup.Werewolf).exclude(self)
        if partners:
            await self.send(
                "你的队友:\n"
                + "\n".join(f"  {p.role_name}: {p.name}" for p in partners)
            )

    @override
    async def interact(self) -> None:
        players = self.game.players.alive()
        partners = players.select(RoleGroup.Werewolf).exclude(self)

        # 避免阻塞
        def broadcast(msg: str | UniMessage) -> asyncio.Task[None]:
            return asyncio.create_task(partners.broadcast(msg))

        msg = UniMessage()
        if partners:
            msg = (
                msg.text("你的队友:\n")
                .text("\n".join(f"  {p.role_name}: {p.name}" for p in partners))
                .text("\n所有私聊消息将被转发至队友\n\n")
            )
        await self.send(
            msg.text("请选择今晚的目标:\n")
            .text(players.show())
            .text("\n\n发送编号选择玩家")
            .text("\n发送 “/stop” 结束回合")
            .text("\n\n意见未统一将空刀")
        )

        selected = None
        finished = False
        while selected is None or not finished:
            input_msg = await self.receive()
            text = input_msg.extract_plain_text()
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                msg = f"当前选择玩家: {players[selected].name}"
                await self.send(f"{msg}\n发送 “/stop” 结束回合")
                broadcast(f"队友 {self.name} {msg}")
            if text == "/stop":
                if selected is not None:
                    finished = True
                    await self.send("你已结束当前回合")
                    broadcast(f"队友 {self.name} 结束当前回合")
                else:
                    await self.send("当前未选择玩家，无法结束回合")
            broadcast(UniMessage.text(f"队友 {self.name}:\n") + input_msg)

        self.selected = players[selected]

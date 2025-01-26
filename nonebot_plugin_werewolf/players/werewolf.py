import secrets
from typing import TYPE_CHECKING
from typing_extensions import override

import anyio
import nonebot
from nonebot_plugin_alconna.uniseg import UniMessage

from ..constant import STOP_COMMAND, stop_command_prompt
from ..models import Role, RoleGroup
from ..utils import ObjectStream, check_index
from .player import Player

if TYPE_CHECKING:
    from ..player_set import PlayerSet

logger = nonebot.logger.opt(colors=True)


@Player.register_role(Role.WEREWOLF, RoleGroup.WEREWOLF)
class Werewolf(Player):
    interact_timeout = 120
    stream: ObjectStream[str | UniMessage]

    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        partners = self.game.players.alive().select(RoleGroup.WEREWOLF).exclude(self)
        if partners:
            await self.send(
                "🐺你的队友:\n"
                + "\n".join(f"  {p.role_name}: {p.name}" for p in partners)
            )

    async def _handle_interact(self, players: "PlayerSet") -> None:
        self.selected = None

        while True:
            input_msg = await self.receive()
            text = input_msg.extract_plain_text()
            index = check_index(text, len(players))
            if index is not None:
                self.selected = players[index - 1]
                msg = f"当前选择玩家: {self.selected.name}"
                await self.send(
                    f"🎯{msg}\n发送 “{stop_command_prompt()}” 结束回合",
                    stop_btn_label="结束回合",
                    select_players=players,
                )
                await self.stream.send(f"📝队友 {self.name} {msg}")
            if text == STOP_COMMAND:
                if self.selected is not None:
                    await self.send("✅你已结束当前回合")
                    await self.stream.send(f"📝队友 {self.name} 结束当前回合")
                    self.stream.close()
                    return
                await self.send(
                    "⚠️当前未选择玩家，无法结束回合",
                    select_players=players,
                )
            else:
                await self.stream.send(
                    UniMessage.text(f"💬队友 {self.name}:\n") + input_msg
                )

    async def _handle_broadcast(self, partners: "PlayerSet") -> None:
        while not self.stream.closed:
            try:
                message = await self.stream.recv()
            except anyio.EndOfStream:
                return

            await partners.broadcast(message)

    @override
    async def _interact(self) -> None:
        players = self.game.players.alive()
        partners = players.select(RoleGroup.WEREWOLF).exclude(self)

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
            .text(f"\n❌发送 “{stop_command_prompt()}” 结束回合")
            .text("\n\n⚠️意见未统一将空刀"),
            select_players=players,
        )

        self.stream = ObjectStream[str | UniMessage](8)

        try:
            async with anyio.create_task_group() as tg:
                tg.start_soon(self._handle_interact, players)
                tg.start_soon(self._handle_broadcast, partners)
        finally:
            del self.stream

    @override
    async def _after_interact(self) -> None:
        state = self.game.state
        if not state.werewolf_finished.is_set():
            state.werewolf_finished.set()
            w = self.game.players.alive().select(RoleGroup.WEREWOLF)
            if (s := w.player_selected()).size == 1:
                state.killed = s.pop()
                await w.broadcast(f"🔪今晚选择的目标为: {state.killed.name}")
            else:
                await w.broadcast("⚠️狼人阵营意见未统一，此晚空刀")

        if not self.game.players.alive().select(Role.WITCH):
            await anyio.sleep(5 + secrets.randbelow(15))

import secrets
from typing import TYPE_CHECKING
from typing_extensions import override

import anyio
from nonebot_plugin_alconna import UniMessage

from ..config import stop_command_prompt
from ..constant import STOP_COMMAND
from ..models import Role, RoleGroup
from ..player import InteractProvider, NotifyProvider, Player
from ..utils import as_player_set, check_index

if TYPE_CHECKING:
    from ..player_set import PlayerSet


class WerewolfInteractProvider(InteractProvider["Werewolf"]):
    @override
    async def before(self) -> None:
        self.game.context.werewolf_start()

    async def handle_interact(self, players: "PlayerSet") -> None:
        stream = self.stream[0]
        self.selected = None

        while True:
            input_msg = await self.p.receive()
            text = input_msg.extract_plain_text()
            index = check_index(text, len(players))
            if index is not None:
                self.selected = players[index - 1]
                msg = f"当前选择玩家: {self.selected.name}"
                await self.p.send(
                    f"🎯{msg}\n发送 “{stop_command_prompt}” 结束回合",
                    stop_btn_label="结束回合",
                    select_players=players,
                )
                await stream.send(f"📝队友 {self.p.name} {msg}")
            if text == STOP_COMMAND:
                if self.selected is not None:
                    await self.p.send("✅你已结束当前回合")
                    await stream.send(f"📝队友 {self.p.name} 结束当前回合")
                    stream.close()
                    return
                await self.p.send(
                    "⚠️当前未选择玩家，无法结束回合",
                    select_players=players,
                )
            else:
                await stream.send(
                    UniMessage.text(f"💬队友 {self.p.name}:\n") + input_msg
                )

    async def handle_broadcast(self, partners: "PlayerSet") -> None:
        stream = self.stream[1]
        while True:
            try:
                message = await stream.receive()
            except anyio.EndOfStream:
                return

            await partners.broadcast(message)

    @override
    async def interact(self) -> None:
        players = self.game.players.alive()
        partners = players.select(RoleGroup.WEREWOLF).exclude(self.p)

        msg = UniMessage()
        if partners:
            msg = (
                msg.text("🐺你的队友:\n")
                .text("\n".join(f"  {p.role_name}: {p.name}" for p in partners))
                .text("\n所有私聊消息将被转发至队友\n\n")
            )
        await self.p.send(
            msg.text("💫请选择今晚的目标:\n")
            .text(players.show())
            .text("\n\n🔪发送编号选择玩家")
            .text(f"\n❌发送 “{stop_command_prompt}” 结束回合")
            .text("\n\n⚠️意见未统一将空刀"),
            select_players=players,
        )

        self.stream = anyio.create_memory_object_stream[str | UniMessage](8)
        send, recv = self.stream

        async with send, recv, anyio.create_task_group() as tg:
            tg.start_soon(self.handle_interact, players)
            tg.start_soon(self.handle_broadcast, partners)

    async def finalize(self) -> None:
        w = self.game.players.alive().select(RoleGroup.WEREWOLF)
        match w.player_selected().shuffled:
            case []:
                await w.broadcast("⚠️狼人未选择目标，此晚空刀")
            case [killed]:
                self.game.context.killed = killed
                await w.broadcast(f"🔪今晚选择的目标为: {killed.name}")
            case [killed, *_] if self.game.behavior.werewolf_multi_select:
                self.game.context.killed = killed
                await w.broadcast(
                    "⚠️狼人阵营意见未统一，随机选择目标\n\n"
                    f"🔪今晚选择的目标为: {killed.name}"
                )
            case players:
                await w.broadcast(
                    f"⚠️狼人阵营意见未统一，此晚空刀\n\n"
                    f"📝选择的玩家:\n{as_player_set(*players).show()}"
                )

    @override
    async def after(self) -> None:
        if self.game.context.werewolf_end():
            await self.finalize()

        if not self.game.players.alive().select(Role.WITCH):
            await anyio.sleep(5 + secrets.randbelow(15))


class WerewolfNotifyProvider(NotifyProvider["Werewolf"]):
    @override
    def message(self, message: UniMessage) -> UniMessage:
        if (
            partners := self.game.players.alive()
            .select(RoleGroup.WEREWOLF)
            .exclude(self.p)
        ):
            message = message.text(
                "\n🐺你的队友:\n\n"
                + "".join(f"  {p.role_name}: {p.name}\n" for p in partners)
            )
        return message


class Werewolf(Player):
    role = Role.WEREWOLF
    role_group = RoleGroup.WEREWOLF
    interact_provider = WerewolfInteractProvider
    notify_provider = WerewolfNotifyProvider

    @property
    @override
    def interact_timeout(self) -> float:
        return self.game.behavior.timeout.werewolf

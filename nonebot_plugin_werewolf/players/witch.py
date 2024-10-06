from nonebot_plugin_alconna.uniseg import UniMessage
from typing_extensions import override

from ..constant import Role, RoleGroup
from ..utils import check_index
from .player import Player, register_role


@register_role(Role.Witch, RoleGroup.GoodGuy)
class Witch(Player):
    antidote: int = 1
    poison: int = 1

    async def handle_killed(self) -> bool:
        msg = UniMessage()
        if (killed := self.game.state.killed) is not None:
            msg.text(f"🔪今晚 {killed.name} 被刀了\n\n")
        else:
            await self.send("ℹ️今晚没有人被刀")
            return False

        if not self.antidote:
            await self.send(msg.text("⚙️你已经用过解药了"))
            return False

        await self.send(msg.text("✏️使用解药请发送 “1”\n❌不使用解药请发送 “/stop”"))

        while True:
            text = await self.receive_text()
            if text == "1":
                self.antidote = 0
                self.selected = killed
                self.game.state.antidote.add(killed)
                await self.send(f"✅你对 {killed.name} 使用了解药，回合结束")
                return True
            if text == "/stop":
                return False
            await self.send("⚠️输入错误: 请输入 “1” 或 “/stop”")

    @override
    async def interact(self) -> None:
        if await self.handle_killed():
            return

        if not self.poison:
            await self.send("⚙️你没有可以使用的药水，回合结束")
            return

        players = self.game.players.alive()
        await self.send(
            UniMessage.text("💫你有一瓶毒药\n")
            .text("玩家列表:\n")
            .text(players.show())
            .text("\n\n🧪发送玩家编号使用毒药")
            .text("\n❌发送 “/stop” 结束回合(不使用药水)")
        )

        while True:
            text = await self.receive_text()
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            if text == "/stop":
                await self.send("ℹ️你选择不使用毒药，回合结束")
                return
            await self.send("⚠️输入错误: 请发送玩家编号或 “/stop”")

        self.poison = 0
        self.selected = players[selected]
        self.game.state.poison.add(self)
        await self.send(f"✅当前回合选择对玩家 {self.selected.name} 使用毒药\n回合结束")

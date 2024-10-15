from nonebot_plugin_alconna.uniseg import UniMessage
from typing_extensions import override

from ..constant import STOP_COMMAND, STOP_COMMAND_PROMPT, Role, RoleGroup
from ..utils import check_index
from .player import Player


@Player.register_role(Role.Guard, RoleGroup.GoodGuy)
class Guard(Player):
    @override
    async def interact(self) -> None:
        players = self.game.players.alive()
        await self.send(
            UniMessage.text("💫请选择需要保护的玩家:\n")
            .text(players.show())
            .text("\n\n🛡️发送编号选择玩家")
            .text(f"\n❌发送 “{STOP_COMMAND_PROMPT}” 结束回合")
        )

        while True:
            text = await self.receive_text()
            if text == STOP_COMMAND:
                await self.send("ℹ️你选择了取消，回合结束")
                return
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                if players[selected] is self.selected:
                    await self.send("⚠️守卫不能连续两晚保护同一目标，请重新选择")
                    continue
                break
            await self.send("⚠️输入错误: 请发送编号选择玩家")

        self.selected = players[selected]
        self.game.state.protected.add(self.selected)
        await self.send(f"✅本回合保护的玩家: {self.selected.name}")

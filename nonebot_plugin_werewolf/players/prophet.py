from nonebot_plugin_alconna.uniseg import UniMessage
from typing_extensions import override

from ..constant import Role, RoleGroup
from ..utils import check_index
from .player import Player, register_role


@register_role(Role.Prophet, RoleGroup.GoodGuy)
class Prophet(Player):
    @override
    async def interact(self) -> None:
        players = self.game.players.alive().exclude(self)
        await self.send(
            UniMessage.text("💫请选择需要查验身份的玩家:\n")
            .text(players.show())
            .text("\n\n🔮发送编号选择玩家")
        )

        while True:
            text = await self.receive_text()
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("⚠️输入错误: 请发送编号选择玩家")

        player = players[selected]
        result = "狼人" if player.role_group == RoleGroup.Werewolf else "好人"
        await self.send(f"✏️玩家 {player.name} 的阵营是『{result}』")

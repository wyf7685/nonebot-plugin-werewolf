from nonebot_plugin_alconna.uniseg import UniMessage
from typing_extensions import override

from ..constant import KillReason
from ..utils import check_index
from .player import Player


class CanShoot(Player):
    @override
    async def post_kill(self) -> None:
        if self.kill_info and self.kill_info.reason == KillReason.Poison:
            await self.send("⚠️你昨晚被女巫毒杀，无法使用技能")
            return await super().post_kill()

        await self.game.send(
            UniMessage.text(f"🕵️{self.role_name} ")
            .at(self.user_id)
            .text(f" 死了\n请{self.role_name}决定击杀目标...")
        )

        self.game.state.shoot = (None, None)
        shoot = await self.shoot()

        if shoot is not None:
            self.game.state.shoot = (self, shoot)
            await self.send(
                UniMessage.text(f"🔫{self.role_name} ")
                .at(self.user_id)
                .text(" 射杀了玩家 ")
                .at(shoot.user_id)
            )
            await shoot.kill(KillReason.Shoot, self)
        else:
            await self.send(f"ℹ️{self.role_name}选择了取消技能")
        return await super().post_kill()

    async def shoot(self) -> Player | None:
        players = self.game.players.alive().exclude(self)
        await self.send(
            "💫请选择需要射杀的玩家:\n"
            + players.show()
            + "\n\n🔫发送编号选择玩家"
            + "\n❌发送 “/stop” 取消技能"
        )

        while True:
            text = await self.receive_text()
            if text == "/stop":
                await self.send("ℹ️已取消技能")
                return None
            index = check_index(text, len(players))
            if index is not None:
                selected = index - 1
                break
            await self.send("⚠️输入错误: 请发送编号选择玩家")

        await self.send(f"🎯选择射杀的玩家: {players[selected].name}")
        return players[selected]

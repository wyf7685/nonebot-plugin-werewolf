from nonebot_plugin_alconna.uniseg import UniMessage
from typing_extensions import override

from ..constant import STOP_COMMAND_PROMPT
from ..models import KillReason
from .player import Player


class CanShoot(Player):
    @override
    async def post_kill(self) -> None:
        if self.kill_info and self.kill_info.reason == KillReason.Poison:
            await self.send("⚠️你昨晚被女巫毒杀，无法使用技能")
            return await super().post_kill()

        await self.game.send(
            UniMessage.text("🕵️玩家 ")
            .at(self.user_id)
            .text(" 死了\n请在私聊决定射杀目标...")
        )

        self.game.state.shoot = None
        shoot = await self.shoot()

        if shoot is not None:
            self.game.state.shoot = self
            await self.send(
                UniMessage.text(f"🔫{self.role_name} ")
                .at(self.user_id)
                .text(" 射杀了玩家 ")
                .at(shoot.user_id)
            )
            await shoot.kill(KillReason.Shoot, self)
            self.selected = shoot
        else:
            await self.send(f"ℹ️{self.role_name}选择了取消技能")
        return await super().post_kill()

    async def shoot(self) -> Player | None:
        players = self.game.players.alive().exclude(self)
        await self.send(
            "💫请选择需要射杀的玩家:\n"
            + players.show()
            + "\n\n🔫发送编号选择玩家"
            + f"\n❌发送 “{STOP_COMMAND_PROMPT}” 取消技能"
        )

        if selected := await self._select_player(
            players,
            on_stop="ℹ️已取消技能，回合结束",
        ):
            await self.send(f"🎯选择射杀的玩家: {selected.name}")

        return selected

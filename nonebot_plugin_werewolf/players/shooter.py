from typing_extensions import override

from nonebot_plugin_alconna import UniMessage

from ..config import stop_command_prompt
from ..models import KillReason
from ..player import KillProvider, Player


class ShooterKillProvider(KillProvider["Player"]):
    @override
    async def post_kill(self) -> None:
        if self.kill_info and self.kill_info.reason == KillReason.POISON:
            await self.p.send("⚠️你昨晚被女巫毒杀，无法使用技能")
            return await super().post_kill()

        await self.game.send(
            UniMessage.text("🕵️玩家 ")
            .at(self.user_id)
            .text(" 死了\n请在私聊决定射杀目标...")
        )

        self.game.context.shooter = None
        shoot = await self.shoot()
        msg = UniMessage.text("玩家 ").at(self.user_id).text(" ")
        if shoot is not None:
            self.game.context.shooter = self.p
            await self.game.send("🔫" + msg.text("射杀了玩家 ").at(shoot.user_id))
            await shoot.kill(KillReason.SHOOT, self.p)
            self.selected = shoot
        else:
            await self.game.send("ℹ️" + msg.text("选择了取消技能"))

        return await super().post_kill()

    async def shoot(self) -> Player | None:
        players = self.game.players.alive().exclude(self.p)
        await self.p.send(
            "💫请选择需要射杀的玩家:\n"
            f"{players.show()}\n\n"
            "🔫发送编号选择玩家\n"
            f"❌发送 “{stop_command_prompt}” 取消技能",
            stop_btn_label="取消技能",
            select_players=players,
        )

        if selected := await self.p.select_player(
            players,
            on_stop="ℹ️已取消技能，回合结束",
            stop_btn_label="取消技能",
        ):
            await self.p.send(f"🎯选择射杀的玩家: {selected.name}")

        return selected

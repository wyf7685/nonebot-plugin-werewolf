from typing_extensions import override

from ..config import stop_command_prompt
from ..models import GameContext, Role, RoleGroup
from ..player import InteractProvider, Player


class GuardInteractProvider(InteractProvider["Guard"]):
    @override
    async def interact(self) -> None:
        players = self.game.players.alive()
        await self.p.send(
            "💫请选择需要保护的玩家:\n"
            f"{players.show()}\n\n"
            "🛡️发送编号选择玩家\n"
            f"❌发送 “{stop_command_prompt}” 结束回合",
            stop_btn_label="结束回合",
            select_players=players,
        )

        self.selected = await self.p.select_player(players, stop_btn_label="结束回合")
        if self.selected:
            self.game.context.protected.add(self.selected)
            await self.p.send(f"✅本回合保护的玩家: {self.selected.name}")


class Guard(Player):
    role = Role.GUARD
    role_group = RoleGroup.GOODGUY
    interact_provider = GuardInteractProvider

    @override
    async def _check_selected(self, player: Player) -> Player | None:
        if (
            self.game.context.state == GameContext.State.NIGHT
            and player is self.selected
        ):
            await self.send("⚠️守卫不能连续两晚保护同一目标，请重新选择")
            return None

        return player

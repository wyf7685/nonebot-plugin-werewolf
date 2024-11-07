from typing_extensions import override

from ..constant import STOP_COMMAND_PROMPT
from ..models import Role, RoleGroup
from .player import Player


@Player.register_role(Role.Guard, RoleGroup.GoodGuy)
class Guard(Player):
    @override
    async def _check_selected(self, player: Player) -> Player | None:
        if player is not self.selected:
            return player
        await self.send("⚠️守卫不能连续两晚保护同一目标，请重新选择")
        return None

    @override
    async def _interact(self) -> None:
        players = self.game.players.alive()
        await self.send(
            "💫请选择需要保护的玩家:\n"
            f"{players.show()}\n\n"
            "🛡️发送编号选择玩家\n"
            f"❌发送 “{STOP_COMMAND_PROMPT}” 结束回合",
            stop_btn_label="结束回合",
            select_players=players,
        )

        self.selected = await self._select_player(players, stop_btn_label="结束回合")
        if self.selected:
            self.game.state.protected.add(self.selected)
            await self.send(f"✅本回合保护的玩家: {self.selected.name}")

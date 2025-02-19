from typing_extensions import override

from ..constant import stop_command_prompt
from ..models import GameState, Role, RoleGroup
from .player import Player


class Guard(Player):
    role = Role.GUARD
    role_group = RoleGroup.GOODGUY

    @override
    async def _check_selected(self, player: Player) -> Player | None:
        if self.game.state.state == GameState.State.NIGHT and player is self.selected:
            await self.send("⚠️守卫不能连续两晚保护同一目标，请重新选择")
            return None

        return player

    @override
    async def _interact(self) -> None:
        players = self.game.players.alive()
        await self.send(
            "💫请选择需要保护的玩家:\n"
            f"{players.show()}\n\n"
            "🛡️发送编号选择玩家\n"
            f"❌发送 “{stop_command_prompt()}” 结束回合",
            stop_btn_label="结束回合",
            select_players=players,
        )

        self.selected = await self._select_player(players, stop_btn_label="结束回合")
        if self.selected:
            self.game.state.protected.add(self.selected)
            await self.send(f"✅本回合保护的玩家: {self.selected.name}")

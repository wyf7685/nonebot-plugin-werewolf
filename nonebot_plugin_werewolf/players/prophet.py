from typing_extensions import override

from ..constant import STOP_COMMAND_PROMPT
from ..models import Role, RoleGroup
from .player import Player


@Player.register_role(Role.Prophet, RoleGroup.GoodGuy)
class Prophet(Player):
    @override
    async def _interact(self) -> None:
        players = self.game.players.alive().exclude(self)
        await self.send(
            "💫请选择需要查验身份的玩家:\n"
            f"{players.show()}\n\n"
            "🔮发送编号选择玩家\n"
            f"❌发送 “{STOP_COMMAND_PROMPT}” 结束回合(不查验身份)"
        )

        if selected := await self._select_player(players):
            result = "狼人" if selected.role_group == RoleGroup.Werewolf else "好人"
            await self.send(f"✏️玩家 {selected.name} 的阵营是『{result}』")

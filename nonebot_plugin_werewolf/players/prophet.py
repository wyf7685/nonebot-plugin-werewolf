from typing_extensions import override

from ..config import stop_command_prompt
from ..models import Role, RoleGroup
from ..player import InteractProvider, Player


class ProphetInteractProvider(InteractProvider["Prophet"]):
    @override
    async def interact(self) -> None:
        players = self.game.players.alive().exclude(self.p)
        await self.p.send(
            "💫请选择需要查验身份的玩家:\n"
            f"{players.show()}\n\n"
            "🔮发送编号选择玩家\n"
            f"❌发送 “{stop_command_prompt}” 结束回合(不查验身份)",
            stop_btn_label="结束回合",
            select_players=players,
        )

        if selected := await self.p.select_player(players, stop_btn_label="结束回合"):
            result = "狼人" if selected.role_group == RoleGroup.WEREWOLF else "好人"
            await self.p.send(f"✏️玩家 {selected.name} 的阵营是『{result}』")


class Prophet(Player):
    role = Role.PROPHET
    role_group = RoleGroup.GOODGUY
    interact_provider = ProphetInteractProvider

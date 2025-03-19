from typing_extensions import override

from ..models import Role, RoleGroup
from .shooter import ShooterKillProvider
from .werewolf import Werewolf


class WolfKing(Werewolf):
    role = Role.WOLFKING
    role_group = RoleGroup.WEREWOLF
    kill_provider = ShooterKillProvider

    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        await self.send("⚙️作为狼王，你可以在死后射杀一名玩家")

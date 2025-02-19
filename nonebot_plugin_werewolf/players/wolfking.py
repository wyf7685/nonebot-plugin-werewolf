from typing_extensions import override

from ..models import Role, RoleGroup
from .can_shoot import CanShoot
from .werewolf import Werewolf


class WolfKing(CanShoot, Werewolf):
    role = Role.WOLFKING
    role_group = RoleGroup.WEREWOLF

    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        await self.send("⚙️作为狼王，你可以在死后射杀一名玩家")

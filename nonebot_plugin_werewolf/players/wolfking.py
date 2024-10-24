from typing_extensions import override

from ..models import Role, RoleGroup
from .can_shoot import CanShoot
from .player import Player
from .werewolf import Werewolf


@Player.register_role(Role.WolfKing, RoleGroup.Werewolf)
class WolfKing(CanShoot, Werewolf):
    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        await self.send("⚙️作为狼王，你可以在死后射杀一名玩家")

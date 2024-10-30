from typing import TYPE_CHECKING

from typing_extensions import override

from ..exception import GameFinished
from ..models import GameStatus, KillReason, Role, RoleGroup
from .player import Player


@Player.register_role(Role.Joker, RoleGroup.Others)
class Joker(Player):
    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        await self.send("⚙️你的胜利条件: 被投票放逐")

    @override
    async def kill(self, reason: KillReason, *killers: Player) -> bool:
        await super().kill(reason, *killers)
        if reason == KillReason.Vote:
            if TYPE_CHECKING:
                assert self.kill_info is not None
            self.game.killed_players.append((self.name, self.kill_info))
            raise GameFinished(GameStatus.Joker)
        return True

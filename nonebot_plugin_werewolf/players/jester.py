from typing_extensions import override

from ..exception import GameFinished
from ..models import GameStatus, KillInfo, KillReason, Role, RoleGroup
from ..player import KillProvider, Player


class JesterKillProvider(KillProvider["Jester"]):
    async def kill(self, reason: KillReason, *killers: Player) -> KillInfo | None:
        kill_info = await super().kill(reason, *killers)
        if kill_info is not None and reason == KillReason.VOTE:
            self.game.killed_players.append((self.name, kill_info))
            raise GameFinished(GameStatus.JESTER)
        return kill_info


class Jester(Player):
    role = Role.JESTER
    role_group = RoleGroup.OTHERS
    kill_provider = JesterKillProvider

    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        await self.send("⚙️你的胜利条件: 被投票放逐")

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot_plugin_alconna.uniseg import UniMessage
from typing_extensions import override

from ..models import KillReason, Role, RoleGroup
from .player import Player

if TYPE_CHECKING:
    from ..player_set import PlayerSet


@Player.register_role(Role.Idiot, RoleGroup.GoodGuy)
class Idiot(Player):
    voted: bool = False

    @override
    async def notify_role(self) -> None:
        await super().notify_role()
        await self.send(
            "作为白痴，你可以在首次被投票放逐时免疫放逐，但在之后的投票中无法继续投票"
        )

    @override
    async def kill(self, reason: KillReason, *killers: Player) -> bool:
        if reason == KillReason.Vote and not self.voted:
            self.voted = True
            await self.game.send(
                UniMessage.text("⚙️玩家")
                .at(self.user_id)
                .text(" 的身份是白痴\n")
                .text("免疫本次投票放逐，且接下来无法参与投票"),
            )
            return False
        return await super().kill(reason, *killers)

    @override
    async def vote(self, players: PlayerSet) -> Player | None:
        if self.voted:
            await self.send("ℹ️你已经发动过白痴身份的技能，无法参与本次投票")
            return None
        return await super().vote(players)

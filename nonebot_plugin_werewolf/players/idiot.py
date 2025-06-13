from typing import TYPE_CHECKING
from typing_extensions import override

from nonebot_plugin_alconna import UniMessage

from ..models import KillInfo, KillReason, Role, RoleGroup
from ..player import KillProvider, NotifyProvider, Player

if TYPE_CHECKING:
    from ..player_set import PlayerSet


class IdiotKillProvider(KillProvider["Idiot"]):
    voted = KillProvider.proxy(bool)

    @override
    async def kill(self, reason: KillReason, *killers: Player) -> KillInfo | None:
        if reason == KillReason.VOTE and not self.voted:
            self.voted = True
            await self.game.send(
                UniMessage.text("⚙️玩家")
                .at(self.user_id)
                .text(" 的身份是白痴\n")
                .text("免疫本次投票放逐，且接下来无法参与投票"),
            )
            return None

        return await super().kill(reason, *killers)


class IdiotNotifyProvider(NotifyProvider["Idiot"]):
    @override
    def message(self, message: UniMessage) -> UniMessage:
        return message.text(
            "作为白痴，你可以在首次被投票放逐时免疫放逐，但在之后的投票中无法继续投票"
        )


class Idiot(Player):
    role = Role.IDIOT
    role_group = RoleGroup.GOODGUY
    kill_provider = IdiotKillProvider
    notify_provider = IdiotNotifyProvider

    voted: bool = False

    @override
    async def vote(self, players: "PlayerSet") -> Player | None:
        if self.voted:
            await self.send("ℹ️你已经发动过白痴身份的技能，无法参与本次投票")
            return None
        return await super().vote(players)

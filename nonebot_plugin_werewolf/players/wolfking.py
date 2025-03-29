from typing_extensions import override

from nonebot_plugin_alconna import UniMessage

from ..models import Role, RoleGroup
from .shooter import ShooterKillProvider
from .werewolf import Werewolf, WerewolfNotifyProvider


class WolfKingNotifyProvider(WerewolfNotifyProvider):
    @override
    def message(self, message: UniMessage) -> UniMessage:
        return super().message(message).text("⚙️作为狼王，你可以在死后射杀一名玩家")


class WolfKing(Werewolf):
    role = Role.WOLFKING
    role_group = RoleGroup.WEREWOLF
    kill_provider = ShooterKillProvider
    notify_provider = WolfKingNotifyProvider

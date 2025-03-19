from ..models import Role, RoleGroup
from ..player import Player
from .shooter import ShooterKillProvider


class Hunter(Player):
    role = Role.HUNTER
    role_group = RoleGroup.GOODGUY
    kill_provider = ShooterKillProvider

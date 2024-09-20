from ..constant import Role, RoleGroup
from .player import Player, register_role


@register_role(Role.Civilian, RoleGroup.GoodGuy)
class Civilian(Player):
    pass

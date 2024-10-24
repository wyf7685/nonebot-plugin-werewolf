from ..models import Role, RoleGroup
from .player import Player


@Player.register_role(Role.Civilian, RoleGroup.GoodGuy)
class Civilian(Player):
    pass

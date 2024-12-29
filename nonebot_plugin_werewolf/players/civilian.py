from ..models import Role, RoleGroup
from .player import Player


@Player.register_role(Role.CIVILIAN, RoleGroup.GOODGUY)
class Civilian(Player):
    pass

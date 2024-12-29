from ..models import Role, RoleGroup
from .can_shoot import CanShoot
from .player import Player


@Player.register_role(Role.HUNTER, RoleGroup.GOODGUY)
class Hunter(CanShoot, Player):
    pass

from ..models import Role, RoleGroup
from .can_shoot import CanShoot
from .player import Player


class Hunter(CanShoot, Player):
    role = Role.HUNTER
    role_group = RoleGroup.GOODGUY

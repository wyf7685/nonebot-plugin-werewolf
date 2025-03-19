from ..models import Role, RoleGroup
from ..player import Player


class Civilian(Player):
    role = Role.CIVILIAN
    role_group = RoleGroup.GOODGUY

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from .config import config

if TYPE_CHECKING:
    from .player import Player


class Role(Enum):
    # 狼人
    狼人 = auto()
    狼王 = auto()

    # 神职
    预言家 = auto()
    女巫 = auto()
    猎人 = auto()
    守卫 = auto()
    白痴 = auto()

    # 平民
    平民 = auto()


class RoleGroup(Enum):
    狼人 = auto()
    好人 = auto()


class KillReason(Enum):
    Kill = auto()
    Poison = auto()
    Shoot = auto()
    Vote = auto()


class GameStatus(Enum):
    Good = auto()
    Bad = auto()
    Unset = auto()


@dataclass
class GameState:
    killed: "Player | None" = None
    shoot: tuple["Player", "Player"] | tuple[None, None] = (None, None)
    protected: "Player | None" = None
    potion: tuple["Player | None", tuple[bool, bool]] = (None, (False, False))


player_preset: dict[int, tuple[int, int, int]] = {
    # 总人数: (狼, 神, 民)
    6: (1, 3, 2),
    7: (2, 3, 2),
    8: (2, 3, 3),
    9: (2, 4, 3),
    10: (3, 4, 3),
    11: (3, 5, 3),
    12: (4, 5, 3),
}

if config.override_preset is not None:
    player_preset |= {i[0]: i[1:] for i in config.override_preset}

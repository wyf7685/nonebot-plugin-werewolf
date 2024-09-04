from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from .config import config

if TYPE_CHECKING:
    from .player import Player


class Role(Enum):
    # 狼人
    Werewolf = auto()
    WolfKing = auto()

    # 神职
    Prophet = auto()
    Witch = auto()
    Hunter = auto()
    Guard = auto()
    Idiot = auto()

    # 平民
    Civilian = auto()


class RoleGroup(Enum):
    Werewolf = auto()
    GoodGuy = auto()


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
    day: int
    killed: Player | None = None
    shoot: tuple[Player, Player] | tuple[None, None] = (None, None)
    protected: Player | None = None
    potion: tuple[Player | None, tuple[bool, bool]] = (None, (False, False))


role_name_conv: dict[Role | RoleGroup, str] = {
    Role.Werewolf: "狼人",
    Role.WolfKing: "狼王",
    Role.Prophet: "预言家",
    Role.Witch: "女巫",
    Role.Hunter: "猎人",
    Role.Guard: "守卫",
    Role.Idiot: "白痴",
    Role.Civilian: "平民",
    RoleGroup.Werewolf: "狼人",
    RoleGroup.GoodGuy: "好人",
}

player_preset: dict[int, tuple[int, int, int]] = {
    # 总人数: (狼, 神, 民)
    6: (1, 2, 3),
    7: (2, 2, 3),
    8: (2, 3, 3),
    9: (2, 4, 3),
    10: (3, 4, 3),
    11: (3, 5, 3),
    12: (4, 5, 3),
}

if config.override_preset is not None:
    player_preset |= {i[0]: i[1:] for i in config.override_preset}

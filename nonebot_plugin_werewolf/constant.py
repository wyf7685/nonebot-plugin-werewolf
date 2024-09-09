from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player


class Role(Enum):
    # 狼人
    Werewolf = 1
    WolfKing = 2

    # 神职
    Prophet = 11
    Witch = 12
    Hunter = 13
    Guard = 14
    Idiot = 15

    # 其他
    Joker = 51

    # 平民
    Civilian = 0


class RoleGroup(Enum):
    Werewolf = auto()
    GoodGuy = auto()
    Others = auto()


class KillReason(Enum):
    Werewolf = auto()
    Poison = auto()
    Shoot = auto()
    Vote = auto()


class GameStatus(Enum):
    GoodGuy = auto()
    Werewolf = auto()
    Unset = auto()
    Joker = auto()


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
    Role.Joker: "小丑",
    Role.Civilian: "平民",
    RoleGroup.Werewolf: "狼人",
    RoleGroup.GoodGuy: "好人",
    RoleGroup.Others: "其他",
}

default_role_preset: dict[int, tuple[int, int, int]] = {
    # 总人数: (狼, 神, 民)
    6: (1, 2, 3),
    7: (2, 2, 3),
    8: (2, 3, 3),
    9: (2, 4, 3),
    10: (3, 4, 3),
    11: (3, 5, 3),
    12: (4, 5, 3),
}

default_werewolf_priority: list[Role] = [
    Role.Werewolf,
    Role.Werewolf,
    Role.WolfKing,
    Role.Werewolf,
]
default_priesthood_proirity: list[Role] = [
    Role.Witch,
    Role.Prophet,
    Role.Hunter,
    Role.Guard,
    Role.Idiot,
]

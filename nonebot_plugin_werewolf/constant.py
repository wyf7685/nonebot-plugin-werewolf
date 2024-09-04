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

    # 平民
    Civilian = 0


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

role_preset: dict[int, tuple[int, int, int]] = {
    # 总人数: (狼, 神, 民)
    6: (1, 2, 3),
    7: (2, 2, 3),
    8: (2, 3, 3),
    9: (2, 4, 3),
    10: (3, 4, 3),
    11: (3, 5, 3),
    12: (4, 5, 3),
}

werewolf_priority: list[Role] = [
    Role.Werewolf,
    Role.Werewolf,
    Role.WolfKing,
    Role.Werewolf,
]
priesthood_proirity: list[Role] = [
    Role.Witch,
    Role.Prophet,
    Role.Hunter,
    Role.Guard,
    Role.Idiot,
]


def __apply_config():
    from .config import config

    global role_preset, werewolf_priority, priesthood_proirity

    if config.role_preset is not None:
        for preset in config.role_preset:
            if preset[0] != preset[1:]:
                raise RuntimeError(
                    "配置项 `role_preset` 错误: "
                    f"预设总人数为 {preset[0]}, 实际总人数为 {sum(preset[1:])}"
                )
        role_preset |= {i[0]: i[1:] for i in config.role_preset}

    if (priority := config.werewolf_priority) is not None:
        min_length = max(i[0] for i in role_preset.values())
        if len(priority) < min_length:
            raise RuntimeError(
                f"配置项 `werewolf_priority` 错误: 应至少为 {min_length} 项"
            )
        werewolf_priority = priority

    if (priority := config.priesthood_proirity) is not None:
        min_length = max(i[1] for i in role_preset.values())
        if len(priority) < min_length:
            raise RuntimeError(
                f"配置项 `priesthood_proirity` 错误: 应至少为 {min_length} 项"
            )
        priesthood_proirity = priority


__apply_config()

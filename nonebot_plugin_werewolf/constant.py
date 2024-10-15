from __future__ import annotations

import dataclasses
from enum import Enum, auto
from typing import TYPE_CHECKING

import nonebot

if TYPE_CHECKING:
    from .players import Player


COMMAND_START = next(
    iter(sorted(nonebot.get_driver().config.command_start, key=len)), ""
)
STOP_COMMAND_PROMPT = f"{COMMAND_START}stop"
STOP_COMMAND = "{{stop}}"


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
    Joker = auto()


@dataclasses.dataclass
class GameState:
    day: int
    """当前天数记录, 不会被 `reset()` 重置"""
    killed: Player | None = None
    """当晚狼人击杀目标, `None` 则为空刀"""
    shoot: Player | None = None
    """当前执行射杀操作的玩家"""
    antidote: set[Player] = dataclasses.field(default_factory=set)
    """当晚女巫使用解药的目标"""
    poison: set[Player] = dataclasses.field(default_factory=set)
    """当晚使用了毒药的女巫"""
    protected: set[Player] = dataclasses.field(default_factory=set)
    """当晚守卫保护的目标"""

    def reset(self) -> None:
        self.killed = None
        self.shoot = None
        self.antidote = set()
        self.poison = set()
        self.protected = set()


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

role_emoji: dict[Role, str] = {
    Role.Werewolf: "🐺",
    Role.WolfKing: "🐺👑",
    Role.Prophet: "🔮",
    Role.Witch: "🧙‍♀️",
    Role.Hunter: "🕵️",
    Role.Guard: "🛡️",
    Role.Idiot: "👨🏻‍🦲",
    Role.Joker: "🤡",
    Role.Civilian: "👨🏻‍🌾",
}

RolePresetDict = dict[int, tuple[int, int, int]]
RolePresetConfig = RolePresetDict | list[tuple[int, int, int, int]]

default_role_preset: RolePresetDict = {
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

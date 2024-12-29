import dataclasses
from enum import Enum, auto
from typing import TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    from .players import Player


class Role(int, Enum):
    # 狼人
    WEREWOLF = 1
    WOLFKING = 2

    # 神职
    PROPHET = 11
    WITCH = 12
    HUNTER = 13
    GUARD = 14
    IDIOT = 15

    # 其他
    JESTER = 51

    # 平民
    CIVILIAN = 0


class RoleGroup(Enum):
    WEREWOLF = auto()
    GOODGUY = auto()
    OTHERS = auto()


class KillReason(Enum):
    WEREWOLF = auto()
    POISON = auto()
    SHOOT = auto()
    VOTE = auto()


class GameStatus(Enum):
    GOODGUY = auto()
    WEREWOLF = auto()
    JESTER = auto()


@dataclasses.dataclass
class GameState:
    day: int
    """当前天数记录, 不会被 `reset()` 重置"""
    werewolf_finished: anyio.Event = dataclasses.field(default_factory=anyio.Event)
    """狼人交互是否结束"""
    killed: "Player | None" = None
    """当晚狼人击杀目标, `None` 则为空刀"""
    shoot: "Player | None" = None
    """当前执行射杀操作的玩家"""
    antidote: set["Player"] = dataclasses.field(default_factory=set)
    """当晚女巫使用解药的目标"""
    poison: set["Player"] = dataclasses.field(default_factory=set)
    """当晚使用了毒药的女巫"""
    protected: set["Player"] = dataclasses.field(default_factory=set)
    """当晚守卫保护的目标"""

    def reset(self) -> None:
        self.werewolf_finished = anyio.Event()
        self.killed = None
        self.shoot = None
        self.antidote = set()
        self.poison = set()
        self.protected = set()


@dataclasses.dataclass
class KillInfo:
    reason: KillReason
    killers: list[str]

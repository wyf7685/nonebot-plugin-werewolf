import dataclasses
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .players import Player


class Role(int, Enum):
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
        self.killed = None
        self.shoot = None
        self.antidote = set()
        self.poison = set()
        self.protected = set()


@dataclasses.dataclass
class KillInfo:
    reason: KillReason
    killers: list[str]

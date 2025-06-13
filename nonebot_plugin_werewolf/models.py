import dataclasses
import functools
from enum import Enum, auto
from typing import TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    from .player import Player


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

    @functools.cached_property
    def emoji(self) -> str:
        from .constant import ROLE_EMOJI

        return ROLE_EMOJI[self]

    @functools.cached_property
    def display(self) -> str:
        from .constant import ROLE_NAME_CONV

        return ROLE_NAME_CONV[self]


class RoleGroup(Enum):
    WEREWOLF = auto()
    GOODGUY = auto()
    OTHERS = auto()

    @functools.cached_property
    def display(self) -> str:
        from .constant import ROLE_NAME_CONV

        return ROLE_NAME_CONV[self]


class KillReason(Enum):
    WEREWOLF = auto()
    POISON = auto()
    SHOOT = auto()
    VOTE = auto()

    @functools.cached_property
    def display(self) -> tuple[str, str]:
        from .constant import REPORT_TEXT

        return REPORT_TEXT[self]


class GameStatus(Enum):
    GOODGUY = auto()
    WEREWOLF = auto()
    JESTER = auto()

    @functools.cached_property
    def display(self) -> str:
        from .constant import GAME_STATUS_CONV

        return GAME_STATUS_CONV[self]


@dataclasses.dataclass
class GameContext:
    class State(Enum):
        DAY = auto()
        VOTE = auto()
        NIGHT = auto()

    day: int
    """当前天数记录, 不会被 `reset()` 重置"""
    state: State = State.NIGHT
    """当前游戏状态, 不会被 `reset()` 重置"""
    _werewolf_interact_count: int = 0
    """内部属性, 记录当晚狼人交互状态"""
    werewolf_finished: anyio.Event = dataclasses.field(default_factory=anyio.Event)
    """狼人交互是否结束"""
    killed: "Player | None" = None
    """当晚狼人击杀目标, `None` 则为空刀"""
    shooter: "Player | None" = None
    """当前执行射杀操作的玩家"""
    antidote: set["Player"] = dataclasses.field(default_factory=set)
    """当晚女巫使用解药的目标"""
    poison: set["Player"] = dataclasses.field(default_factory=set)
    """当晚使用了毒药的女巫"""
    protected: set["Player"] = dataclasses.field(default_factory=set)
    """当晚守卫保护的目标"""

    def reset(self) -> None:
        self.werewolf_finished = anyio.Event()
        self._werewolf_interact_count = 0
        self.killed = None
        self.shooter = None
        self.antidote = set()
        self.poison = set()
        self.protected = set()

    def werewolf_start(self) -> None:
        self._werewolf_interact_count += 1

    def werewolf_end(self) -> bool:
        self._werewolf_interact_count -= 1
        if self._werewolf_interact_count == 0:
            self.werewolf_finished.set()
        return self.werewolf_finished.is_set()


@dataclasses.dataclass
class KillInfo:
    reason: KillReason
    killers: list[str]

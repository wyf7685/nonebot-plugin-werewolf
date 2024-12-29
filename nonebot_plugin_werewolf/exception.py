from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import GameStatus


class Error(Exception):
    """插件错误类型基类"""


class GameFinished(Error):  # noqa: N818
    """游戏结束时抛出，无视游戏进程进入结算"""

    status: "GameStatus"

    def __init__(self, status: "GameStatus") -> None:
        self.status = status

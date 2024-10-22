import functools
from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar

import anyio
from nonebot_plugin_alconna import UniMessage
from nonebot_plugin_uninfo import Session

if TYPE_CHECKING:
    from .player_set import PlayerSet
    from .players import Player

T = TypeVar("T")


def check_index(text: str, arrlen: int) -> int | None:
    if text.isdigit():
        index = int(text)
        if 1 <= index <= arrlen:
            return index
    return None


def link(text: str, url: str | None) -> str:
    return text if url is None else f"\u001b]8;;{url}\u0007{text}\u001b]8;;\u0007"


def extract_session_member_nick(session: Session) -> str | None:
    return (
        (session.member and session.member.nick)
        or session.user.nick
        or session.user.name
    )


class _InputTask:
    _event: anyio.Event
    _msg: UniMessage

    def __init__(self) -> None:
        self._event = anyio.Event()

    def set(self, msg: UniMessage) -> None:
        self._msg = msg
        self._event.set()

    async def wait(self) -> UniMessage:
        await self._event.wait()
        return self._msg


class InputStore:
    locks: ClassVar[dict[str, anyio.Lock]] = defaultdict(anyio.Lock)
    tasks: ClassVar[dict[str, _InputTask]] = {}

    @classmethod
    async def fetch(cls, user_id: str, group_id: str | None = None) -> UniMessage[Any]:
        key = f"{group_id}_{user_id}"
        async with cls.locks[key]:
            cls.tasks[key] = task = _InputTask()
            return await task.wait()

    @classmethod
    def put(cls, msg: UniMessage, user_id: str, group_id: str | None = None) -> None:
        key = f"{group_id}_{user_id}"
        if task := cls.tasks.pop(key, None):
            task.set(msg)

    @classmethod
    def cleanup(cls, players: list[str], group_id: str) -> None:
        for key in (f"{g}_{p}" for p in players for g in (group_id, None)):
            if key in cls.locks:
                del cls.locks[key]
            if key in cls.tasks:
                del cls.tasks[key]


@functools.cache
def cached_player_set() -> type["PlayerSet"]:
    from .player_set import PlayerSet

    return PlayerSet


def as_player_set(*player: "Player") -> "PlayerSet":
    return cached_player_set()(player)

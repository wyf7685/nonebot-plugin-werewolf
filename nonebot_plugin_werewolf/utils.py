import abc
import functools
import itertools
from collections import defaultdict
from typing import TYPE_CHECKING, Any, ClassVar, Generic, ParamSpec, TypeVar

import anyio
import anyio.streams.memory
from nonebot.adapters import Bot, Event
from nonebot.internal.matcher import current_bot
from nonebot_plugin_alconna.uniseg import (
    Button,
    FallbackStrategy,
    Keyboard,
    Receipt,
    Target,
    UniMessage,
)
from nonebot_plugin_uninfo import Session

from .config import config
from .constant import STOP_COMMAND, STOP_COMMAND_PROMPT

if TYPE_CHECKING:
    from .player_set import PlayerSet
    from .players import Player

T = TypeVar("T")
P = ParamSpec("P")


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

    @staticmethod
    def _key(user_id: str, group_id: str | None) -> str:
        return f"{group_id}_{user_id}"

    @classmethod
    async def fetch(cls, user_id: str, group_id: str | None = None) -> UniMessage[Any]:
        key = cls._key(user_id, group_id)
        async with cls.locks[key]:
            cls.tasks[key] = task = _InputTask()
            try:
                return await task.wait()
            finally:
                cls.tasks.pop(key, None)

    @classmethod
    async def fetch_until_stop(cls, user_id: str, group_id: str | None = None) -> None:
        while True:
            msg = await cls.fetch(user_id, group_id)
            if msg.extract_plain_text().strip() == STOP_COMMAND:
                return

    @classmethod
    def put(cls, msg: UniMessage, user_id: str, group_id: str | None = None) -> None:
        key = cls._key(user_id, group_id)
        if task := cls.tasks.pop(key, None):
            task.set(msg)

    @classmethod
    def cleanup(cls, players: list[str], group_id: str) -> None:
        for p, g in itertools.product(players, (group_id, None)):
            key = cls._key(p, g)
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


class ObjectStream(Generic[T]):
    __unset: Any = object()
    _send: anyio.streams.memory.MemoryObjectSendStream[T]
    _recv: anyio.streams.memory.MemoryObjectReceiveStream[T]
    _closed: anyio.Event

    def __init__(self, max_buffer_size: float = 0) -> None:
        self._send, self._recv = anyio.create_memory_object_stream(max_buffer_size)
        self._closed = anyio.Event()

    async def send(self, obj: T) -> None:
        await self._send.send(obj)

    async def recv(self) -> T:
        result = self.__unset

        async def _recv() -> None:
            nonlocal result
            result = await self._recv.receive()
            tg.cancel_scope.cancel()

        async def _cancel() -> None:
            await self._closed.wait()
            tg.cancel_scope.cancel()

        async with anyio.create_task_group() as tg:
            tg.start_soon(_recv)
            tg.start_soon(_cancel)

        if result is self.__unset:
            raise anyio.EndOfStream

        return result

    def close(self) -> None:
        self._closed.set()

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    async def wait_closed(self) -> None:
        await self._closed.wait()


def btn(label: str, text: str, /) -> Button:
    return Button(flag="input", label=label, text=text)


def add_stop_button(msg: str | UniMessage, label: str | None = None) -> UniMessage:
    if isinstance(msg, str):
        msg = UniMessage.text(msg)
    return msg.keyboard(btn(label or STOP_COMMAND_PROMPT, STOP_COMMAND_PROMPT))


def add_players_button(msg: str | UniMessage, players: "PlayerSet") -> UniMessage:
    if isinstance(msg, str):
        msg = UniMessage.text(msg)

    pls = list(enumerate(players, 1))
    while pls:
        msg = msg.keyboard(*(btn(p.name, str(i)) for i, p in pls[:3]))
        pls = pls[3:]
    return msg


class SendHandler(abc.ABC, Generic[P]):
    bot: Bot
    target: Event | Target
    reply_to: bool | None = None
    last_msg: UniMessage | None = None
    last_receipt: Receipt | None = None

    def update(self, target: Event | Target, bot: Bot | None = None) -> None:
        self.bot = bot or current_bot.get()
        self.target = target

    async def _edit(self) -> None:
        if (
            config.enable_button
            and self.last_msg is not None
            and self.last_receipt is not None
            and self.last_receipt.editable
        ):
            await self.last_receipt.edit(self.last_msg.exclude(Keyboard))

    async def _send(self, message: UniMessage) -> None:
        if not config.enable_button:
            message = message.exclude(Keyboard)
        receipt = await message.send(
            target=self.target,
            bot=self.bot,
            reply_to=self.reply_to,
            fallback=FallbackStrategy.ignore,
        )
        self.last_msg = message
        self.last_receipt = receipt

    @abc.abstractmethod
    def solve_msg(
        self,
        msg: UniMessage,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> UniMessage:
        raise NotImplementedError

    async def send(
        self,
        msg: str | UniMessage,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> Receipt:
        msg = UniMessage.text(msg) if isinstance(msg, str) else msg
        msg = self.solve_msg(msg, *args, **kwargs)

        async with anyio.create_task_group() as tg:
            tg.start_soon(self._edit)
            tg.start_soon(self._send, msg)

        if TYPE_CHECKING:
            assert self.last_receipt is not None

        return self.last_receipt
